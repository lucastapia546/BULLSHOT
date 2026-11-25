"""Claude Code PreToolUse hook for the Robinhood MCP.

Claude Code pipes the pending tool call to stdin as JSON. Exit code 2 blocks the
call and shows stderr to the agent. This hook fails closed: a Robinhood tool runs
only if its exact name is in [mcp].allowed_tools in config.toml. Orders, cancels,
option exercises, trade-approval actions, watchlist/scan/alert writes, banking and
credit data, and any tool Robinhood adds later are all blocked.
"""
from __future__ import annotations

import json
import sys

from .config import load_config

ALLOW, BLOCK = 0, 2


def classify(tool_name: str, cfg) -> str:
    """Return 'other' (not Robinhood), 'read' (allowlisted), 'order', or 'blocked'."""
    # Local: mcp__robinhood-trading__<tool>. Cloud claude.ai connector: mcp__<connector name>__<tool>,
    # where the connector name varies, so match any MCP server whose name mentions Robinhood.
    if not tool_name.startswith("mcp__") or "__" not in tool_name[5:]:
        return "other"
    server, name = tool_name[5:].rsplit("__", 1)
    if server != cfg.server_name and "robinhood" not in server.lower():
        return "other"
    if name in cfg.allowed_tools:
        return "read"
    if any(p in name.lower() for p in cfg.order_patterns):
        return "order"
    return "blocked"


def decide(event: dict, cfg) -> tuple[int, str]:
    tool = event.get("tool_name", "")
    kind = classify(tool, cfg)
    if kind in ("other", "read"):
        return ALLOW, ""
    if kind == "order":
        return BLOCK, (
            f"BLOCKED {tool}: this agent never places, reviews, cancels, or approves real orders "
            f"(mode={cfg.mode}). Record the trade on paper instead: python3 -m tradeagent.cli order "
            "--symbol SYM --side buy|sell --dollars N --price P --strategy NAME --reason '...'")
    return BLOCK, (f"BLOCKED {tool}: not on the read-only allowlist ([mcp].allowed_tools in config.toml). "
                   "Only Lucas adds tools to that list.")


def main() -> None:
    try:
        event = json.load(sys.stdin)
        cfg = load_config()
    except Exception as exc:  # fail closed on anything unexpected
        print(f"BLOCKED: trade guard could not run ({exc})", file=sys.stderr)
        sys.exit(BLOCK)
    code, msg = decide(event, cfg)
    if msg:
        print(msg, file=sys.stderr)
    sys.exit(code)


if __name__ == "__main__":
    main()
