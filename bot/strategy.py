"""Candidate-signal generation: mean-reversion dip buying.

The idea (Connors-style RSI-2): in stocks that are in a long-term uptrend,
sharp short-term selloffs are usually noise and tend to bounce back within
days. We buy the dip and sell the bounce. The ML brain then decides which
dips are actually worth buying, based on past wins and losses.
"""
import pandas as pd


def entry_signal(row: pd.Series, prev: pd.Series) -> str | None:
    """Return a setup name if this bar produces a buy candidate, else None."""
    needed = ["sma5", "sma200", "rsi2", "rsi14", "bb_pos", "atr_pct"]
    if any(pd.isna(row[c]) for c in needed) or any(pd.isna(prev[c]) for c in needed):
        return None

    close = row["Close"]

    # Only buy dips in stocks whose long-term trend is up.
    if close <= row["sma200"]:
        return None

    # RSI-2 dip: extremely oversold short-term, price stretched below its
    # 5-day mean — the classic snap-back setup. The <5 threshold keeps only
    # the most washed-out dips: fewer trades, but a bigger edge per trade,
    # which is what lets each trade clear its broker costs.
    if row["rsi2"] < 5 and close < row["sma5"]:
        return "rsi2_dip"

    return None
