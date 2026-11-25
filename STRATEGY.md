# Strategy v1: "pullback" (moderate risk, daily)

A starting hypothesis to test on paper, not a proven edge. Expect to revise it.

## Watchlist
Liquid large caps and broad ETFs, so fills and quotes are realistic:
SPY, QQQ, AAPL, MSFT, NVDA, AMZN, GOOGL, META, JPM, XLE

## Entry (buy)
Buy up to $20 of a watchlist name when ALL hold:
1. Price is above its 50-day average (uptrend).
2. Price has pulled back at least 3% from its 10-day high.
3. Today's move is not worse than -4% (avoid catching a crash on news).
4. We don't already hold it and the guardrails allow a new position.
Pick at most one new entry per day, the one with the deepest pullback that still meets rule 1.

## Exit (sell the whole position)
- Take profit: up 4% or more from our average cost.
- Stop loss: down 3% or more from our average cost.
- Time stop: held 7 trading days without hitting either.

## What we're measuring
Win rate, average win vs average loss, and return vs SPY buy-and-hold over the same days.
Graduation bar is in config.toml under `[graduation]`.
