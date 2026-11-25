"""SQLite storage and the paper-trading ledger."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

from .config import DB_PATH, Config
from .guardrails import AccountState

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    day TEXT NOT NULL,
    mode TEXT NOT NULL,           -- paper | propose | live
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,           -- buy | sell
    dollars REAL NOT NULL,
    price REAL NOT NULL,
    shares REAL NOT NULL,
    strategy TEXT NOT NULL,
    reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rejections (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    day TEXT NOT NULL,
    symbol TEXT, side TEXT, dollars REAL, price REAL,
    strategy TEXT, reason TEXT,
    blocked_by TEXT NOT NULL      -- JSON list of guardrail messages
);
CREATE TABLE IF NOT EXISTS marks (
    day TEXT PRIMARY KEY,
    prices TEXT NOT NULL,         -- JSON {symbol: price}
    benchmark REAL,               -- SPY close that day
    equity REAL NOT NULL,
    cash REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    kind TEXT NOT NULL,           -- takeaway | plan | lesson
    text TEXT NOT NULL
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = Path(path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def today() -> str:
    return date.today().isoformat()


def positions(conn: sqlite3.Connection) -> dict[str, dict]:
    """Average-cost positions from the paper ledger: {symbol: {shares, cost, opened}}."""
    pos: dict[str, dict] = {}
    for t in conn.execute("SELECT * FROM trades WHERE mode='paper' ORDER BY id"):
        p = pos.setdefault(t["symbol"], {"shares": 0.0, "cost": 0.0, "opened": t["day"]})
        if t["side"] == "buy":
            p["shares"] += t["shares"]
            p["cost"] += t["dollars"]
        else:
            avg = p["cost"] / p["shares"] if p["shares"] else 0.0
            p["shares"] -= t["shares"]
            p["cost"] -= avg * t["shares"]
        if p["shares"] <= 1e-5:  # fractional-share dust left by rounding
            pos.pop(t["symbol"])
    return pos


def cash(conn: sqlite3.Connection, cfg: Config) -> float:
    c = cfg.starting_capital
    for t in conn.execute("SELECT side, dollars FROM trades WHERE mode='paper'"):
        c += -t["dollars"] if t["side"] == "buy" else t["dollars"]
    return round(c, 2)


def latest_prices(conn: sqlite3.Connection) -> dict[str, float]:
    row = conn.execute("SELECT prices FROM marks ORDER BY day DESC LIMIT 1").fetchone()
    return json.loads(row["prices"]) if row else {}


def account_state(conn: sqlite3.Connection, cfg: Config, prices: dict[str, float] | None = None) -> AccountState:
    prices = {**latest_prices(conn), **(prices or {})}
    pos = positions(conn)
    value = {s: p["shares"] * prices.get(s, p["cost"] / p["shares"]) for s, p in pos.items()}
    c = cash(conn, cfg)
    equity = c + sum(value.values())
    prev = conn.execute("SELECT equity FROM marks WHERE day < ? ORDER BY day DESC LIMIT 1", (today(),)).fetchone()
    orders_today = conn.execute(
        "SELECT COUNT(*) FROM trades WHERE day=? AND mode='paper'", (today(),)).fetchone()[0]
    return AccountState(
        cash=c,
        equity=round(equity, 2),
        day_start_equity=prev["equity"] if prev else cfg.starting_capital,
        open_symbols=frozenset(pos),
        position_value=value,
        orders_today=orders_today,
    )


def record_trade(conn, *, mode, symbol, side, dollars, price, strategy, reason, shares=None) -> int:
    now = datetime.now().isoformat(timespec="seconds")
    cur = conn.execute(
        "INSERT INTO trades (ts, day, mode, symbol, side, dollars, price, shares, strategy, reason)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (now, today(), mode, symbol.upper(), side, round(dollars, 2), price, shares if shares is not None else dollars / price, strategy, reason))
    conn.commit()
    return cur.lastrowid


def record_rejection(conn, *, symbol, side, dollars, price, strategy, reason, blocked_by) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO rejections (ts, day, symbol, side, dollars, price, strategy, reason, blocked_by)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (now, today(), symbol.upper(), side, dollars, price, strategy, reason, json.dumps(list(blocked_by))))
    conn.commit()


def record_mark(conn, cfg: Config, prices: dict[str, float], benchmark: float | None, day: str | None = None) -> AccountState:
    state = account_state(conn, cfg, prices)
    merged = {**latest_prices(conn), **prices}
    conn.execute(
        "INSERT OR REPLACE INTO marks (day, prices, benchmark, equity, cash) VALUES (?,?,?,?,?)",
        (day or today(), json.dumps(merged), benchmark, state.equity, state.cash))
    conn.commit()
    return state


def add_note(conn, kind: str, text: str, day: str | None = None) -> None:
    conn.execute("INSERT INTO notes (day, kind, text) VALUES (?,?,?)", (day or today(), kind, text))
    conn.commit()
