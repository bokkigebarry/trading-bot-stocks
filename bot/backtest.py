"""Walk-forward backtest = the bot's training ground.

The simulation moves through history one day at a time. The brain only
ever trains on trades that are already closed, then judges new ones —
so it genuinely learns as it goes, with no peeking into the future.
"""
import pandas as pd

from .brain import Brain
from .config import Config
from .features import add_indicators, feature_vector, ticker_winrate
from .journal import Journal
from .portfolio import Portfolio
from .strategy import entry_signal


def run_backtest(cfg: Config, data: dict[str, pd.DataFrame], journal: Journal,
                 verbose: bool = True) -> dict:
    frames = {t: add_indicators(df) for t, df in data.items()}

    # one shared daily calendar across all tickers
    all_dates = sorted(set().union(*[set(df.index) for df in frames.values()]))
    warmup = 210  # bars needed before indicators (sma200) are valid
    dates = all_dates[warmup:]

    portfolio = Portfolio(cfg)
    brain = Brain(cfg.min_trades_to_learn, cfg.retrain_every)
    equity_curve = []
    skipped_by_brain = 0
    retrain_count = 0

    for date in dates:
        prices = {}
        for ticker, df in frames.items():
            if date not in df.index:
                continue
            row = df.loc[date]
            prices[ticker] = float(row["Close"])

        # --- manage open positions ---
        for ticker in list(portfolio.positions):
            df = frames[ticker]
            if date not in df.index:
                continue
            row = df.loc[date]
            pos = portfolio.positions[ticker]
            pos.days_held += 1
            exit_hit = portfolio.check_exit(pos, float(row["Low"]),
                                            float(row["High"]), float(row["Close"]),
                                            float(row["sma5"]))
            if exit_hit:
                price, reason = exit_hit
                pos, pnl, pnl_pct = portfolio.close_position(ticker, date, price, reason)
                journal.record_trade(
                    "backtest", ticker, pos.setup, pos.entry_date, pos.entry_price,
                    date.date(), price, pos.shares, pnl, pnl_pct, reason,
                    pos.confidence, pos.features)
                if brain.maybe_retrain(journal):
                    retrain_count += 1
                    if verbose:
                        n = journal.closed_trade_count()
                        print(f"  [{date.date()}] brain retrained on {n} trades")

        # --- market breadth: how much of the universe is above its 200-day? ---
        above = total = 0
        for ticker, df in frames.items():
            if date not in df.index:
                continue
            row = df.loc[date]
            if not pd.isna(row["sma200"]):
                total += 1
                above += row["Close"] > row["sma200"]
        breadth_ok = total > 0 and above / total >= cfg.min_market_breadth

        # --- look for new entries: rank candidates, take the most confident ---
        candidates = []
        if breadth_ok:
            tstats = journal.ticker_win_rates()
            for ticker, df in frames.items():
                if date not in df.index or ticker in portfolio.positions:
                    continue
                i = df.index.get_loc(date)
                if i < 1:
                    continue
                row, prev = df.iloc[i], df.iloc[i - 1]
                setup = entry_signal(row, prev)
                if setup is None:
                    continue
                feats = feature_vector(row)
                feats["ticker_winrate"] = ticker_winrate(tstats, ticker)
                conf = brain.win_probability(feats)
                if brain.model is not None and conf < cfg.confidence_threshold:
                    skipped_by_brain += 1
                    continue
                candidates.append((conf, ticker, setup, float(row["Close"]), feats))
        for conf, ticker, setup, price, feats in sorted(candidates,
                                                        key=lambda c: -c[0]):
            portfolio.open_position(ticker, setup, date.date(), price,
                                    conf, feats, prices)

        equity_curve.append((date, portfolio.equity(prices)))

    # liquidate whatever is still open at the end
    last = dates[-1]
    for ticker in list(portfolio.positions):
        price = float(frames[ticker]["Close"].iloc[-1])
        pos, pnl, pnl_pct = portfolio.close_position(ticker, last, price, "end_of_test")
        journal.record_trade("backtest", ticker, pos.setup, pos.entry_date,
                             pos.entry_price, last.date(), price, pos.shares,
                             pnl, pnl_pct, "end_of_test", pos.confidence, pos.features)

    curve = pd.Series(dict(equity_curve))
    return {
        "equity_curve": curve,
        "final_equity": float(curve.iloc[-1]),
        "skipped_by_brain": skipped_by_brain,
        "retrain_count": retrain_count,
        "brain": brain,
    }
