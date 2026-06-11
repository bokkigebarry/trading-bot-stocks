"""Candidate-signal generation: mean reversion, both directions.

Long  (Connors-style RSI-2): in long-term uptrends, sharp short-term
selloffs are usually noise and bounce back within days — buy the dip.
Short (the mirror): in long-term downtrends, sharp short-term rallies
are usually noise and fade within days — short the rip.

The ML brain then decides which candidates are actually worth taking,
based on past wins and losses (it sees the direction as a feature).
"""
import pandas as pd


def entry_signal(row: pd.Series, prev: pd.Series) -> tuple[str, str] | None:
    """Return (setup, side) if this bar produces a candidate, else None."""
    needed = ["sma5", "sma200", "rsi2", "rsi14", "bb_pos", "atr_pct"]
    if any(pd.isna(row[c]) for c in needed) or any(pd.isna(prev[c]) for c in needed):
        return None

    close = row["Close"]

    # Long: extreme dip in an uptrend. The <5 threshold keeps only the most
    # washed-out dips: fewer trades, but a bigger edge per trade.
    if close > row["sma200"] and row["rsi2"] < 5 and close < row["sma5"]:
        return "rsi2_dip", "long"

    # Short: extreme rip in a downtrend — the exact mirror image.
    if close < row["sma200"] and row["rsi2"] > 95 and close > row["sma5"]:
        return "rsi2_rip", "short"

    return None
