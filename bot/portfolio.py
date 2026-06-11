"""Paper portfolio: fake money, realistic Interactive Brokers-like costs."""
from dataclasses import dataclass, field

from .config import Config


@dataclass
class Position:
    ticker: str
    setup: str
    entry_date: str
    entry_price: float       # fill price incl. slippage
    shares: float
    stop_price: float        # disaster stop, ATR-based
    confidence: float
    features: dict
    days_held: int = 0


@dataclass
class Portfolio:
    cfg: Config
    cash: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)

    def __post_init__(self):
        if self.cash == 0.0:
            self.cash = self.cfg.starting_cash

    def equity(self, prices: dict[str, float]) -> float:
        total = self.cash
        for t, pos in self.positions.items():
            total += pos.shares * prices.get(t, pos.entry_price)
        return total

    def can_open(self) -> bool:
        return len(self.positions) < self.cfg.max_positions

    def position_size(self, price: float, prices: dict[str, float]) -> float:
        """Equal slices of equity; the bounce/time exit is the real risk control."""
        max_value = min(self.equity(prices) / self.cfg.max_positions,
                        self.cash - self.cfg.commission_per_order)
        if max_value <= 0:
            return 0.0
        return float(int(max_value / price))  # whole shares, like a real broker

    def open_position(self, ticker, setup, date, price, confidence, features,
                      prices: dict[str, float]) -> Position | None:
        if ticker in self.positions or not self.can_open():
            return None
        fill = price * (1 + self.cfg.slippage_pct)
        # disaster stop scaled to the stock's own volatility (ATR)
        atr_pct = float(features.get("atr_pct") or 0.02)
        stop = fill * (1 - self.cfg.atr_stop_mult * atr_pct)
        shares = self.position_size(fill, prices)
        if shares < 1:
            return None
        cost = shares * fill + self.cfg.commission_per_order
        if cost > self.cash:
            return None
        self.cash -= cost
        pos = Position(ticker, setup, str(date), fill, shares, stop,
                       confidence, features)
        self.positions[ticker] = pos
        return pos

    def close_position(self, ticker: str, date, price: float,
                       reason: str) -> tuple[Position, float, float]:
        pos = self.positions.pop(ticker)
        fill = price * (1 - self.cfg.slippage_pct)
        proceeds = pos.shares * fill - self.cfg.commission_per_order
        cost_basis = pos.shares * pos.entry_price + self.cfg.commission_per_order
        pnl = proceeds - cost_basis
        pnl_pct = pnl / cost_basis
        self.cash += proceeds
        return pos, pnl, pnl_pct

    def check_exit(self, pos: Position, low: float, high: float,
                   close: float, sma5: float) -> tuple[float, str] | None:
        """Decide whether today's bar triggers an exit. Returns (price, reason)."""
        # disaster stop on the close: intraday wicks below the stop are the
        # noise we're trading on, not a reason to sell at the bottom
        if close <= pos.stop_price:
            return close, "stop_loss"
        # mean reversion: the bounce happened once price closes back
        # above its 5-day average — take the money and move on
        if sma5 == sma5 and close > sma5:  # sma5==sma5 filters NaN
            return close, "bounce_exit"
        if pos.days_held >= self.cfg.max_holding_days:
            return close, "time_exit"
        return None
