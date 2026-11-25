# Trading agent rules

This repo runs a **paper-trading** agent for a $100 stock account. Claude reads real market and
account data through the official Robinhood MCP (`robinhood-trading`) and records simulated trades
in a local SQLite ledger. Nothing here places real orders.

## Hard rules
- Never place, modify, or cancel a real order, and never move money or change Robinhood settings.
  `.claude/settings.json` runs `tradeagent/hook_guard.py` before every Robinhood tool call and blocks
  anything that isn't a read. Do not try to work around it.
- Every trade goes through `python3 -m tradeagent.cli order`, which enforces config.toml limits.
  If it blocks a trade, accept the block. Don't split or resize an order to sneak past a limit.
- Stocks and ETFs only. No options, crypto, margin, or short selling.
- Never ask Lucas for passwords, MFA codes, or API keys. Robinhood sign-in happens in Robinhood's own OAuth page.
- `mode` in config.toml stays `"paper"`. Only Lucas changes it, and v1 has no live-trading path anyway.

## Workflow
- Daily: `/paper-day` (see `.claude/commands/paper-day.md`).
- Strategy lives in `STRATEGY.md`. Change it only between sessions, and log why with
  `python3 -m tradeagent.cli note --kind plan --text "..."` so results stay comparable.
- The report at `data/report.html` shows whether paper results clear the graduation bar in config.toml.

## Dev
- `python3 -m pytest -q` runs the guardrail and hook tests.
- Python 3.11+ standard library only at runtime.
