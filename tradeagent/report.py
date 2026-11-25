"""Performance metrics and a self-contained HTML report (no extra dependencies)."""
from __future__ import annotations

import html
import json
from collections import defaultdict
from pathlib import Path

from . import db
from .config import ROOT, Config


def round_trips(conn) -> list[dict]:
    """Realized P&L for every paper sell, using average cost."""
    pos: dict[str, dict] = defaultdict(lambda: {"shares": 0.0, "cost": 0.0, "strategy": ""})
    closed = []
    for t in conn.execute("SELECT * FROM trades WHERE mode='paper' ORDER BY id"):
        p = pos[t["symbol"]]
        if t["side"] == "buy":
            p["shares"] += t["shares"]
            p["cost"] += t["dollars"]
            p["strategy"] = t["strategy"]
        elif p["shares"] > 0:
            avg = p["cost"] / p["shares"]
            basis = avg * t["shares"]
            closed.append({"day": t["day"], "symbol": t["symbol"], "strategy": p["strategy"] or t["strategy"],
                           "pnl": round(t["dollars"] - basis, 2),
                           "pnl_pct": round((t["dollars"] / basis - 1) * 100, 2) if basis else 0.0})
            p["shares"] -= t["shares"]
            p["cost"] -= basis
    return closed


def metrics(conn, cfg: Config) -> dict:
    marks = [dict(r) for r in conn.execute("SELECT day, equity, benchmark FROM marks ORDER BY day")]
    closed = round_trips(conn)
    state = db.account_state(conn, cfg)
    total_return = (state.equity / cfg.starting_capital - 1) * 100

    bench = [m for m in marks if m["benchmark"]]
    bench_return = (bench[-1]["benchmark"] / bench[0]["benchmark"] - 1) * 100 if len(bench) >= 2 else None

    peak, max_dd = cfg.starting_capital, 0.0
    for m in marks:
        peak = max(peak, m["equity"])
        max_dd = max(max_dd, (peak - m["equity"]) / peak * 100)

    wins = [c for c in closed if c["pnl"] > 0]
    by_strategy: dict[str, dict] = {}
    for c in closed:
        s = by_strategy.setdefault(c["strategy"], {"trades": 0, "wins": 0, "pnl": 0.0})
        s["trades"] += 1
        s["wins"] += c["pnl"] > 0
        s["pnl"] = round(s["pnl"] + c["pnl"], 2)

    g = cfg.graduation
    checks = [
        ("Trading days", len(marks), g.get("min_trading_days", 20), len(marks) >= g.get("min_trading_days", 20)),
        ("Closed trades", len(closed), g.get("min_closed_trades", 15), len(closed) >= g.get("min_closed_trades", 15)),
        ("Total return %", round(total_return, 2), g.get("min_total_return_pct", 2.0),
         total_return >= g.get("min_total_return_pct", 2.0)),
        ("Max drawdown %", round(max_dd, 2), g.get("max_drawdown_pct", 8.0), max_dd <= g.get("max_drawdown_pct", 8.0)),
    ]
    if g.get("must_beat_benchmark", True):
        checks.append(("Beat SPY by (pts)", None if bench_return is None else round(total_return - bench_return, 2),
                       0, bench_return is not None and total_return > bench_return))
    return {
        "equity": state.equity, "cash": state.cash, "total_return_pct": round(total_return, 2),
        "benchmark_return_pct": None if bench_return is None else round(bench_return, 2),
        "max_drawdown_pct": round(max_dd, 2), "closed_trades": len(closed),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "realized_pnl": round(sum(c["pnl"] for c in closed), 2),
        "by_strategy": by_strategy, "graduation": checks,
        "ready_for_real_money": all(c[3] for c in checks), "marks": marks,
    }


def _money(x):
    return "n/a" if x is None else f"${x:,.2f}"


def _pct(x):
    return "n/a" if x is None else f"{x:+.2f}%"


def write_report(conn, cfg: Config, out: str | None = None) -> Path:
    m = metrics(conn, cfg)
    trades = [dict(r) for r in conn.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 200")]
    rejections = [dict(r) for r in conn.execute("SELECT * FROM rejections ORDER BY id DESC LIMIT 50")]
    notes = [dict(r) for r in conn.execute("SELECT * FROM notes ORDER BY day DESC, id DESC LIMIT 30")]
    e = html.escape

    # Both lines indexed to 100 on day one so they share one axis.
    series = []
    first_b = next((x["benchmark"] for x in m["marks"] if x["benchmark"]), None)
    for x in m["marks"]:
        series.append({"day": x["day"], "acct": round(x["equity"] / cfg.starting_capital * 100, 2),
                       "spy": round(x["benchmark"] / first_b * 100, 2) if first_b and x["benchmark"] else None})

    grad_rows = "".join(
        f"<tr><td>{e(name)}</td><td class=num>{'n/a' if val is None else val}</td>"
        f"<td class=num>{'≤ ' if 'drawdown' in name else '≥ ' if 'Beat' not in name else '> '}{target}</td>"
        f"<td>{'✓ met' if ok else '✗ not yet'}</td></tr>"
        for name, val, target, ok in m["graduation"])
    strat_rows = "".join(
        f"<tr><td>{e(s)}</td><td class=num>{v['trades']}</td><td class=num>{v['wins'] / v['trades'] * 100:.0f}%</td>"
        f"<td class=num>{_money(v['pnl'])}</td></tr>" for s, v in m["by_strategy"].items()) or \
        "<tr><td colspan=4 class=muted>No closed trades yet</td></tr>"
    trade_rows = "".join(
        f"<tr><td>{e(t['day'])}</td><td>{e(t['side'])}</td><td><b>{e(t['symbol'])}</b></td>"
        f"<td class=num>{_money(t['dollars'])}</td><td class=num>{_money(t['price'])}</td>"
        f"<td>{e(t['strategy'])}</td><td>{e(t['reason'])}</td></tr>" for t in trades) or \
        "<tr><td colspan=7 class=muted>No trades yet</td></tr>"
    rej_rows = "".join(
        f"<tr><td>{e(r['day'])}</td><td>{e(r['side'] or '')} {e(r['symbol'] or '')}</td>"
        f"<td class=num>{_money(r['dollars'])}</td><td>{e('; '.join(json.loads(r['blocked_by'])))}</td></tr>"
        for r in rejections) or "<tr><td colspan=4 class=muted>Nothing blocked</td></tr>"
    note_items = "".join(
        f"<li><span class=tag>{e(n['kind'])}</span> <span class=muted>{e(n['day'])}</span><br>{e(n['text'])}</li>"
        for n in notes) or "<li class=muted>No takeaways yet. The daily run writes these.</li>"

    ready = m["ready_for_real_money"]
    page = TEMPLATE.format(
        mode=e(cfg.mode.upper()), equity=_money(m["equity"]), cash=_money(m["cash"]),
        ret=_pct(m["total_return_pct"]), spy=_pct(m["benchmark_return_pct"]),
        dd=f"{m['max_drawdown_pct']:.2f}%", win="n/a" if m["win_rate_pct"] is None else f"{m['win_rate_pct']:.0f}%",
        closed=m["closed_trades"], realized=_money(m["realized_pnl"]),
        verdict=("Paper results clear every bar. Ask Lucas before any real money." if ready
                 else "Not ready for real money yet. Keep paper trading."),
        verdict_cls="good" if ready else "wait",
        grad_rows=grad_rows, strat_rows=strat_rows, trade_rows=trade_rows, rej_rows=rej_rows,
        notes=note_items, series=json.dumps(series))
    path = Path(out) if out else ROOT / "data" / "report.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page)
    return path


TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paper trading report</title>
<style>
.viz-root {{ color-scheme: light; --surface-1:#ffffff; --surface-2:#f6f6f4; --border:#e4e4e0;
  --text-primary:#191919; --text-secondary:#666666; --series-1:#257de0; --series-2:#f47230;
  --good:#008a17; --wait:#b26b00; }}
@media (prefers-color-scheme: dark) {{ :root:where(:not([data-theme="light"])) .viz-root {{ color-scheme: dark;
  --surface-1:#191919; --surface-2:#222220; --border:#333331; --text-primary:#efefef; --text-secondary:#9c9c9c;
  --series-1:#338ced; --series-2:#e76624; --good:#0aac23; --wait:#d28e05; }} }}
* {{ box-sizing:border-box }}
body {{ margin:0; font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif }}
.viz-root {{ background:var(--surface-2); color:var(--text-primary); min-height:100vh; padding:28px }}
main {{ max-width:1080px; margin:0 auto }}
h1 {{ font-size:24px; margin:0 0 4px }} h2 {{ font-size:16px; margin:0 0 12px }}
.muted {{ color:var(--text-secondary) }}
.badge {{ display:inline-block; font-size:12px; font-weight:600; padding:2px 8px; border-radius:99px;
  border:1px solid var(--border); margin-left:8px; vertical-align:middle }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin:20px 0 }}
.tile, .card {{ background:var(--surface-1); border:1px solid var(--border); border-radius:12px; padding:16px }}
.tile .k {{ font-size:12px; color:var(--text-secondary) }} .tile .v {{ font-size:22px; font-weight:600; font-variant-numeric:tabular-nums }}
.card {{ margin-bottom:16px }}
.verdict {{ font-weight:600 }} .verdict.good {{ color:var(--good) }} .verdict.wait {{ color:var(--wait) }}
.grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px }} @media (max-width:760px) {{ .grid2 {{ grid-template-columns:1fr }} }}
table {{ width:100%; border-collapse:collapse; font-size:14px }}
th, td {{ text-align:left; padding:6px 8px; border-bottom:1px solid var(--border); vertical-align:top }}
th {{ font-weight:600; color:var(--text-secondary); font-size:12px }}
.num {{ text-align:right; font-variant-numeric:tabular-nums }}
.tag {{ font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:var(--text-secondary) }}
ul.notes {{ list-style:none; padding:0; margin:0 }} ul.notes li {{ padding:8px 0; border-bottom:1px solid var(--border) }}
.legend {{ display:flex; gap:16px; font-size:13px; margin-bottom:8px }}
.legend i {{ display:inline-block; width:14px; height:2px; vertical-align:middle; margin-right:6px }}
#chart {{ position:relative }} #chart svg {{ width:100%; height:260px; display:block }}
#tip {{ position:absolute; pointer-events:none; background:var(--surface-1); border:1px solid var(--border);
  border-radius:8px; padding:6px 10px; font-size:13px; display:none; white-space:nowrap; box-shadow:0 2px 8px rgba(0,0,0,.12) }}
</style></head>
<body><div class="viz-root"><main>
<h1>Paper trading report <span class="badge">{mode} MODE</span></h1>
<div class="muted">Simulated $100 account. No real orders are placed in this mode.</div>

<div class="tiles">
 <div class="tile"><div class="k">Equity</div><div class="v">{equity}</div></div>
 <div class="tile"><div class="k">Return</div><div class="v">{ret}</div></div>
 <div class="tile"><div class="k">SPY same period</div><div class="v">{spy}</div></div>
 <div class="tile"><div class="k">Win rate ({closed} closed)</div><div class="v">{win}</div></div>
 <div class="tile"><div class="k">Max drawdown</div><div class="v">{dd}</div></div>
 <div class="tile"><div class="k">Cash</div><div class="v">{cash}</div></div>
</div>

<div class="card">
 <h2>Account vs SPY, indexed to 100</h2>
 <div class="legend"><span><i style="background:var(--series-1)"></i>Paper account</span>
  <span><i style="background:var(--series-2)"></i>SPY buy-and-hold</span></div>
 <div id="chart"><svg id="svg" role="img" aria-label="Paper account value versus SPY, both indexed to 100"></svg><div id="tip"></div></div>
</div>

<div class="grid2">
 <div class="card"><h2>Ready for real money?</h2><p class="verdict {verdict_cls}">{verdict}</p>
  <table><tr><th>Check</th><th class=num>Now</th><th class=num>Needed</th><th>Status</th></tr>{grad_rows}</table></div>
 <div class="card"><h2>Takeaways</h2><ul class="notes">{notes}</ul></div>
</div>

<div class="card"><h2>By strategy</h2>
 <table><tr><th>Strategy</th><th class=num>Closed</th><th class=num>Win rate</th><th class=num>Realized P&amp;L</th></tr>{strat_rows}</table>
 <p class="muted">Realized P&amp;L: {realized}</p></div>

<div class="card"><h2>Trades</h2>
 <table><tr><th>Day</th><th>Side</th><th>Symbol</th><th class=num>Amount</th><th class=num>Price</th><th>Strategy</th><th>Why</th></tr>{trade_rows}</table></div>

<div class="card"><h2>Blocked by guardrails</h2>
 <table><tr><th>Day</th><th>Order</th><th class=num>Amount</th><th>Why it was blocked</th></tr>{rej_rows}</table></div>
</main></div>
<script>
const data = {series};
const svg = document.getElementById('svg'), tip = document.getElementById('tip');
function draw() {{
  const W = svg.clientWidth, H = 260, L = 44, R = 16, T = 12, B = 28;
  svg.setAttribute('viewBox', `0 0 ${{W}} ${{H}}`);
  if (data.length < 2) {{ svg.innerHTML = `<text x="${{W/2}}" y="${{H/2}}" text-anchor="middle" fill="var(--text-secondary)">The chart fills in after two daily marks.</text>`; return; }}
  const vals = data.flatMap(d => [d.acct, d.spy]).filter(v => v != null);
  let lo = Math.min(...vals, 100), hi = Math.max(...vals, 100); const pad = (hi - lo) * 0.1 || 1; lo -= pad; hi += pad;
  const x = i => L + i * (W - L - R) / (data.length - 1), y = v => T + (hi - v) * (H - T - B) / (hi - lo);
  const path = k => data.map((d, i) => d[k] == null ? '' : `${{i && data[i-1][k] != null ? 'L' : 'M'}}${{x(i).toFixed(1)}},${{y(d[k]).toFixed(1)}}`).join('');
  let g = '';
  for (let k = 0; k <= 4; k++) {{ const v = lo + (hi - lo) * k / 4;
    g += `<line x1="${{L}}" x2="${{W-R}}" y1="${{y(v)}}" y2="${{y(v)}}" stroke="var(--border)"/>`+
         `<text x="${{L-6}}" y="${{y(v)+4}}" text-anchor="end" font-size="11" fill="var(--text-secondary)">${{v.toFixed(1)}}</text>`; }}
  [0, data.length - 1].forEach(i => g += `<text x="${{x(i)}}" y="${{H-8}}" text-anchor="${{i ? 'end' : 'start'}}" font-size="11" fill="var(--text-secondary)">${{data[i].day}}</text>`);
  g += `<path d="${{path('spy')}}" fill="none" stroke="var(--series-2)" stroke-width="2" stroke-linejoin="round"/>`;
  g += `<path d="${{path('acct')}}" fill="none" stroke="var(--series-1)" stroke-width="2" stroke-linejoin="round"/>`;
  g += `<line id="xh" y1="${{T}}" y2="${{H-B}}" stroke="var(--text-secondary)" stroke-dasharray="3 3" visibility="hidden"/>`;
  g += `<circle id="d1" r="4" fill="var(--series-1)" stroke="var(--surface-1)" stroke-width="2" visibility="hidden"/>`;
  g += `<circle id="d2" r="4" fill="var(--series-2)" stroke="var(--surface-1)" stroke-width="2" visibility="hidden"/>`;
  g += `<rect x="${{L}}" y="0" width="${{W-L-R}}" height="${{H}}" fill="transparent" id="hit"/>`;
  svg.innerHTML = g;
  const hit = svg.querySelector('#hit'), xh = svg.querySelector('#xh'), d1 = svg.querySelector('#d1'), d2 = svg.querySelector('#d2');
  hit.addEventListener('mousemove', ev => {{
    const r = svg.getBoundingClientRect(), px = ev.clientX - r.left;
    const i = Math.max(0, Math.min(data.length - 1, Math.round((px - L) / (W - L - R) * (data.length - 1)))), d = data[i];
    [xh, d1, d2].forEach(n => n.setAttribute('visibility', 'visible'));
    xh.setAttribute('x1', x(i)); xh.setAttribute('x2', x(i));
    d1.setAttribute('cx', x(i)); d1.setAttribute('cy', y(d.acct));
    if (d.spy != null) {{ d2.setAttribute('cx', x(i)); d2.setAttribute('cy', y(d.spy)); }} else d2.setAttribute('visibility', 'hidden');
    tip.innerHTML = `<b>${{d.day}}</b><br>Paper account: ${{d.acct.toFixed(2)}}<br>SPY: ${{d.spy == null ? 'n/a' : d.spy.toFixed(2)}}`;
    tip.style.display = 'block'; tip.style.left = Math.min(px + 12, W - 170) + 'px'; tip.style.top = '8px';
  }});
  hit.addEventListener('mouseleave', () => {{ tip.style.display = 'none'; [xh, d1, d2].forEach(n => n.setAttribute('visibility', 'hidden')); }});
}}
draw(); addEventListener('resize', draw);
</script></body></html>
"""
