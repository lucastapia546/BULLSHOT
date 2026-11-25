"""Command line the agent (and Lucas) use to run the paper account.

    python -m tradeagent.cli status
    python -m tradeagent.cli mark --prices '{"AAPL": 231.2, "MSFT": 410.5}' --benchmark 598.1
    python -m tradeagent.cli order --symbol AAPL --side buy --dollars 20 --price 231.2 \
        --strategy pullback --reason "Pulled back 3% to its 20-day average on light volume"
    python -m tradeagent.cli note --kind takeaway --text "..."
    python -m tradeagent.cli report
    python -m tradeagent.cli site          # JSON for the dashboard in site/
"""
from __future__ import annotations

import argparse
import json
import sys

from . import db
from .config import load_config
from .guardrails import OrderRequest, check_order


def cmd_status(args, cfg, conn):
    state = db.account_state(conn, cfg)
    pos = db.positions(conn)
    out = {
        "mode": cfg.mode,
        "cash": state.cash,
        "equity": state.equity,
        "day_start_equity": state.day_start_equity,
        "orders_today": state.orders_today,
        "orders_left_today": max(0, cfg.max_orders_per_day - state.orders_today),
        "positions": {s: {"shares": round(p["shares"], 6), "cost": round(p["cost"], 2),
                          "opened": p["opened"], "value": round(state.position_value[s], 2)} for s, p in pos.items()},
        "limits": {"max_order_dollars": cfg.max_order_dollars, "max_open_positions": cfg.max_open_positions,
                   "daily_loss_stop_pct": cfg.daily_loss_stop_pct, "min_cash_reserve": cfg.min_cash_reserve},
    }
    print(json.dumps(out, indent=2))


def cmd_mark(args, cfg, conn):
    prices = {k.upper(): float(v) for k, v in json.loads(args.prices).items()}
    state = db.record_mark(conn, cfg, prices, args.benchmark, args.day)
    print(json.dumps({"day": args.day or db.today(), "equity": state.equity, "cash": state.cash}))


def cmd_order(args, cfg, conn):
    if cfg.mode != "paper":
        print(f"mode is '{cfg.mode}'. v1 only supports paper trading; no order was recorded.", file=sys.stderr)
        return 1
    order = OrderRequest(symbol=args.symbol, side=args.side, dollars=args.dollars,
                         price=args.price, asset_type=args.asset_type)
    state = db.account_state(conn, cfg, {args.symbol.upper(): args.price})
    if args.side == "sell" and args.all:
        order = OrderRequest(order.symbol, "sell", round(state.position_value.get(order.symbol.upper(), 0.0), 2),
                             order.price, order.asset_type)
    verdict = check_order(order, state, cfg)
    if not verdict:
        db.record_rejection(conn, symbol=order.symbol, side=order.side, dollars=order.dollars, price=order.price,
                            strategy=args.strategy, reason=args.reason, blocked_by=verdict.reasons)
        print(json.dumps({"filled": False, "blocked_by": list(verdict.reasons)}, indent=2))
        return 2
    shares = None
    if args.side == "sell" and args.all:
        shares = db.positions(conn)[order.symbol.upper()]["shares"]
    trade_id = db.record_trade(conn, mode="paper", symbol=order.symbol, side=order.side, dollars=order.dollars,
                               price=order.price, strategy=args.strategy, reason=args.reason, shares=shares)
    print(json.dumps({"filled": True, "paper_trade_id": trade_id, "symbol": order.symbol.upper(),
                      "side": order.side, "dollars": order.dollars, "price": order.price}, indent=2))
    return 0


def cmd_note(args, cfg, conn):
    db.add_note(conn, args.kind, args.text, args.day)
    print("saved")


def cmd_report(args, cfg, conn):
    from .report import write_report
    path = write_report(conn, cfg, args.out)
    print(f"wrote {path}")


def cmd_site(args, cfg, conn):
    from .site_data import write
    path = write(conn, cfg, args.out, sample=args.sample)
    print(f"wrote {path}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="tradeagent")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    m = sub.add_parser("mark", help="record end-of-day prices for holdings and the SPY benchmark")
    m.add_argument("--prices", required=True, help='JSON like {"AAPL": 231.2}')
    m.add_argument("--benchmark", type=float, help="SPY price")
    m.add_argument("--day")
    o = sub.add_parser("order", help="paper-trade an order after guardrail checks")
    o.add_argument("--symbol", required=True)
    o.add_argument("--side", required=True, choices=["buy", "sell"])
    o.add_argument("--dollars", type=float, default=0.0)
    o.add_argument("--all", action="store_true", help="sell the whole position")
    o.add_argument("--price", type=float, required=True)
    o.add_argument("--asset-type", default="stock")
    o.add_argument("--strategy", required=True)
    o.add_argument("--reason", required=True)
    n = sub.add_parser("note")
    n.add_argument("--kind", default="takeaway", choices=["takeaway", "plan", "lesson"])
    n.add_argument("--text", required=True)
    n.add_argument("--day")
    r = sub.add_parser("report")
    r.add_argument("--out")
    st = sub.add_parser("site", help="export the ledger as JSON for the dashboard site")
    st.add_argument("--out")
    st.add_argument("--sample", action="store_true", help="flag the export as sample data")
    args = p.parse_args(argv)

    cfg = load_config()
    conn = db.connect()
    handler = {"status": cmd_status, "mark": cmd_mark, "order": cmd_order,
               "note": cmd_note, "report": cmd_report, "site": cmd_site}[args.cmd]
    return handler(args, cfg, conn) or 0


if __name__ == "__main__":
    sys.exit(main())
