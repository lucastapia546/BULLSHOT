"""Export the paper ledger as one JSON file for the dashboard site in site/.

The site is static: it only ever reads this JSON, so it never touches Robinhood or the database.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .config import ROOT, Config
from .report import metrics, round_trips

SCHEMA_VERSION = 1


def build(conn, cfg: Config, *, sample: bool = False) -> dict:
    m = metrics(conn, cfg)
    state = db.account_state(conn, cfg)
    prices = db.latest_prices(conn)
    trades = [dict(r) for r in conn.execute("SELECT * FROM trades WHERE mode='paper' ORDER BY id")]
    closed = round_trips(conn)

    first_b = next((x["benchmark"] for x in m["marks"] if x["benchmark"]), None)
    curve = [{"day": x["day"], "equity": round(x["equity"], 2),
              "acct_index": round(x["equity"] / cfg.starting_capital * 100, 2),
              "spy_index": round(x["benchmark"] / first_b * 100, 2) if first_b and x["benchmark"] else None}
             for x in m["marks"]]

    positions = []
    for s, p in db.positions(conn).items():
        value = state.position_value[s]
        positions.append({"symbol": s, "shares": round(p["shares"], 6), "cost": round(p["cost"], 2),
                          "price": prices.get(s), "value": round(value, 2), "opened": p["opened"],
                          "pnl": round(value - p["cost"], 2),
                          "pnl_pct": round((value / p["cost"] - 1) * 100, 2) if p["cost"] else 0.0})

    symbols: dict[str, dict] = {}
    for t in trades:
        s = symbols.setdefault(t["symbol"], {"symbol": t["symbol"], "trades": 0, "traded_dollars": 0.0,
                                             "realized_pnl": 0.0, "wins": 0, "losses": 0, "open_pnl": None})
        s["trades"] += 1
        s["traded_dollars"] = round(s["traded_dollars"] + t["dollars"], 2)
    for c in closed:
        s = symbols[c["symbol"]]
        s["realized_pnl"] = round(s["realized_pnl"] + c["pnl"], 2)
        s["wins" if c["pnl"] > 0 else "losses"] += 1
    for p in positions:
        symbols[p["symbol"]]["open_pnl"] = p["pnl"]

    grad = []
    for name, value, target, ok in m["graduation"]:
        op = "<=" if "drawdown" in name.lower() else ">" if "beat" in name.lower() else ">="
        grad.append({"name": name, "value": value, "target": target, "op": op, "met": bool(ok)})

    summary = {k: v for k, v in m.items() if k not in ("marks", "graduation", "by_strategy")}
    summary["open_pnl"] = round(sum(p["pnl"] for p in positions), 2)
    summary["day_change"] = round(curve[-1]["equity"] - curve[-2]["equity"], 2) if len(curve) >= 2 else None

    return {
        "schema": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sample": sample,
        "mode": cfg.mode,
        "starting_capital": cfg.starting_capital,
        "limits": {"max_order_dollars": cfg.max_order_dollars, "max_open_positions": cfg.max_open_positions,
                   "max_orders_per_day": cfg.max_orders_per_day},
        "summary": summary,
        "graduation": grad,
        "by_strategy": m["by_strategy"],
        "curve": curve,
        "positions": positions,
        "symbols": sorted(symbols.values(), key=lambda s: -s["traded_dollars"]),
        "trades": trades[::-1],
        "closed": closed[::-1],
        "notes": [dict(r) for r in conn.execute("SELECT day, kind, text FROM notes ORDER BY day DESC, id DESC")],
        "rejections": [{**dict(r), "blocked_by": json.loads(r["blocked_by"])}
                       for r in conn.execute("SELECT day, symbol, side, dollars, blocked_by FROM rejections"
                                             " ORDER BY id DESC LIMIT 50")],
    }


def write(conn, cfg: Config, out: str | None = None, *, sample: bool = False) -> Path:
    path = Path(out) if out else ROOT / "site" / "data" / "ledger.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build(conn, cfg, sample=sample), indent=1))
    return path
