"""Day-trading experiment: Opening Range Breakout (ORB) on 5-minute bars.

Rules, per US trading session:
- The first 30 minutes define the "opening range" (high/low).
- If price then breaks above the range high, buy the momentum.
- Hard stop at the range low, profit target at entry + 2x the range,
  and ALWAYS flat by the close — a day trader never holds overnight.

A separate ML brain learns which breakouts tend to work (gap size,
relative volume, time of day, ...) from its own day-trade journal.

Honest limitation: Yahoo only provides ~60 days of 5-minute history,
so results here are an indication, not proof like the 6-year swing test.
"""
import os
import time

import numpy as np
import pandas as pd
import yfinance as yf

from .brain import Brain
from .config import Config
from .journal import Journal

# Feature snapshot at the moment of breakout — what the day-brain learns from.
DAY_FEATURE_NAMES = [
    "gap_pct",        # today's open vs yesterday's close
    "or_range_pct",   # opening range size relative to price
    "or_vol_ratio",   # opening-range volume vs its 20-session average
    "breakout_time",  # how far into the day the breakout came (0..1)
    "prev_day_ret",   # yesterday's session return
    "ret_5d",         # return over the last 5 sessions
    "avg_range_5",    # average daily range of the last 5 sessions
]


def load_intraday(tickers: list[str], cache_dir: str,
                  refresh: bool = False) -> dict[str, pd.DataFrame]:
    """~60 days of 5-minute bars per ticker, cached for the rest of the day."""
    os.makedirs(cache_dir, exist_ok=True)
    data = {}
    for t in tickers:
        cache_file = os.path.join(cache_dir, f"{t.replace('.', '_')}_5m.csv")
        fresh = (os.path.exists(cache_file)
                 and time.time() - os.path.getmtime(cache_file) < 20 * 3600)
        if fresh and not refresh:
            df = pd.read_csv(cache_file, index_col=0)
            df.index = pd.to_datetime(df.index, utc=True).tz_convert("America/New_York")
        else:
            df = yf.download(t, period="60d", interval="5m",
                             auto_adjust=True, progress=False)
            if df is None or df.empty:
                print(f"  ! skipping {t}: no intraday data")
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
            df.to_csv(cache_file)
        if len(df) > 500:
            data[t] = df
        else:
            print(f"  ! skipping {t}: insufficient intraday data")
    return data


def run_daytrade(cfg: Config, refresh: bool = False) -> None:
    # US tickers only: one session clock, and the most liquid 5-min data
    tickers = [t for t in cfg.universe if not t.endswith(".AS")]
    print(f"Downloading ~60 days of 5-minute bars for {len(tickers)} US tickers...")
    data = load_intraday(tickers, cfg.cache_dir, refresh)
    print(f"Loaded {len(data)} tickers. Running session-by-session simulation...\n")

    # fresh journal each run: the 60-day window overlaps the previous run,
    # so keeping old rows would double-count the same sessions
    if os.path.exists(cfg.day_db_path):
        os.remove(cfg.day_db_path)
    journal = Journal(cfg.day_db_path)
    brain = Brain(cfg.min_trades_to_learn, cfg.retrain_every, DAY_FEATURE_NAMES)

    # split each ticker into sessions, keyed by date
    sessions: dict[str, dict] = {}
    for t, df in data.items():
        sessions[t] = {d: g for d, g in df.groupby(df.index.date) if len(g) >= 30}
    all_dates = sorted({d for s in sessions.values() for d in s})

    hist: dict[str, list[dict]] = {t: [] for t in sessions}  # past session stats
    equity = cfg.starting_cash
    daily_pnl: dict = {}
    skipped_by_brain = 0

    for date in all_dates:
        # --- collect breakout candidates across the universe ---
        candidates = []
        for t, days in sessions.items():
            if date not in days:
                continue
            day = days[date]
            orb = day.iloc[:cfg.day_or_bars]
            rest = day.iloc[cfg.day_or_bars:]
            or_high = float(orb["High"].max())
            or_low = float(orb["Low"].min())
            rng = or_high - or_low
            rng_pct = rng / or_high
            if not (cfg.day_min_range_pct <= rng_pct <= cfg.day_max_range_pct):
                continue
            breakout = rest[rest["High"] > or_high]
            if breakout.empty:
                continue
            bar_i = rest.index.get_loc(breakout.index[0])

            h = hist[t]
            prev_close = h[-1]["close"] if h else float(day["Open"].iloc[0])
            or_vols = [s["or_vol"] for s in h[-20:]]
            feats = {
                "gap_pct": float(day["Open"].iloc[0]) / prev_close - 1,
                "or_range_pct": rng_pct,
                "or_vol_ratio": (float(orb["Volume"].sum()) / np.mean(or_vols)
                                 if or_vols else 1.0),
                "breakout_time": bar_i / max(len(rest), 1),
                "prev_day_ret": (h[-1]["close"] / h[-2]["close"] - 1
                                 if len(h) >= 2 else 0.0),
                "ret_5d": (prev_close / h[-5]["close"] - 1 if len(h) >= 5 else 0.0),
                "avg_range_5": (float(np.mean([s["range_pct"] for s in h[-5:]]))
                                if h else rng_pct),
            }
            conf = brain.win_probability(feats)
            if brain.model is not None and conf < cfg.confidence_threshold:
                skipped_by_brain += 1
                continue
            candidates.append((conf, t, or_high, or_low, rng, rest, bar_i, feats))

        # --- take the most confident few, simulate each trade ---
        for conf, t, or_high, or_low, rng, rest, bar_i, feats in sorted(
                candidates, key=lambda c: -c[0])[:cfg.max_positions]:
            entry = or_high * (1 + cfg.slippage_pct)
            shares = int((equity / cfg.max_positions
                          - cfg.commission_per_order) / entry)
            if shares < 1:
                continue
            stop, target = or_low, entry + cfg.day_target_rr * rng

            exit_price, reason = float(rest["Close"].iloc[-1]), "eod_exit"
            for j in range(bar_i, len(rest)):
                bar = rest.iloc[j]
                # same-bar ambiguity is resolved pessimistically: stop first
                if float(bar["Low"]) <= stop:
                    exit_price, reason = stop, "stop_loss"
                    break
                if j > bar_i and float(bar["High"]) >= target:
                    exit_price, reason = target, "take_profit"
                    break

            fill_out = exit_price * (1 - cfg.slippage_pct)
            cost_basis = shares * entry + cfg.commission_per_order
            pnl = shares * fill_out - cfg.commission_per_order - shares * entry \
                - cfg.commission_per_order
            pnl_pct = pnl / cost_basis
            equity += pnl
            daily_pnl[date] = daily_pnl.get(date, 0.0) + pnl

            journal.record_trade("daytrade", t, "orb_breakout", date, entry,
                                 date, fill_out, shares, pnl, pnl_pct, reason,
                                 conf, feats)
            brain.maybe_retrain(journal)

        # --- after trading, append today's session stats to history ---
        for t, days in sessions.items():
            if date not in days:
                continue
            day = days[date]
            hist[t].append({
                "close": float(day["Close"].iloc[-1]),
                "or_vol": float(day["Volume"].iloc[:cfg.day_or_bars].sum()),
                "range_pct": (float(day["High"].max()) - float(day["Low"].min()))
                             / float(day["Close"].iloc[-1]),
            })

    # --- report ---
    from .report import print_report
    print(f"Brain skipped {skipped_by_brain} low-confidence breakouts.")
    print_report(journal, "daytrade")

    if daily_pnl:
        s = pd.Series(daily_pnl).sort_index()
        avg_day_pct = (s / cfg.starting_cash).mean()
        print(f"\n=== Day-by-day (over {len(s)} trading days) ===")
        print(f"Average per day:  EUR {s.mean():+,.2f}  ({avg_day_pct:+.2%} of start capital)")
        print(f"Best day:         EUR {s.max():+,.2f}")
        print(f"Worst day:        EUR {s.min():+,.2f}")
        print(f"Green days:       {(s > 0).sum()}/{len(s)}")
        print(f"Final equity:     EUR {equity:,.2f}  (started {cfg.starting_cash:,.0f})")

    lessons = brain.lessons()
    if lessons:
        print("\n=== What the day-brain looks at (feature importance) ===")
        for name, imp in lessons:
            print(f"  {name:<14} {'#' * int(imp * 100)} {imp:.0%}")
