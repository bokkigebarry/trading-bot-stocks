"""Central configuration for the paper-trading bot."""
from dataclasses import dataclass, field


# Tickers the bot watches. Mix of Amsterdam (.AS suffix) and large US stocks.
# A wide universe matters: the bot ranks all dip candidates by confidence and
# only takes the best few, so more tickers = more selective entries.
DEFAULT_UNIVERSE = [
    # Amsterdam (AEX/AMX)
    "ASML.AS", "ADYEN.AS", "INGA.AS", "PHIA.AS", "AD.AS",
    "HEIA.AS", "UNA.AS", "KPN.AS", "BESI.AS", "ASM.AS",
    "WKL.AS", "RAND.AS", "AKZA.AS", "MT.AS", "NN.AS",
    "ABN.AS", "AGN.AS", "ASRNL.AS", "IMCD.AS", "AALB.AS",
    # US large caps
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL",
    "META", "TSLA", "AMD", "JPM", "V",
    "MA", "KO", "PEP", "JNJ", "PG",
    "XOM", "WMT", "HD", "NFLX", "COST",
    "ORCL", "BAC", "DIS", "CSCO", "INTC",
]


@dataclass
class Config:
    universe: list[str] = field(default_factory=lambda: list(DEFAULT_UNIVERSE))

    # Paper portfolio
    starting_cash: float = 1_000.0           # EUR of fake money (small-account reality)
    max_positions: int = 3                   # fewer, bigger slices: fixed fees weigh less

    # Interactive Brokers-like costs (EUR). Flat fee per order + slippage.
    # (IBKR tiered: ~EUR 1.25 min on AEX, ~USD 1 on US stocks — 2.0 is conservative.)
    commission_per_order: float = 2.0
    slippage_pct: float = 0.0005             # 0.05% price slip on fills

    # Exit rules (mean reversion: sell the bounce, not a fixed target).
    # The 10-day time exit is the real risk control; the ATR stop is only a
    # catastrophe brake (checked on the close — tighter stops kept selling
    # the bottom of the very dips we bought, in every test).
    atr_stop_mult: float = 6.0               # catastrophe stop: entry - 6x ATR
    max_holding_days: int = 10               # bounce didn't come -> get out

    # Learning (the "brain")
    min_trades_to_learn: int = 30            # need this many journaled trades before ML kicks in
    retrain_every: int = 10                  # retrain after every N new closed trades
    confidence_threshold: float = 0.60       # only take trades the model rates >60% win chance

    # Market regime: fraction of the universe above its own 200-day average.
    # Strong breadth -> dips get bought (longs). Weak breadth -> the whole
    # market is falling, so rips get shorted instead (shorts).
    min_market_breadth: float = 0.5
    allow_shorts: bool = True                # set False to go long-only again

    # Data
    history_years: int = 6
    db_path: str = "bot_data/journal.db"
    cache_dir: str = "bot_data/cache"

    # Day-trading experiment (opening range breakout, 5-minute bars,
    # US stocks only, always flat by the close). Separate journal/brain:
    # intraday patterns are a different world from daily dips.
    day_db_path: str = "bot_data/journal_day.db"
    day_or_bars: int = 6                     # opening range = first 6 x 5min = 30 min
    day_target_rr: float = 2.0               # profit target = entry + 2x opening range
    day_min_range_pct: float = 0.003         # skip too-quiet opens (target < costs)
    day_max_range_pct: float = 0.03          # skip chaotic opens (news, earnings)
