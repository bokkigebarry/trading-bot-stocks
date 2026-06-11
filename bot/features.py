"""Technical indicators and the ML feature vector.

Every feature here is computed using ONLY past data (no lookahead),
so the same code is valid in backtests and live paper trading.
"""
import numpy as np
import pandas as pd

# Names of the features fed to the ML brain, in fixed order.
FEATURE_NAMES = [
    "rsi2", "rsi14", "sma5_dist", "sma20_dist", "sma50_dist", "sma200_dist",
    "macd_hist", "bb_pos", "atr_pct", "ret_5d", "ret_20d",
    "vol_ratio", "trend_up", "ticker_winrate", "is_short",
]


def ticker_winrate(stats: dict[str, tuple[int, float]], ticker: str,
                   prior_n: int = 5, prior_rate: float = 0.5) -> float:
    """The bot's own past win rate on this stock, shrunk toward 50% when
    there is little evidence — so the brain can learn which stocks suit
    the strategy without overreacting to a lucky first trade."""
    n, wr = stats.get(ticker, (0, prior_rate))
    return (wr * n + prior_rate * prior_n) / (n + prior_n)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Append indicator columns to an OHLCV frame."""
    out = df.copy()
    close = out["Close"]

    # Moving averages
    out["sma5"] = close.rolling(5).mean()
    out["sma20"] = close.rolling(20).mean()
    out["sma50"] = close.rolling(50).mean()
    out["sma200"] = close.rolling(200).mean()

    # RSI(14) — slow oversold/overbought; RSI(2) — fast dip detector
    delta = close.diff()
    for period, col in ((14, "rsi14"), (2, "rsi2")):
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - 100 / (1 + rs)
        # a window of only gains has loss=0: RSI is 100 by definition
        out[col] = rsi.where(~((loss == 0) & (gain > 0)), 100.0)

    # MACD histogram
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    out["macd_hist"] = macd - signal

    # Bollinger band position: 0 = at lower band, 1 = at upper band
    mid = out["sma20"]
    std = close.rolling(20).std()
    out["bb_pos"] = (close - (mid - 2 * std)) / (4 * std)

    # ATR as % of price (volatility)
    tr = pd.concat([
        out["High"] - out["Low"],
        (out["High"] - close.shift()).abs(),
        (out["Low"] - close.shift()).abs(),
    ], axis=1).max(axis=1)
    out["atr"] = tr.rolling(14).mean()
    out["atr_pct"] = out["atr"] / close

    # Momentum and volume
    out["ret_5d"] = close.pct_change(5)
    out["ret_20d"] = close.pct_change(20)
    out["vol_ratio"] = out["Volume"] / out["Volume"].rolling(20).mean()

    return out


def feature_vector(row: pd.Series) -> dict[str, float]:
    """The snapshot of market conditions the brain learns from."""
    close = row["Close"]
    return {
        "rsi2": row["rsi2"],
        "rsi14": row["rsi14"],
        "sma5_dist": close / row["sma5"] - 1,
        "sma20_dist": close / row["sma20"] - 1,
        "sma50_dist": close / row["sma50"] - 1,
        "sma200_dist": close / row["sma200"] - 1,
        "macd_hist": row["macd_hist"] / close,
        "bb_pos": row["bb_pos"],
        "atr_pct": row["atr_pct"],
        "ret_5d": row["ret_5d"],
        "ret_20d": row["ret_20d"],
        "vol_ratio": row["vol_ratio"],
        "trend_up": 1.0 if close > row["sma200"] else 0.0,
    }
