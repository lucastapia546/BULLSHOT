from __future__ import annotations

import os
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # Python 3.9/3.10 (e.g. the macOS system Python)
    import tomli as tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get("TRADEAGENT_CONFIG", ROOT / "config.toml"))
DB_PATH = Path(os.environ.get("TRADEAGENT_DB", ROOT / "data" / "trades.db"))

MODES = ("paper", "propose", "live")


@dataclass(frozen=True)
class Config:
    mode: str
    starting_capital: float
    max_order_dollars: float
    max_open_positions: int
    max_orders_per_day: int
    daily_loss_stop_pct: float
    min_cash_reserve: float
    asset_types: tuple[str, ...]
    min_price: float
    blocked_symbols: frozenset[str]
    server_name: str
    allowed_tools: frozenset[str]
    order_patterns: tuple[str, ...]
    graduation: dict = field(default_factory=dict)


def load_config(path: Path | None = None) -> Config:
    raw = tomllib.loads(Path(path or CONFIG_PATH).read_text())
    mode = raw.get("mode", "propose")
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    b, u, m = raw["budget"], raw["universe"], raw["mcp"]
    return Config(
        mode=mode,
        starting_capital=float(b["starting_capital"]),
        max_order_dollars=float(b["max_order_dollars"]),
        max_open_positions=int(b["max_open_positions"]),
        max_orders_per_day=int(b["max_orders_per_day"]),
        daily_loss_stop_pct=float(b["daily_loss_stop_pct"]),
        min_cash_reserve=float(b["min_cash_reserve"]),
        asset_types=tuple(a.lower() for a in u["asset_types"]),
        min_price=float(u["min_price"]),
        blocked_symbols=frozenset(s.upper() for s in u.get("blocked_symbols", [])),
        server_name=m["server_name"],
        allowed_tools=frozenset(m["allowed_tools"]),
        order_patterns=tuple(p.lower() for p in m.get("order_patterns", [])),
        graduation=dict(raw.get("graduation", {})),
    )
