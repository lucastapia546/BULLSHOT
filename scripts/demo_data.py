"""Fill a throwaway database with made-up paper trades so you can preview the report.

    TRADEAGENT_DB=data/demo.db python3 scripts/demo_data.py && TRADEAGENT_DB=data/demo.db python3 -m tradeagent.cli report --out data/demo_report.html
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tradeagent import db  # noqa: E402
from tradeagent.config import load_config  # noqa: E402

random.seed(7)
cfg = load_config()
conn = db.connect()
conn.executescript("DELETE FROM trades; DELETE FROM marks; DELETE FROM notes; DELETE FROM rejections;")
prices = {"AAPL": 228.0, "MSFT": 415.0, "NVDA": 180.0, "AMZN": 215.0, "GOOGL": 172.0, "META": 590.0,
          "JPM": 245.0, "QQQ": 505.0, "XLE": 92.0}
spy = 598.0
day = date(2026, 10, 23)
for n in range(23):
    while day.weekday() >= 5:
        day += timedelta(days=1)
    d = day.isoformat()
    for s in prices:
        prices[s] = round(prices[s] * (1 + random.gauss(0.0008, 0.015)), 2)
    spy = round(spy * (1 + random.gauss(0.0005, 0.008)), 2)
    if n % 3 == 0:
        held = db.positions(conn)
        for s in random.sample([s for s in prices if s not in held], 2):
            db.record_trade(conn, mode="paper", symbol=s, side="buy", dollars=20, price=prices[s],
                            strategy="pullback", reason=f"Pulled back 3.4% from 10-day high, above 50-day avg")
    elif n % 3 == 2:
        for s, p in list(db.positions(conn).items()):
            value = round(p["shares"] * prices[s], 2)
            db.record_trade(conn, mode="paper", symbol=s, side="sell", dollars=value, price=prices[s],
                            strategy="pullback", reason="Hit take-profit" if value > p["cost"] else "Hit stop-loss",
                            shares=p["shares"])
    conn.execute("UPDATE trades SET day=? WHERE day=?", (d, db.today()))
    db.record_mark(conn, cfg, dict(prices), spy, d)
    day += timedelta(days=1)
db.record_rejection(conn, symbol="NVDA", side="buy", dollars=40, price=prices["NVDA"], strategy="pullback",
                    reason="demo", blocked_by=["$40.00 is over the $25.00 per-order cap"])
db.add_note(conn, "takeaway", "Two of three stop-losses came within a day of entry. Entries may be too early; "
            "consider waiting for a green day after the pullback.", day.isoformat())
db.add_note(conn, "takeaway", "Take-profits are paying more than stop-losses cost, so the plan can survive a few losing streaks.",
            day.isoformat())
print("demo data written")
