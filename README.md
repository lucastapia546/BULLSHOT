# BULLSHOT

A paper-trading agent for a small ($100) stock account. Claude reads real quotes and account data
through Robinhood's official Agentic Trading MCP, decides trades with a written strategy, records them
on paper in a local ledger, and writes takeaways. A report page shows trades, P&L vs SPY, and whether
the strategy has earned a shot at real money.

**v1 never places real orders.** A Claude Code hook blocks every Robinhood tool that isn't a read.

## How it fits together

```
Claude Code  ──read-only──▶  Robinhood MCP (agent.robinhood.com/mcp/trading)
    │   ▲ hook_guard.py blocks order / cancel / transfer / unknown tools
    ▼
tradeagent.cli  ──guardrails.py (config.toml caps)──▶  data/trades.db (SQLite paper ledger)
                                                            │
                                                            ▼
                                                    data/report.html
```

| File | What it does |
|---|---|
| `config.toml` | Mode (`paper`), $ caps, position limits, daily loss stop, graduation bar |
| `STRATEGY.md` | The trading rules the agent follows |
| `tradeagent/guardrails.py` | Pure checks every order must pass |
| `tradeagent/hook_guard.py` | Claude Code PreToolUse hook: allows reads, blocks everything else |
| `tradeagent/cli.py` | `status`, `mark`, `order`, `note`, `report` |
| `tradeagent/report.py` | Metrics and the HTML report |
| `.claude/commands/paper-day.md` | The `/paper-day` routine |

## Setup (on your computer)

1. Python 3.11+ and [Claude Code](https://code.claude.com).
2. Clone this repo and `cd` into it.
3. Connect Robinhood's MCP (you sign in on Robinhood's own page; never paste credentials into chat):
   ```
   claude mcp add robinhood-trading --transport http https://agent.robinhood.com/mcp/trading
   ```
4. In the Robinhood app, open the MCP account's Agent Settings and turn **Trade approvals on**,
   and leave that account unfunded while we're paper trading. Belt and braces on top of the hook.
5. Start `claude` in this folder and run `/paper-day` once per trading day, ideally in the last hour
   before the close.
6. Open `data/report.html` in a browser.

Preview with fake data: `TRADEAGENT_DB=data/demo.db python3 scripts/demo_data.py && TRADEAGENT_DB=data/demo.db python3 -m tradeagent.cli report --out data/demo_report.html`

## Tests

```
pip install -r requirements-dev.txt
python3 -m pytest -q
```

## Not built yet
- Live trading. It needs Lucas's explicit go-ahead after the paper results clear the bar in `config.toml`.
- Scheduling `/paper-day` automatically.
- Importing Lucas's real Robinhood order history into the report.
