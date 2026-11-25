import json

from tradeagent import cli, db
from tradeagent.config import load_config
from tradeagent.site_data import build


def test_site_export(tmp_path, monkeypatch):
    dbfile = tmp_path / "t.db"
    monkeypatch.setattr(db, "DB_PATH", dbfile)
    cli.main(["mark", "--prices", '{"AAPL": 200}', "--benchmark", "500", "--day", "2026-01-01"])
    cli.main(["order", "--symbol", "AAPL", "--side", "buy", "--dollars", "20", "--price", "200",
              "--strategy", "pullback", "--reason", "test"])
    cli.main(["order", "--symbol", "AAPL", "--side", "sell", "--all", "--price", "210",
              "--strategy", "pullback", "--reason", "take profit"])
    cli.main(["order", "--symbol", "MSFT", "--side", "buy", "--dollars", "20", "--price", "400",
              "--strategy", "pullback", "--reason", "test"])
    cli.main(["mark", "--prices", '{"MSFT": 420}', "--benchmark", "505", "--day", "2026-01-02"])
    out = tmp_path / "ledger.json"
    assert cli.main(["site", "--out", str(out)]) == 0
    d = json.loads(out.read_text())
    assert d["schema"] == 1 and d["sample"] is False and d["mode"] == "paper"
    syms = {s["symbol"]: s for s in d["symbols"]}
    assert syms["AAPL"]["realized_pnl"] == 1.0 and syms["AAPL"]["wins"] == 1
    assert syms["MSFT"]["open_pnl"] == 1.0
    assert [p["symbol"] for p in d["positions"]] == ["MSFT"]
    assert d["curve"][-1]["spy_index"] == 101.0
    assert d["trades"][0]["symbol"] == "MSFT"  # newest first
    assert d["summary"]["day_change"] is not None


def test_empty_ledger_exports(tmp_path):
    conn = db.connect(tmp_path / "e.db")
    d = build(conn, load_config())
    assert d["curve"] == [] and d["trades"] == [] and d["summary"]["day_change"] is None
