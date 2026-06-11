"""Trade journal — the bot's memory.

Every closed trade is stored with the market conditions at entry and the
outcome. This is what the brain trains on: it literally learns from the
bot's own mistakes (and successes).
"""
import json
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,              -- 'backtest' or 'paper'
    ticker TEXT NOT NULL,
    setup TEXT NOT NULL,             -- which strategy proposed it
    entry_date TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_date TEXT,
    exit_price REAL,
    shares REAL NOT NULL,
    pnl REAL,                        -- realized profit/loss in EUR, after costs
    pnl_pct REAL,
    exit_reason TEXT,                -- stop_loss / take_profit / time_exit
    confidence REAL,                 -- brain's win-probability at entry
    features TEXT NOT NULL           -- JSON snapshot of market conditions at entry
);
CREATE TABLE IF NOT EXISTS portfolio_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS equity_history (
    date TEXT PRIMARY KEY,           -- one snapshot per paper-trading day
    equity REAL NOT NULL,
    cash REAL NOT NULL,
    open_positions INTEGER NOT NULL
);
"""


class Journal:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def record_trade(self, mode, ticker, setup, entry_date, entry_price,
                     exit_date, exit_price, shares, pnl, pnl_pct,
                     exit_reason, confidence, features: dict) -> None:
        self.conn.execute(
            """INSERT INTO trades (mode, ticker, setup, entry_date, entry_price,
               exit_date, exit_price, shares, pnl, pnl_pct, exit_reason,
               confidence, features)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (mode, ticker, setup, str(entry_date), entry_price, str(exit_date),
             exit_price, shares, pnl, pnl_pct, exit_reason, confidence,
             json.dumps(features)),
        )
        self.conn.commit()

    def training_data(self) -> tuple[list[dict], list[int]]:
        """All closed trades as (feature dicts, win/loss labels)."""
        rows = self.conn.execute(
            "SELECT features, pnl FROM trades WHERE pnl IS NOT NULL"
        ).fetchall()
        X = [json.loads(f) for f, _ in rows]
        y = [1 if pnl > 0 else 0 for _, pnl in rows]
        return X, y

    def ticker_win_rates(self) -> dict[str, tuple[int, float]]:
        """Per ticker: (closed trade count, win rate) — how well the bot
        has historically done on each stock."""
        rows = self.conn.execute(
            """SELECT ticker, COUNT(*), AVG(pnl > 0) FROM trades
               WHERE pnl IS NOT NULL GROUP BY ticker"""
        ).fetchall()
        return {t: (int(n), float(wr)) for t, n, wr in rows}

    def closed_trade_count(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM trades WHERE pnl IS NOT NULL"
        ).fetchone()[0]

    def all_trades(self, mode: str | None = None):
        q = "SELECT * FROM trades WHERE pnl IS NOT NULL"
        args = ()
        if mode:
            q += " AND mode = ?"
            args = (mode,)
        cur = self.conn.execute(q + " ORDER BY exit_date", args)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def record_equity(self, date: str, equity: float, cash: float,
                      open_positions: int) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO equity_history VALUES (?,?,?,?)",
            (date, equity, cash, open_positions),
        )
        self.conn.commit()

    def equity_history(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT date, equity, cash, open_positions FROM equity_history "
            "ORDER BY date"
        ).fetchall()
        return [{"date": d, "equity": e, "cash": c, "open_positions": n}
                for d, e, c, n in rows]

    # --- persistent state for live paper trading (open positions, cash) ---
    def save_state(self, key: str, value) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO portfolio_state (key, value) VALUES (?,?)",
            (key, json.dumps(value)),
        )
        self.conn.commit()

    def load_state(self, key: str, default=None):
        row = self.conn.execute(
            "SELECT value FROM portfolio_state WHERE key = ?", (key,)
        ).fetchone()
        return json.loads(row[0]) if row else default
