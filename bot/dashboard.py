"""Dashboard generator — one self-contained HTML file from the journal.

`python -m bot dashboard` (and every paper run) renders bot_data/dashboard.html:
equity curve, open positions, recent trades, P/L per stock, win-rate trend.
No server needed — just open the file in a browser. When the bot runs in
the cloud, the file is committed back to the repo after every run.
"""
import json
from datetime import datetime

from .config import Config
from .journal import Journal

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trading Bot Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root {
    --bg: #0d0d0d; --card: #1a1a1a; --border: #242424;
    --text: #f0ece4; --muted: #9a9a9a;
    --green: #10b981; --red: #ef4444; --accent: #c4a97d;
  }
  * { box-sizing: border-box; margin: 0; }
  body { background: var(--bg); color: var(--text);
         font: 14px/1.5 "Inter", -apple-system, "Segoe UI", sans-serif;
         padding: 32px 24px; max-width: 1180px; margin: 0 auto; }
  .eyebrow { color: var(--accent); font-size: 11px; font-weight: 600;
             text-transform: uppercase; letter-spacing: .12em; margin-bottom: 6px; }
  h1 { font-size: 30px; font-weight: 800; letter-spacing: -.02em; margin-bottom: 4px; }
  h2 { font-size: 12px; color: var(--muted); margin: 34px 0 12px;
       text-transform: uppercase; letter-spacing: .1em; font-weight: 600; }
  .sub { color: var(--muted); font-size: 12px; margin-bottom: 8px; }
  .status { display: inline-flex; align-items: center; gap: 7px; margin-bottom: 26px;
            font-size: 12px; color: var(--muted); }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green);
         box-shadow: 0 0 0 3px rgba(16,185,129,.2); }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr));
           gap: 12px; }
  .card { background: var(--card); border: 1px solid var(--border);
          border-radius: 12px; padding: 16px; }
  .card .label { color: var(--muted); font-size: 11px; font-weight: 600;
                 text-transform: uppercase; letter-spacing: .1em; }
  .card .value { font-size: 24px; font-weight: 800; margin-top: 6px;
                 letter-spacing: -.02em; font-variant-numeric: tabular-nums; }
  .pos { color: var(--green); } .neg { color: var(--red); }
  .chart-box { background: var(--card); border: 1px solid var(--border);
               border-radius: 12px; padding: 18px; margin-top: 12px; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  @media (max-width: 800px) { .grid2 { grid-template-columns: 1fr; } }
  table { width: 100%; border-collapse: collapse; background: var(--card);
          border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
  th, td { padding: 10px 14px; text-align: left; font-size: 13px; }
  td { font-variant-numeric: tabular-nums; }
  th { background: var(--bg); color: var(--muted); font-weight: 600;
       font-size: 11px; text-transform: uppercase; letter-spacing: .08em; }
  tr + tr td { border-top: 1px solid var(--border); }
  table tr:hover td { background: rgba(36,36,36,.5); }
  .badge { padding: 2px 10px; border-radius: 999px; font-size: 11px;
           font-weight: 600; letter-spacing: .03em; }
  .long { background: rgba(16,185,129,.1); color: var(--green);
          border: 1px solid rgba(16,185,129,.3); }
  .short { background: rgba(239,68,68,.1); color: var(--red);
           border: 1px solid rgba(239,68,68,.3); }
  .paper { background: rgba(196,169,125,.2); color: var(--accent);
           border: 1px solid rgba(196,169,125,.3); }
  .backtest { background: #242424; color: var(--muted); border: 1px solid #303030; }
  canvas { max-height: 300px; }
  .pager { display: flex; gap: 6px; margin-top: 14px; flex-wrap: wrap; align-items: center; }
  .pager button { background: var(--card); color: var(--text); font-family: inherit;
                  border: 1px solid var(--border); border-radius: 8px;
                  padding: 5px 12px; cursor: pointer; font-size: 13px; }
  .pager button:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
  .pager button.cur { background: var(--accent); color: #0d0d0d;
                      font-weight: 700; border-color: var(--accent); }
  .pager button:disabled { opacity: .4; cursor: default; }
  .pager .dots { color: var(--muted); padding: 4px 2px; }
  .tabs { display: flex; gap: 8px; margin-bottom: 10px; flex-wrap: wrap; }
  .tab { background: var(--card); color: var(--muted); font-family: inherit;
         border: 1px solid var(--border); border-radius: 999px;
         padding: 6px 14px; cursor: pointer; font-size: 12px; font-weight: 600; }
  .tab:hover { border-color: var(--accent); color: var(--text); }
  .tab.cur { background: var(--accent); color: #0d0d0d; border-color: var(--accent); }
  .hint { color: var(--muted); font-size: 12px; margin-bottom: 12px; max-width: 680px; }
</style>
</head>
<body>
<div class="eyebrow">Self-Learning Trading Bot</div>
<h1>Paper Portfolio</h1>
<div class="sub">Updated __GENERATED__ · fake money · mean reversion, long &amp; short</div>
<div class="status"><span class="dot"></span> Bot active · last trading run __LASTRUN__</div>

<div class="cards">
  <div class="card"><div class="label">Equity</div>
    <div class="value">€__EQUITY__</div></div>
  <div class="card"><div class="label">Cash</div>
    <div class="value">€__CASH__</div></div>
  <div class="card"><div class="label">Realized P/L (paper)</div>
    <div class="value __REAL_CLS__">__REALIZED__</div></div>
  <div class="card"><div class="label">Unrealized P/L</div>
    <div class="value __UNREAL_CLS__">__UNREALIZED__</div></div>
  <div class="card"><div class="label">Win rate (paper)</div>
    <div class="value">__WINRATE__</div></div>
  <div class="card"><div class="label">Closed trades (paper)</div>
    <div class="value">__NTRADES__</div></div>
</div>

<h2>Equity over time</h2>
<div class="chart-box"><canvas id="equityChart"></canvas></div>

<h2>Open positions</h2>
__POSITIONS__

<h2>Trades</h2>
<div class="tabs">
  <button id="tab-paper" class="tab cur" onclick="setFilter('paper')">🟢 Live paper (<span id="cnt-paper">0</span>)</button>
  <button id="tab-backtest" class="tab" onclick="setFilter('backtest')">Backtest training (<span id="cnt-backtest">0</span>)</button>
  <button id="tab-all" class="tab" onclick="setFilter('all')">All (<span id="cnt-all">0</span>)</button>
</div>
<div class="hint" id="tradesHint"></div>
<div id="tradesTable"><div class="card">No closed trades yet.</div></div>
<div class="pager" id="pager"></div>

<div class="grid2">
  <div>
    <h2>P/L per stock (live paper)</h2>
    <div class="chart-box"><canvas id="tickerChart"></canvas></div>
  </div>
  <div>
    <h2>Win rate trend (training + live, per 25 trades)</h2>
    <div class="chart-box"><canvas id="learnChart"></canvas></div>
  </div>
</div>

<script>
const DATA = __DATA__;
Chart.defaults.color = "#9a9a9a";
Chart.defaults.borderColor = "#242424";
Chart.defaults.font.family = "'Inter', sans-serif";

new Chart(document.getElementById("equityChart"), {
  type: "line",
  data: { labels: DATA.equity.labels, datasets: [{
    label: "Equity (EUR)", data: DATA.equity.values, borderColor: "#c4a97d",
    backgroundColor: "rgba(196,169,125,.12)", fill: true, tension: .25, pointRadius: 2 }]},
  options: { plugins: { legend: { display: false } } }
});

new Chart(document.getElementById("tickerChart"), {
  type: "bar",
  data: { labels: DATA.per_ticker.labels, datasets: [{
    data: DATA.per_ticker.values,
    backgroundColor: DATA.per_ticker.values.map(v => v >= 0 ? "#10b981" : "#ef4444") }]},
  options: { indexAxis: "y", plugins: { legend: { display: false } } }
});

new Chart(document.getElementById("learnChart"), {
  type: "line",
  data: { labels: DATA.learning.labels, datasets: [{
    label: "win rate", data: DATA.learning.values, borderColor: "#f0ece4",
    tension: .25, pointRadius: 2 }]},
  options: { scales: { y: { min: 0, max: 100,
    ticks: { callback: v => v + "%" } } },
    plugins: { legend: { display: false } } }
});

// --- trades, filterable (live paper / backtest / all), 25 per page ---
const PER_PAGE = 25;
let page = 1;
const money = v => (v >= 0 ? "+€" : "-€") +
  Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const HINTS = {
  paper: "The bot's real live paper trades since going live — this is what it is actually doing now.",
  backtest: "Historical simulation used to train the brain before going live. These are NOT live trades.",
  all: "Everything in the journal: live paper trades plus the backtest training history.",
};
// default to live paper if any exist, so the live activity is what you see first
let filter = DATA.trades.some(t => t.mode === "paper") ? "paper" : "all";

function visibleTrades() {
  return filter === "all" ? DATA.trades : DATA.trades.filter(t => t.mode === filter);
}
function setFilter(f) {
  filter = f; page = 1;
  document.querySelectorAll(".tab").forEach(b => b.classList.remove("cur"));
  document.getElementById("tab-" + f).classList.add("cur");
  renderTrades();
}

function renderTrades() {
  document.getElementById("cnt-paper").textContent =
    DATA.trades.filter(t => t.mode === "paper").length;
  document.getElementById("cnt-backtest").textContent =
    DATA.trades.filter(t => t.mode === "backtest").length;
  document.getElementById("cnt-all").textContent = DATA.trades.length;
  document.getElementById("tradesHint").textContent = HINTS[filter];
  document.getElementById("tab-" + filter).classList.add("cur");

  const list = visibleTrades();
  const total = list.length;
  if (!total) {
    document.getElementById("tradesTable").innerHTML =
      "<div class='card'>No trades in this view yet.</div>";
    document.getElementById("pager").innerHTML = "";
    return;
  }
  const pages = Math.ceil(total / PER_PAGE);
  page = Math.min(Math.max(1, page), pages);

  const rows = list.slice((page - 1) * PER_PAGE, page * PER_PAGE).map(t =>
    `<tr><td>${t.date}</td><td><b>${t.ticker}</b></td>` +
    `<td><span class="badge ${t.side}">${t.side.toUpperCase()}</span></td>` +
    `<td><span class="badge ${t.mode}">${t.mode}</span></td>` +
    `<td>${t.entry.toFixed(2)}</td><td>${t.exit.toFixed(2)}</td>` +
    `<td class="${t.pnl >= 0 ? "pos" : "neg"}">${money(t.pnl)}</td>` +
    `<td>${t.reason}</td></tr>`).join("");
  document.getElementById("tradesTable").innerHTML =
    "<table><tr><th>Closed</th><th>Stock</th><th>Side</th><th>Mode</th>" +
    "<th>Entry</th><th>Exit</th><th>P/L</th><th>Exit reason</th></tr>" + rows + "</table>";

  // page buttons: always 1 and last, current +/- 2, dots in between
  const nums = [];
  for (let p = 1; p <= pages; p++) {
    if (p === 1 || p === pages || Math.abs(p - page) <= 2) nums.push(p);
    else if (nums[nums.length - 1] !== "…") nums.push("…");
  }
  document.getElementById("pager").innerHTML =
    `<button ${page === 1 ? "disabled" : ""} onclick="go(${page - 1})">‹ Prev</button>` +
    nums.map(p => p === "…" ? `<span class="dots">…</span>` :
      `<button class="${p === page ? "cur" : ""}" onclick="go(${p})">${p}</button>`).join("") +
    `<button ${page === pages ? "disabled" : ""} onclick="go(${page + 1})">Next ›</button>`;
}
function go(p) { page = p; renderTrades(); }
renderTrades();
</script>
</body>
</html>
"""


def _money(x: float) -> str:
    return f"{x:+,.2f}".replace("+", "+€").replace("-", "-€")


def _cls(x: float) -> str:
    return "pos" if x >= 0 else "neg"


def render_dashboard(cfg: Config) -> str:
    journal = Journal(cfg.db_path)

    paper_trades = journal.all_trades("paper")
    all_trades = journal.all_trades(None)
    history = journal.equity_history()
    cash = journal.load_state("cash", cfg.starting_cash)
    positions = journal.load_state("positions", [])
    prices = journal.load_state("last_prices", {})

    def _sign(p):  # shorts profit when price falls
        return -1 if p.get("side", "long") == "short" else 1

    unrealized = sum((prices.get(p["ticker"], p["entry_price"]) - p["entry_price"])
                     * p["shares"] * _sign(p) for p in positions)
    pos_value = sum(prices.get(p["ticker"], p["entry_price"]) * p["shares"]
                    * _sign(p) for p in positions)
    equity = cash + pos_value
    realized = sum(t["pnl"] for t in paper_trades)
    wins = sum(1 for t in paper_trades if t["pnl"] > 0)
    winrate = f"{wins / len(paper_trades):.0%}" if paper_trades else "—"

    # open positions table
    if positions:
        rows = ""
        for p in positions:
            cur = prices.get(p["ticker"], p["entry_price"])
            upnl = (cur - p["entry_price"]) * p["shares"] * _sign(p)
            side = p.get("side", "long")
            rows += (f"<tr><td><b>{p['ticker']}</b></td>"
                     f"<td><span class='badge {side}'>{side.upper()}</span></td>"
                     f"<td>{p['shares']:.0f}</td><td>{p['entry_price']:.2f}</td>"
                     f"<td>{cur:.2f}</td><td class='{_cls(upnl)}'>{_money(upnl)}</td>"
                     f"<td>{p['entry_date']}</td><td>{p['days_held']}</td>"
                     f"<td>{p['confidence']:.0%}</td></tr>")
        positions_html = ("<table><tr><th>Stock</th><th>Side</th><th>Shares</th>"
                          "<th>Entry</th><th>Last</th><th>Unrealized</th>"
                          "<th>Since</th><th>Days</th><th>Confidence</th></tr>"
                          f"{rows}</table>")
    else:
        positions_html = "<div class='card'>No open positions.</div>"

    # all trades, newest first — paginated client-side, 25 per page
    trades_data = [
        {"date": str(t["exit_date"]), "ticker": t["ticker"], "mode": t["mode"],
         "side": "short" if "rip" in t["setup"] else "long",
         "entry": round(t["entry_price"], 2), "exit": round(t["exit_price"], 2),
         "pnl": round(t["pnl"], 2), "reason": t["exit_reason"]}
        for t in sorted(all_trades, key=lambda t: str(t["exit_date"]), reverse=True)
    ]

    # charts data
    eq_labels = [h["date"] for h in history] or [datetime.now().strftime("%Y-%m-%d")]
    eq_values = [round(h["equity"], 2) for h in history] or [round(equity, 2)]

    # per-stock P/L from LIVE paper trades (what the bot actually earned),
    # falling back to the full journal until live trades exist
    per_ticker: dict[str, float] = {}
    for t in (paper_trades or all_trades):
        per_ticker[t["ticker"]] = per_ticker.get(t["ticker"], 0.0) + t["pnl"]
    ranked = sorted(per_ticker.items(), key=lambda kv: kv[1], reverse=True)

    chunk = 25
    learn_labels, learn_values = [], []
    for i in range(0, len(all_trades) - chunk + 1, chunk):
        batch = all_trades[i:i + chunk]
        learn_labels.append(str(i + chunk))
        learn_values.append(round(100 * sum(1 for t in batch if t["pnl"] > 0) / chunk))

    data = {
        "equity": {"labels": eq_labels, "values": eq_values},
        "per_ticker": {"labels": [k for k, _ in ranked],
                       "values": [round(v, 2) for _, v in ranked]},
        "learning": {"labels": learn_labels, "values": learn_values},
        "trades": trades_data,
    }

    last_run = journal.load_state("last_paper_run") or "—"

    html = (PAGE
            .replace("__GENERATED__", datetime.now().strftime("%Y-%m-%d %H:%M"))
            .replace("__LASTRUN__", last_run)
            .replace("__EQUITY__", f"{equity:,.2f}")
            .replace("__CASH__", f"{cash:,.2f}")
            .replace("__REALIZED__", _money(realized))
            .replace("__REAL_CLS__", _cls(realized))
            .replace("__UNREALIZED__", _money(unrealized))
            .replace("__UNREAL_CLS__", _cls(unrealized))
            .replace("__WINRATE__", winrate)
            .replace("__NTRADES__", str(len(paper_trades)))
            .replace("__POSITIONS__", positions_html)
            .replace("__DATA__", json.dumps(data)))

    # bot_data copy for local viewing + docs/index.html for GitHub Pages
    import os
    os.makedirs("docs", exist_ok=True)
    out = "bot_data/dashboard.html"
    for path in (out, "docs/index.html"):
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
    return out
