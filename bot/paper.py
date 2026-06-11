"""Live paper trading on real, current prices.

Run `python -m bot paper` once per day (e.g. after the US close).
Positions and cash persist in the journal database between runs, and the
brain retrains on everything journaled so far — backtest plus paper trades.
"""
from datetime import date

import pandas as pd

from .brain import Brain
from .config import Config
from .data import load_universe
from .features import add_indicators, feature_vector, ticker_winrate
from .journal import Journal
from .portfolio import Portfolio, Position
from .strategy import entry_signal


def run_paper_day(cfg: Config) -> None:
    journal = Journal(cfg.db_path)
    today = str(date.today())

    if journal.load_state("last_paper_run") == today:
        print("Already ran today — paper trading works on daily bars, once per day.")
        return

    print("Fetching fresh prices...")
    # full history_years, NOT a shorter window: this shares the cache with
    # `bot train`, and a short download would cripple the next retrain
    data = load_universe(cfg.universe, cfg.history_years, cfg.cache_dir, refresh=True)
    frames = {t: add_indicators(df) for t, df in data.items()}

    # weekend/holiday guard: don't process the same daily bar twice
    last_bar = str(max(df.index[-1].date() for df in frames.values()))
    if journal.load_state("last_bar_date") == last_bar:
        print("No new market data since last run (weekend/holiday) — nothing to do.")
        return
    journal.save_state("last_bar_date", last_bar)

    # restore portfolio
    portfolio = Portfolio(cfg)
    portfolio.cash = journal.load_state("cash", cfg.starting_cash)
    for p in journal.load_state("positions", []):
        portfolio.positions[p["ticker"]] = Position(**p)

    # train the brain on the full journal
    brain = Brain(cfg.min_trades_to_learn, cfg.retrain_every)
    brain.maybe_retrain(journal)
    n = journal.closed_trade_count()
    print(f"Brain: {'trained on ' + str(n) + ' past trades' if brain.model else 'still gathering experience (' + str(n) + f'/{cfg.min_trades_to_learn} trades)'}")

    prices = {t: float(df["Close"].iloc[-1]) for t, df in frames.items()}

    # --- exits ---
    for ticker in list(portfolio.positions):
        if ticker not in frames:
            continue
        row = frames[ticker].iloc[-1]
        pos = portfolio.positions[ticker]
        pos.days_held += 1
        exit_hit = portfolio.check_exit(pos, float(row["Low"]), float(row["High"]),
                                        float(row["Close"]), float(row["sma5"]))
        if exit_hit:
            price, reason = exit_hit
            pos, pnl, pnl_pct = portfolio.close_position(ticker, today, price, reason)
            journal.record_trade("paper", ticker, pos.setup, pos.entry_date,
                                 pos.entry_price, today, price, pos.shares, pnl,
                                 pnl_pct, reason, pos.confidence, pos.features)
            print(f"  SELL {ticker}: {reason}, P/L EUR {pnl:+.2f} ({pnl_pct:+.1%})")

    # --- market breadth: how much of the universe is above its 200-day? ---
    above = total = 0
    for df in frames.values():
        row = df.iloc[-1]
        if not pd.isna(row["sma200"]):
            total += 1
            above += row["Close"] > row["sma200"]
    breadth_ok = total > 0 and above / total >= cfg.min_market_breadth
    if not breadth_ok:
        print(f"  market breadth {above}/{total} below limit — no dip buying today")

    # --- entries: rank candidates, take the most confident ---
    candidates = []
    if breadth_ok:
        tstats = journal.ticker_win_rates()
        for ticker, df in frames.items():
            if ticker in portfolio.positions or len(df) < 2:
                continue
            row, prev = df.iloc[-1], df.iloc[-2]
            setup = entry_signal(row, prev)
            if setup is None:
                continue
            feats = feature_vector(row)
            feats["ticker_winrate"] = ticker_winrate(tstats, ticker)
            conf = brain.win_probability(feats)
            if brain.model is not None and conf < cfg.confidence_threshold:
                print(f"  skip {ticker} ({setup}): brain says only {conf:.0%} win chance")
                continue
            candidates.append((conf, ticker, setup, float(row["Close"]), feats))
    for conf, ticker, setup, price, feats in sorted(candidates, key=lambda c: -c[0]):
        pos = portfolio.open_position(ticker, setup, today, price, conf, feats, prices)
        if pos:
            print(f"  BUY  {ticker}: {setup} @ {pos.entry_price:.2f}, "
                  f"{pos.shares:.0f} shares, confidence {conf:.0%}")

    # persist state
    journal.save_state("cash", portfolio.cash)
    journal.save_state("positions", [vars(p) for p in portfolio.positions.values()])
    journal.save_state("last_paper_run", today)
    journal.save_state("last_prices", prices)

    equity = portfolio.equity(prices)
    journal.record_equity(today, equity, portfolio.cash, len(portfolio.positions))

    from .dashboard import render_dashboard
    print(f"Dashboard updated: {render_dashboard(cfg)}")
    print(f"\nCash: EUR {portfolio.cash:,.2f} | Open positions: "
          f"{len(portfolio.positions)} | Equity: EUR {equity:,.2f}")
    for t, pos in portfolio.positions.items():
        cur = prices.get(t, pos.entry_price)
        upnl = (cur - pos.entry_price) * pos.shares
        print(f"  {t:<10} {pos.shares:>5.0f} sh @ {pos.entry_price:.2f} "
              f"-> {cur:.2f}  unrealized EUR {upnl:+.2f}")
