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
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root {
    --bg: #0d1117; --card: #161b22; --border: #30363d;
    --text: #e6edf3; --muted: #8b949e;
    --green: #3fb950; --red: #f85149; --accent: #58a6ff;
  }
  * { box-sizing: border-box; margin: 0; }
  body { background: var(--bg); color: var(--text);
         font: 14px/1.5 -apple-system, "Segoe UI", sans-serif; padding: 24px; }
  h1 { font-size: 20px; margin-bottom: 4px; }
  h2 { font-size: 15px; color: var(--muted); margin: 28px 0 12px; }
  .sub { color: var(--muted); font-size: 12px; margin-bottom: 20px; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
           gap: 12px; }
  .card { background: var(--card); border: 1px solid var(--border);
          border-radius: 8px; padding: 14px; }
  .card .label { color: var(--muted); font-size: 12px; }
  .card .value { font-size: 22px; font-weight: 600; margin-top: 2px; }
  .pos { color: var(--green); } .neg { color: var(--red); }
  .chart-box { background: var(--card); border: 1px solid var(--border);
               border-radius: 8px; padding: 16px; margin-top: 12px; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  @media (max-width: 800px) { .grid2 { grid-template-columns: 1fr; } }
  table { width: 100%; border-collapse: collapse; background: var(--card);
          border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
  th, td { padding: 8px 12px; text-align: left; font-size: 13px; }
  th { background: #1c2128; color: var(--muted); font-weight: 500; }
  tr + tr td { border-top: 1px solid var(--border); }
  .badge { padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
  .long { background: #1a3526; color: var(--green); }
  .short { background: #3d1d23; color: var(--red); }
  .paper { background: #1c2f45; color: var(--accent); }
  .backtest { background: #2d2436; color: #c297e8; }
  canvas { max-height: 300px; }
  .pager { display: flex; gap: 6px; margin-top: 12px; flex-wrap: wrap; align-items: center; }
  .pager button { background: var(--card); color: var(--text);
                  border: 1px solid var(--border); border-radius: 6px;
                  padding: 4px 10px; cursor: pointer; font-size: 13px; }
  .pager button:hover:not(:disabled) { border-color: var(--accent); }
  .pager button.cur { background: var(--accent); color: #0d1117;
                      font-weight: 600; border-color: var(--accent); }
  .pager button:disabled { opacity: .4; cursor: default; }
  .pager .dots { color: var(--muted); padding: 4px 2px; }
</style>
</head>
<body>
<h1>🤖 Trading Bot — Paper Portfolio</h1>
<div class="sub">Generated __GENERATED__ · fake money · long-only mean-reversion dip buyer</div>

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

<h2>All trades (<span id="tradeCount">0</span>)</h2>
<div id="tradesTable"><div class="card">No closed trades yet.</div></div>
<div class="pager" id="pager"></div>

<div class="grid2">
  <div>
    <h2>P/L per stock (all journaled trades)</h2>
    <div class="chart-box"><canvas id="tickerChart"></canvas></div>
  </div>
  <div>
    <h2>Win rate trend (per 25 trades)</h2>
    <div class="chart-box"><canvas id="learnChart"></canvas></div>
  </div>
</div>

<script>
const DATA = __DATA__;
Chart.defaults.color = "#8b949e";
Chart.defaults.borderColor = "#30363d";

new Chart(document.getElementById("equityChart"), {
  type: "line",
  data: { labels: DATA.equity.labels, datasets: [{
    label: "Equity (EUR)", data: DATA.equity.values, borderColor: "#58a6ff",
    backgroundColor: "rgba(88,166,255,.12)", fill: true, tension: .25, pointRadius: 2 }]},
  options: { plugins: { legend: { display: false } } }
});

new Chart(document.getElementById("tickerChart"), {
  type: "bar",
  data: { labels: DATA.per_ticker.labels, datasets: [{
    data: DATA.per_ticker.values,
    backgroundColor: DATA.per_ticker.values.map(v => v >= 0 ? "#3fb950" : "#f85149") }]},
  options: { indexAxis: "y", plugins: { legend: { display: false } } }
});

new Chart(document.getElementById("learnChart"), {
  type: "line",
  data: { labels: DATA.learning.labels, datasets: [{
    label: "win rate", data: DATA.learning.values, borderColor: "#c297e8",
    tension: .25, pointRadius: 2 }]},
  options: { scales: { y: { min: 0, max: 100,
    ticks: { callback: v => v + "%" } } },
    plugins: { legend: { display: false } } }
});

// --- all trades, paginated 25 per page ---
const PER_PAGE = 25;
let page = 1;
const money = v => (v >= 0 ? "+€" : "-€") +
  Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function renderTrades() {
  const total = DATA.trades.length;
  document.getElementById("tradeCount").textContent = total;
  if (!total) return;
  const pages = Math.ceil(total / PER_PAGE);
  page = Math.min(Math.max(1, page), pages);

  const rows = DATA.trades.slice((page - 1) * PER_PAGE, page * PER_PAGE).map(t =>
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

    per_ticker: dict[str, float] = {}
    for t in all_trades:
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

    html = (PAGE
            .replace("__GENERATED__", datetime.now().strftime("%Y-%m-%d %H:%M"))
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

    out = "bot_data/dashboard.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return out
