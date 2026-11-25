from tradeagent import cli, db
from tradeagent.config import load_config
from tradeagent.report import metrics


def test_paper_round_trip(tmp_path, monkeypatch):
    dbfile = tmp_path / "t.db"
    monkeypatch.setattr(db, "DB_PATH", dbfile)
    assert cli.main(["mark", "--prices", '{"AAPL": 200}', "--benchmark", "500", "--day", "2026-01-01"]) == 0
    assert cli.main(["order", "--symbol", "AAPL", "--side", "buy", "--dollars", "20", "--price", "200",
                     "--strategy", "pullback", "--reason", "test"]) == 0
    assert cli.main(["order", "--symbol", "AAPL", "--side", "buy", "--dollars", "50", "--price", "200",
                     "--strategy", "pullback", "--reason", "too big"]) == 2
    assert cli.main(["order", "--symbol", "AAPL", "--side", "sell", "--all", "--price", "210",
                     "--strategy", "pullback", "--reason", "take profit"]) == 0
    conn = db.connect(dbfile)
    cfg = load_config()
    assert db.positions(conn) == {}
    assert db.cash(conn, cfg) == 101.0
    m = metrics(conn, cfg)
    assert m["closed_trades"] == 1 and m["win_rate_pct"] == 100.0 and m["realized_pnl"] == 1.0
    assert conn.execute("SELECT COUNT(*) FROM rejections").fetchone()[0] == 1
    assert m["ready_for_real_money"] is False
