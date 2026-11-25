import pytest

from tradeagent.config import load_config
from tradeagent.guardrails import AccountState, OrderRequest, check_order


@pytest.fixture
def cfg():
    return load_config()


def state(**kw):
    base = dict(cash=100.0, equity=100.0, day_start_equity=100.0, open_symbols=frozenset(),
                position_value={}, orders_today=0)
    base.update(kw)
    return AccountState(**base)


def test_config_ships_in_paper_mode(cfg):
    assert cfg.mode == "paper"


def test_small_buy_allowed(cfg):
    assert check_order(OrderRequest("AAPL", "buy", 20, 230), state(), cfg)


@pytest.mark.parametrize("order,expect", [
    (OrderRequest("AAPL", "buy", 30, 230), "per-order cap"),
    (OrderRequest("AAPL", "buy", 20, 3), "below"),
    (OrderRequest("AAPL", "buy", 20, 230, asset_type="option"), "asset type"),
    (OrderRequest("AAPL240119C00200000", "buy", 20, 2), "ticker"),
    (OrderRequest("AAPL", "short", 20, 230), "side"),
    (OrderRequest("AAPL", "sell", 20, 230), "no AAPL position"),
])
def test_blocked_orders(cfg, order, expect):
    v = check_order(order, state(), cfg)
    assert not v and any(expect in r for r in v.reasons)


def test_position_limit(cfg):
    s = state(open_symbols=frozenset({"A", "B", "C", "D"}))
    assert not check_order(OrderRequest("MSFT", "buy", 10, 400), s, cfg)
    # adding to an existing holding is still fine
    assert check_order(OrderRequest("A", "buy", 10, 50), s, cfg)


def test_cash_reserve(cfg):
    assert not check_order(OrderRequest("AAPL", "buy", 20, 230), state(cash=25.0), cfg)


def test_daily_order_limit(cfg):
    assert not check_order(OrderRequest("AAPL", "buy", 10, 230), state(orders_today=3), cfg)


def test_daily_loss_stop_blocks_buys_not_sells(cfg):
    s = state(equity=94.0, open_symbols=frozenset({"AAPL"}), position_value={"AAPL": 20.0})
    assert not check_order(OrderRequest("MSFT", "buy", 10, 400), s, cfg)
    assert check_order(OrderRequest("AAPL", "sell", 20, 230), s, cfg)


def test_cannot_oversell(cfg):
    s = state(open_symbols=frozenset({"AAPL"}), position_value={"AAPL": 10.0})
    assert not check_order(OrderRequest("AAPL", "sell", 20, 230), s, cfg)
