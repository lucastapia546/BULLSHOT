"""Pure guardrail checks. No I/O: callers pass in the current account state."""
from __future__ import annotations

from dataclasses import dataclass

from .config import Config


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str            # "buy" or "sell"
    dollars: float       # notional value of the order
    price: float         # latest quote per share
    asset_type: str = "stock"


@dataclass(frozen=True)
class AccountState:
    cash: float
    equity: float                 # cash + market value of positions
    day_start_equity: float
    open_symbols: frozenset[str]
    position_value: dict[str, float]  # symbol -> current market value
    orders_today: int


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    reasons: tuple[str, ...]

    def __bool__(self) -> bool:
        return self.allowed


def check_order(order: OrderRequest, state: AccountState, cfg: Config) -> Verdict:
    reasons: list[str] = []
    symbol = order.symbol.upper().strip()
    side = order.side.lower().strip()

    if not symbol.isalpha() or len(symbol) > 5:
        reasons.append(f"'{order.symbol}' is not a plain stock ticker")
    if side not in ("buy", "sell"):
        reasons.append(f"side must be buy or sell, got '{order.side}'")
    if order.asset_type.lower() not in cfg.asset_types:
        reasons.append(f"asset type '{order.asset_type}' is not allowed (only {', '.join(cfg.asset_types)})")
    if symbol in cfg.blocked_symbols:
        reasons.append(f"{symbol} is on the blocked list")
    if order.dollars <= 0:
        reasons.append("order amount must be positive")
    if order.price <= 0:
        reasons.append("need a valid current price")
    elif order.price < cfg.min_price:
        reasons.append(f"price ${order.price:.2f} is below the ${cfg.min_price:.2f} minimum")
    if order.dollars > cfg.max_order_dollars:
        reasons.append(f"${order.dollars:.2f} is over the ${cfg.max_order_dollars:.2f} per-order cap")
    if state.orders_today >= cfg.max_orders_per_day:
        reasons.append(f"already {state.orders_today} orders today (max {cfg.max_orders_per_day})")

    if state.day_start_equity > 0:
        loss_pct = (state.day_start_equity - state.equity) / state.day_start_equity * 100
        if loss_pct >= cfg.daily_loss_stop_pct and side == "buy":
            reasons.append(f"down {loss_pct:.1f}% today, daily loss stop is {cfg.daily_loss_stop_pct:.1f}%")

    if side == "buy":
        if symbol not in state.open_symbols and len(state.open_symbols) >= cfg.max_open_positions:
            reasons.append(f"already holding {len(state.open_symbols)} positions (max {cfg.max_open_positions})")
        if state.cash - order.dollars < cfg.min_cash_reserve:
            reasons.append(f"would leave ${state.cash - order.dollars:.2f} cash, reserve is ${cfg.min_cash_reserve:.2f}")
    elif side == "sell":
        held = state.position_value.get(symbol, 0.0)
        if held <= 0:
            reasons.append(f"no {symbol} position to sell (no short selling)")
        elif order.dollars > held * 1.02:
            reasons.append(f"selling ${order.dollars:.2f} but only ${held:.2f} of {symbol} is held")

    return Verdict(allowed=not reasons, reasons=tuple(reasons))
