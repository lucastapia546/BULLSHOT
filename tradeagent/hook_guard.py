"""Claude Code PreToolUse hook for the Robinhood MCP.

Claude Code pipes the pending tool call to stdin as JSON. Exit code 2 blocks the
call and shows stderr to the agent. This hook fails closed:

  * read tools (quotes, positions, history...) are allowed
  * order, cancel, transfer and settings tools are always blocked in v1
  * any tool we can't classify is blocked
"""
from __future__ import annotations

import json
import re
import sys

from .config import load_config

ALLOW, BLOCK = 0, 2


def classify(tool_name: str, cfg) -> str:
    """Return 'read', 'order', 'forbidden', 'unknown', or 'other' (not Robinhood)."""
    prefix = f"mcp__{cfg.server_name}__"
    if not tool_name.startswith(prefix):
        return "other"
    name = tool_name[len(prefix):].lower()
    words = set(re.split(r"[_\-\s.]+", name)) | {name}

    def hit(patterns):
        return any(p in name for p in patterns)

    if hit(cfg.forbidden_patterns):
        return "forbidden"
    if hit(cfg.order_patterns):
        # "get_orders" / "list_order_history" are reads; "place_order" is not.
        if words & {"get", "list", "history", "search", "status"}:
            return "read"
        return "order"
    if hit(cfg.read_patterns):
        return "read"
    return "unknown"


def decide(event: dict, cfg) -> tuple[int, str]:
    tool = event.get("tool_name", "")
    kind = classify(tool, cfg)
    if kind in ("other", "read"):
        return ALLOW, ""
    if kind == "order":
        return BLOCK, (
            f"BLOCKED {tool}: real orders are disabled (mode={cfg.mode}). "
            "Record the trade on paper instead: python -m tradeagent.cli order "
            "--symbol SYM --side buy|sell --dollars N --price P --strategy NAME --reason '...'")
    if kind == "forbidden":
        return BLOCK, f"BLOCKED {tool}: this agent never cancels, modifies, transfers, or changes settings."
    return BLOCK, (f"BLOCKED {tool}: not on the read-only allowlist. If it is a harmless read, "
                   "add a matching pattern to [mcp].read_patterns in config.toml.")


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
