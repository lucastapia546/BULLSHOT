/* BULLSHOT dashboard. Reads one JSON export of the paper ledger and draws everything client-side. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const NS = "http://www.w3.org/2000/svg";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (x, sign = false) => x == null ? "n/a" : (sign && x > 0 ? "+" : x < 0 ? "−" : "") + "$" + Math.abs(x).toFixed(2);
  const pct = (x) => x == null ? "n/a" : (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x).toFixed(2) + "%";
  const tone = (x) => x == null || Math.abs(x) < 0.005 ? "flat" : x > 0 ? "gain" : "loss";
  const fmtDay = (d) => new Date(d + "T12:00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const el = (tag, attrs = {}, parent) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  };

  // The live export wins; the sample only shows until the first real run has been published.
  const SOURCES = ["data/ledger.json", "data/sample.json"];
  async function load() {
    for (const src of SOURCES) {
      try {
        const r = await fetch(src + "?t=" + Date.now(), { cache: "no-store" });
        if (r.ok) return await r.json();
      } catch (_) { /* try the next source */ }
    }
    throw new Error("no data");
  }

  let D = null;
  function render(data) {
    D = data;
    $("sample-banner").hidden = !data.sample;
    $("mode").textContent = (data.mode || "paper").toUpperCase();
    const gen = new Date(data.generated_at);
    const lastDay = data.curve.length ? data.curve[data.curve.length - 1].day : null;
    $("updated").textContent = lastDay
      ? `Last market day ${fmtDay(lastDay)} · updated ${gen.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}`
      : "Waiting for the first paper run";
    hero(data); road(data); tiles(data); map(data); chart(data); positions(data); notes(data); tape(data); blocks(data);
  }

  function countUp(node, to, fmt, ms = 1100) {
    const t0 = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - k, 3);
      node.textContent = fmt(to * e);
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  function hero(d) {
    const s = d.summary;
    $("start-cap").textContent = money(d.starting_capital);
    countUp($("equity"), s.equity, (v) => "$" + v.toFixed(2));
    const ret = $("ret");
    ret.textContent = pct(s.total_return_pct);
    ret.className = "chip " + tone(s.total_return_pct);
    $("spy").textContent = pct(s.benchmark_return_pct);
    const dc = $("daychg");
    dc.textContent = s.day_change == null ? "n/a" : money(s.day_change, true);
    dc.className = "mono " + tone(s.day_change);
    if (s.benchmark_return_pct == null) {
      $("vs").innerHTML = "SPY comparison starts after two daily marks.";
    } else {
      const gap = s.total_return_pct - s.benchmark_return_pct;
      $("vs").innerHTML = Math.abs(gap) < 0.05
        ? "Neck and neck with just holding SPY."
        : gap > 0 ? `Beating plain SPY by <b class="gain">${gap.toFixed(2)} pts</b>.`
                  : `Trailing plain SPY by <b class="loss">${Math.abs(gap).toFixed(2)} pts</b>. Holding the index would have done better so far.`;
    }
  }

  function road(d) {
    const list = $("road");
    list.innerHTML = "";
    let met = 0;
    for (const g of d.graduation) {
      met += g.met;
      let frac, shown;
      const v = g.value;
      if (g.op === "<=") { frac = g.met ? 1 : v ? Math.min(1, g.target / v) : 0; shown = `${v ?? "n/a"}% / max ${g.target}%`; }
      else if (g.op === ">") { frac = v == null ? 0 : v > 0 ? 1 : 0; shown = v == null ? "n/a" : `${v > 0 ? "+" : ""}${v} pts`; }
      else { frac = v == null ? 0 : Math.max(0, Math.min(1, v / g.target)); shown = `${v ?? "n/a"} / ${g.target}`; }
      const li = document.createElement("li");
      if (g.met) li.className = "met";
      li.innerHTML = `<span>${g.met ? "✓ " : ""}${esc(g.name)}</span><span class="v">${esc(shown)}</span><span class="bar"><i style="width:0"></i></span>`;
      list.appendChild(li);
      requestAnimationFrame(() => requestAnimationFrame(() => { li.querySelector("i").style.width = (frac * 100).toFixed(1) + "%"; }));
    }
    $("road-count").textContent = `${met}/${d.graduation.length} met`;
    const v = $("verdict");
    v.textContent = d.summary.ready_for_real_money
      ? "Every bar is cleared. Lucas decides whether real money comes next."
      : "Not ready for real money. The agent keeps paper trading until every bar is met.";
    v.className = "verdict" + (d.summary.ready_for_real_money ? " ready" : "");
  }

  function tiles(d) {
    const s = d.summary;
    const items = [
      ["Win rate", s.win_rate_pct == null ? "n/a" : s.win_rate_pct.toFixed(0) + "%", `${s.closed_trades} closed trades`, ""],
      ["Realized P&L", money(s.realized_pnl, true), "from closed trades", tone(s.realized_pnl)],
      ["Open P&L", money(s.open_pnl, true), `${d.positions.length} of ${d.limits.max_open_positions} slots used`, tone(s.open_pnl)],
      ["Max drawdown", s.max_drawdown_pct.toFixed(2) + "%", "worst peak-to-dip", ""],
      ["Cash", money(s.cash), "uninvested", ""],
      ["Trades", String(d.trades.length), `${d.symbols.length} different tickers`, ""],
    ];
    $("tiles").innerHTML = items.map(([k, v, sub, t]) =>
      `<div class="tile"><div class="k">${k}</div><div class="v ${t}">${esc(v)}</div><div class="s">${esc(sub)}</div></div>`).join("");
  }

  /* ---------- Trade map ---------- */
  function map(d) {
    const M = window.MAP, svg = $("map-svg"), tip = $("map-tip"), wrap = $("map");
    svg.innerHTML = "";
    svg.setAttribute("viewBox", `0 0 ${M.w} ${M.h}`);
    const C = { gain: css("--gain"), loss: css("--loss"), flat: css("--flat"), dot: css("--dot") };
    const held = new Set(d.positions.map((p) => p.symbol));
    const lastTrade = {};
    for (const t of d.trades) if (!lastTrade[t.symbol]) lastTrade[t.symbol] = t;  // trades are newest first

    let off = 0;
    const pins = d.symbols.map((s) => {
      const hq = M.hq[s.symbol];
      const pnl = s.realized_pnl + (s.open_pnl || 0);
      const r = Math.max(6, Math.min(20, 4 + Math.sqrt(s.traded_dollars) * 1.25));
      const ax = hq ? hq[0] : 60 + (off++) * 56, ay = hq ? hq[1] : 585;
      return { ...s, pnl, r, ax, ay, x: ax, y: ay, city: hq ? hq[2] : "Location not mapped yet", held: held.has(s.symbol), t: tone(pnl) };
    });

    // Spread pins that share a city (the Bay Area gets crowded) while keeping them near home.
    for (let it = 0; it < 400; it++) {
      for (let i = 0; i < pins.length; i++) for (let j = i + 1; j < pins.length; j++) {
        const a = pins[i], b = pins[j];
        let dx = b.x - a.x, dy = b.y - a.y, dist = Math.hypot(dx, dy);
        // Leave room for the ticker label, which sits to the right of each pin.
        const min = a.r + b.r + (Math.abs(dy) < 14 ? 44 : 14);
        if (dist < min) {
          if (dist < 0.01) { dx = Math.cos(i + j); dy = Math.sin(i + j); dist = 1; }
          const push = (min - dist) / 2;
          a.x -= dx / dist * push; a.y -= dy / dist * push;
          b.x += dx / dist * push; b.y += dy / dist * push;
        }
      }
      for (const p of pins) {
        p.x += (p.ax - p.x) * 0.006; p.y += (p.ay - p.y) * 0.006;
        p.x = Math.max(p.r + 6, Math.min(M.w - p.r - 50, p.x));
        p.y = Math.max(p.r + 6, Math.min(M.h - p.r - 6, p.y));
      }
    }

    // Land: faint state lines, then the dot matrix tinted by nearby pins.
    el("path", { d: M.states, class: "state-line" }, svg);
    const dotsG = el("g", {}, svg);
    const reach = 70;
    for (const [x, y] of M.dots) {
      let best = 0, col = null;
      for (const p of pins) {
        const k = 1 - Math.hypot(x - p.ax, y - p.ay) / (reach + p.r * 2);
        if (k > best) { best = k; col = C[p.t]; }
      }
      const c = el("circle", { cx: x, cy: y, r: 1.9, class: "land-dot" }, dotsG);
      if (col && best > 0) {
        c.style.fill = col;
        c.style.fillOpacity = (0.1 + best * best * 0.75).toFixed(2);
        c.setAttribute("r", (1.9 + best * 0.9).toFixed(2));
      }
      c.style.opacity = 0;
      c.style.transition = `opacity .6s ease ${(x / M.w * 900).toFixed(0)}ms`;
    }
    requestAnimationFrame(() => requestAnimationFrame(() => dotsG.querySelectorAll("circle").forEach((c) => (c.style.opacity = 1))));

    const pinsG = el("g", {}, svg);
    const byPnl = [...pins].sort((a, b) => b.pnl - a.pnl);
    pins.forEach((p, i) => {
      const g = el("g", { class: "pin" + (p.held ? " held" : ""), "data-sym": p.symbol, tabindex: 0, role: "button",
        "aria-label": `${p.symbol}, ${p.city}, P&L ${money(p.pnl, true)}` }, pinsG);
      if (Math.hypot(p.x - p.ax, p.y - p.ay) > 3) {
        el("line", { x1: p.ax, y1: p.ay, x2: p.x, y2: p.y, class: "leader" }, g);
        el("circle", { cx: p.ax, cy: p.ay, r: 1.8, fill: C[p.t] }, g);
      }
      el("circle", { cx: p.x, cy: p.y, r: p.r * 2.1, fill: C[p.t], class: "glow", filter: "blur(6px)" }, g);
      el("circle", { cx: p.x, cy: p.y, r: p.r, stroke: C[p.t], class: "halo" }, g);
      el("circle", { cx: p.x, cy: p.y, r: p.r, fill: C[p.t], class: "core" }, g);
      const left = p.x > M.w - 90;
      const label = el("text", { x: p.x + (left ? -(p.r + 5) : p.r + 5), y: p.y + 4, "text-anchor": left ? "end" : "start" }, g);
      label.textContent = p.symbol;
      g.style.opacity = 0;
      g.animate([{ opacity: 0, transform: "translateY(-14px)" }, { opacity: 1, transform: "translateY(0)" }],
        { duration: 500, delay: 700 + i * 90, easing: "cubic-bezier(.2,.8,.2,1)", fill: "forwards" });

      const show = () => focus(p.symbol, true);
      g.addEventListener("mouseenter", show);
      g.addEventListener("focus", show);
      g.addEventListener("click", show);
      g.addEventListener("mouseleave", () => focus(null));
      g.addEventListener("blur", () => focus(null));
    });

    // Leaderboard beside the map.
    const board = $("board");
    board.innerHTML = byPnl.map((p) => `<li data-sym="${esc(p.symbol)}"><span class="sym">${esc(p.symbol)}<span class="sub">${esc(p.city.split(" (")[0])}${p.held ? " · held" : ""}</span></span><span class="p ${p.t}">${money(p.pnl, true)}</span></li>`).join("")
      || `<li class="empty">No trades yet.</li>`;
    board.querySelectorAll("li[data-sym]").forEach((li) => {
      li.addEventListener("mouseenter", () => focus(li.dataset.sym, true));
      li.addEventListener("mouseleave", () => focus(null));
    });

    function focus(sym, withTip) {
      pinsG.querySelectorAll(".pin").forEach((g) => {
        g.classList.toggle("dim", !!sym && g.dataset.sym !== sym);
        g.classList.toggle("focus", g.dataset.sym === sym);
      });
      board.querySelectorAll("li").forEach((li) => li.classList.toggle("focus", li.dataset.sym === sym));
      if (!sym || !withTip) { tip.hidden = true; return; }
      const p = pins.find((q) => q.symbol === sym);
      const pos = d.positions.find((q) => q.symbol === sym);
      const lt = lastTrade[sym];
      tip.innerHTML = `<div class="t"><span>${esc(sym)}</span><span class="${p.t}">${money(p.pnl, true)}</span></div>
        <div class="city">${esc(p.city)}</div>
        <dl><dt>Trades</dt><dd>${p.trades}</dd>
        <dt>Won / lost</dt><dd>${p.wins} / ${p.losses}</dd>
        <dt>Dollars traded</dt><dd>${money(p.traded_dollars)}</dd>
        ${pos ? `<dt>Held now</dt><dd>${money(pos.value)} <span class="${tone(pos.pnl)}">${pct(pos.pnl_pct)}</span></dd>` : ""}</dl>
        ${lt ? `<div class="why">Last: ${esc(lt.side)} on ${fmtDay(lt.day)}. ${esc(lt.reason)}</div>` : ""}`;
      tip.hidden = false;
      const box = wrap.getBoundingClientRect(), k = box.width / M.w;
      let x = p.x * k + p.r * k + 14, y = p.y * k - 20;
      if (x + 290 > box.width) x = p.x * k - p.r * k - 14 - tip.offsetWidth;
      y = Math.max(8, Math.min(y, box.height - tip.offsetHeight - 8));
      tip.style.left = Math.max(8, x) + "px";
      tip.style.top = y + "px";
    }
  }

  /* ---------- Account vs SPY chart ---------- */
  function chart(d) {
    const svg = $("chart-svg"), tip = $("chart-tip"), data = d.curve;
    const W = svg.clientWidth || 900, H = 300, L = 46, R = 14, T = 14, B = 30;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.innerHTML = "";
    if (data.length < 2) {
      el("text", { x: W / 2, y: H / 2, "text-anchor": "middle", fill: css("--text-2") }, svg).textContent = "The chart fills in after two daily marks.";
      return;
    }
    const vals = data.flatMap((p) => [p.acct_index, p.spy_index]).filter((v) => v != null);
    let lo = Math.min(...vals, 100), hi = Math.max(...vals, 100);
    const pad = (hi - lo) * 0.12 || 1; lo -= pad; hi += pad;
    const x = (i) => L + i * (W - L - R) / (data.length - 1);
    const y = (v) => T + (hi - v) * (H - T - B) / (hi - lo);
    const line = (k) => data.map((p, i) => p[k] == null ? "" : `${i && data[i - 1][k] != null ? "L" : "M"}${x(i).toFixed(1)},${y(p[k]).toFixed(1)}`).join("");

    const defs = el("defs", {}, svg);
    const grad = el("linearGradient", { id: "acctFill", x1: 0, x2: 0, y1: 0, y2: 1 }, defs);
    el("stop", { offset: "0%", "stop-color": css("--gain"), "stop-opacity": 0.28 }, grad);
    el("stop", { offset: "100%", "stop-color": css("--gain"), "stop-opacity": 0 }, grad);

    for (let k = 0; k <= 4; k++) {
      const v = lo + (hi - lo) * k / 4;
      el("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: css("--line") }, svg);
      el("text", { x: L - 8, y: y(v) + 4, "text-anchor": "end", "font-size": 11, fill: css("--text-3"), "font-family": css("--mono") }, svg).textContent = v.toFixed(1);
    }
    el("line", { x1: L, x2: W - R, y1: y(100), y2: y(100), stroke: css("--text-3"), "stroke-dasharray": "3 4" }, svg);
    const ticks = Math.min(6, data.length);
    for (let k = 0; k < ticks; k++) {
      const i = Math.round(k * (data.length - 1) / (ticks - 1));
      el("text", { x: x(i), y: H - 8, "text-anchor": k === 0 ? "start" : k === ticks - 1 ? "end" : "middle", "font-size": 11, fill: css("--text-3") }, svg).textContent = fmtDay(data[i].day);
    }
    el("path", { d: `${line("acct_index")}L${x(data.length - 1)},${H - B}L${x(0)},${H - B}Z`, fill: "url(#acctFill)" }, svg);
    const spy = el("path", { d: line("spy_index"), fill: "none", stroke: css("--spy"), "stroke-width": 2, "stroke-linejoin": "round" }, svg);
    const acct = el("path", { d: line("acct_index"), fill: "none", stroke: css("--gain"), "stroke-width": 2.5, "stroke-linejoin": "round" }, svg);
    for (const p of [spy, acct]) {
      const len = p.getTotalLength();
      p.style.strokeDasharray = len; p.style.strokeDashoffset = len;
      p.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }], { duration: 1400, easing: "cubic-bezier(.3,.7,.2,1)", fill: "forwards" });
    }
    const last = data[data.length - 1];
    el("circle", { cx: x(data.length - 1), cy: y(last.acct_index), r: 4, fill: css("--gain") }, svg);

    // Trade markers along the bottom of the chart.
    const dayIdx = Object.fromEntries(data.map((p, i) => [p.day, i]));
    for (const t of d.trades) {
      const i = dayIdx[t.day];
      if (i == null) continue;
      el("rect", { x: x(i) - 1, y: H - B - (t.side === "buy" ? 8 : 14), width: 2, height: 6, rx: 1,
        fill: t.side === "buy" ? css("--spy") : css("--gold"), opacity: 0.8 }, svg);
    }

    const xh = el("line", { y1: T, y2: H - B, stroke: css("--text-3"), "stroke-dasharray": "3 3", visibility: "hidden" }, svg);
    const d1 = el("circle", { r: 4.5, fill: css("--gain"), stroke: css("--bg"), "stroke-width": 2, visibility: "hidden" }, svg);
    const d2 = el("circle", { r: 4.5, fill: css("--spy"), stroke: css("--bg"), "stroke-width": 2, visibility: "hidden" }, svg);
    const hit = el("rect", { x: L, y: 0, width: W - L - R, height: H, fill: "transparent" }, svg);
    hit.addEventListener("mousemove", (ev) => {
      const r = svg.getBoundingClientRect(), px = (ev.clientX - r.left) * (W / r.width);
      const i = Math.max(0, Math.min(data.length - 1, Math.round((px - L) / (W - L - R) * (data.length - 1)))), p = data[i];
      [xh, d1].forEach((n) => n.setAttribute("visibility", "visible"));
      xh.setAttribute("x1", x(i)); xh.setAttribute("x2", x(i));
      d1.setAttribute("cx", x(i)); d1.setAttribute("cy", y(p.acct_index));
      if (p.spy_index != null) { d2.setAttribute("visibility", "visible"); d2.setAttribute("cx", x(i)); d2.setAttribute("cy", y(p.spy_index)); }
      else d2.setAttribute("visibility", "hidden");
      const n = d.trades.filter((t) => t.day === p.day);
      tip.innerHTML = `<div>${fmtDay(p.day)}</div><div>Account <b class="gain">${money(p.equity)}</b> (${p.acct_index.toFixed(2)})</div>
        <div>SPY <b style="color:var(--spy)">${p.spy_index == null ? "n/a" : p.spy_index.toFixed(2)}</b></div>
        ${n.length ? `<div class="muted">${n.map((t) => `${esc(t.side)} ${esc(t.symbol)}`).join(", ")}</div>` : ""}`;
      tip.hidden = false;
      const sx = x(i) * r.width / W;
      tip.style.left = Math.min(sx + 14, r.width - tip.offsetWidth - 4) + "px";
      tip.style.top = "10px";
    });
    hit.addEventListener("mouseleave", () => { tip.hidden = true; [xh, d1, d2].forEach((n) => n.setAttribute("visibility", "hidden")); });
  }

  function positions(d) {
    $("positions").innerHTML = d.positions.map((p) => `<div class="pos">
      <span class="sym">${esc(p.symbol)}</span><span class="pnl ${tone(p.pnl)}">${money(p.pnl, true)} · ${pct(p.pnl_pct)}</span>
      <span class="meta">${p.shares.toFixed(4)} sh since ${fmtDay(p.opened)}</span><span class="meta r">${money(p.cost)} → ${money(p.value)}</span>
    </div>`).join("") || `<div class="empty">All cash right now. No open positions.</div>`;
  }

  function notes(d) {
    $("notes").innerHTML = d.notes.slice(0, 8).map((n) =>
      `<li class="${esc(n.kind)}"><span class="tag">${esc(n.kind)} · ${fmtDay(n.day)}</span>${esc(n.text)}</li>`).join("")
      || `<li class="empty">No takeaways yet. The daily run writes these.</li>`;
  }

  let tapeFilter = "all", tapeLimit = 12;
  function tape(d) {
    const pnlBySell = {};
    // Match closed round trips to sells by day + symbol so sells can show their result.
    for (const c of d.closed) pnlBySell[c.day + c.symbol] = c;
    const rows = d.trades.filter((t) => tapeFilter === "all" || t.side === tapeFilter);
    $("tape").innerHTML = rows.slice(0, tapeLimit).map((t) => {
      const c = t.side === "sell" ? pnlBySell[t.day + t.symbol] : null;
      return `<li><span class="d">${esc(t.day)}</span><span class="side ${esc(t.side)}">${esc(t.side)}</span>
        <span class="sym">${esc(t.symbol)}</span><span class="amt">${money(t.dollars)}</span>
        <span class="why">${c ? `<b class="${tone(c.pnl)}">${money(c.pnl, true)}</b>` : ""}${esc(t.reason)}</span></li>`;
    }).join("") + (rows.length > tapeLimit ? `<li style="display:block;border:0"><button class="more" id="more">Show ${rows.length - tapeLimit} more</button></li>` : "")
      || `<li class="empty">No trades yet.</li>`;
    const more = $("more");
    if (more) more.onclick = () => { tapeLimit += 25; tape(d); };
  }
  $("filters").addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (!b || !D) return;
    tapeFilter = b.dataset.f; tapeLimit = 12;
    $("filters").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    tape(D);
  });

  function blocks(d) {
    $("blocks").innerHTML = d.rejections.map((r) =>
      `<li><span class="d">${esc(r.day)}</span><span><b>${esc(r.side || "")} ${esc(r.symbol || "")}</b> ${money(r.dollars)}. ${esc(r.blocked_by.join("; "))}</span></li>`).join("")
      || `<li class="empty">Nothing blocked yet.</li>`;
  }

  let resizeT;
  addEventListener("resize", () => { clearTimeout(resizeT); resizeT = setTimeout(() => D && chart(D), 150); });

  async function refresh() {
    try {
      const data = await load();
      if (!D || data.generated_at !== D.generated_at) render(data);
    } catch (e) {
      $("updated").textContent = "Could not load the ledger export.";
    }
  }
  refresh();
  setInterval(refresh, 5 * 60 * 1000);  // pick up a new daily run without a reload
})();
