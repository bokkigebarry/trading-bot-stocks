"""Market data download and caching via Yahoo Finance."""
import os
import pandas as pd
import yfinance as yf


def get_history(ticker: str, years: int, cache_dir: str, refresh: bool = False) -> pd.DataFrame:
    """Daily OHLCV history for one ticker, cached on disk as parquet/csv."""
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{ticker.replace('.', '_')}.csv")

    if not refresh and os.path.exists(cache_file):
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        if not df.empty:
            return df

    df = yf.download(ticker, period=f"{years}y", interval="1d",
                     auto_adjust=True, progress=False)
    if df is None or df.empty:
        return pd.DataFrame()

    # yfinance sometimes returns MultiIndex columns even for one ticker
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df.to_csv(cache_file)
    return df


def load_universe(tickers: list[str], years: int, cache_dir: str,
                  refresh: bool = False) -> dict[str, pd.DataFrame]:
    """Load history for all tickers, skipping any that fail."""
    data = {}
    for t in tickers:
        df = get_history(t, years, cache_dir, refresh=refresh)
        if len(df) > 250:  # need at least ~1 year of bars
            data[t] = df
        else:
            print(f"  ! skipping {t}: no/insufficient data")
    return data
