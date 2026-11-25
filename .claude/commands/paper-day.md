---
description: Run one paper-trading day: read market data from Robinhood, decide trades, record them on paper, write takeaways, rebuild the report.
---

Run today's paper-trading session. Follow CLAUDE.md and STRATEGY.md exactly.

0. If running in the cloud (`$CLAUDE_CODE_REMOTE` is `true`), first run `scripts/ledger_sync.sh pull` to restore the paper ledger.
1. `python3 -m tradeagent.cli status` to see paper cash, positions, and orders left today.
2. Using ONLY allowlisted read tools on the Robinhood MCP (`robinhood-trading` locally, or the Robinhood connector in the cloud), get current quotes (`get_equity_quotes`) for every symbol held, SPY, and the watchlist in STRATEGY.md. Use `get_equity_historicals` or `get_equity_technical_indicators` for the 10-day high and 50-day average, and `get_earnings_calendar` to avoid entering right before earnings.
3. `python3 -m tradeagent.cli mark --prices '<json of symbol: price>' --benchmark <SPY price>`.
4. Apply STRATEGY.md's exit rules to each holding first, then its entry rules. For each trade, run `python3 -m tradeagent.cli order ...` with the strategy name and a one-sentence reason that cites the numbers. If the guardrails block it, accept that and do not retry with tweaked numbers.
5. Write 1-3 takeaways with `python3 -m tradeagent.cli note --kind takeaway --text "..."`: what happened, what you learned, what you'd change. Be specific and honest about losses.
6. `python3 -m tradeagent.cli report` and print the summary: equity, return vs SPY, trades made, and graduation progress.
7. In the cloud, finish with `scripts/ledger_sync.sh push` so the ledger and report are saved to the `paper-data` branch.

If the Robinhood tools are missing or ask for sign-in, stop, write a `lesson` note saying the Robinhood connection needs a fresh sign-in, and push the ledger. Never trade on made-up or stale prices.

Never call a Robinhood tool that places, modifies, or cancels an order. The hook blocks them anyway.
