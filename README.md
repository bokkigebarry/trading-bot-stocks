# Self-Learning Paper Trading Bot 🤖📈

A stock trading bot that trades **fake money** on real market prices and
learns from its own trade journal. Built together with Claude.

## How it works

- **Strategy:** mean-reversion dip buying — buy extreme 2-day selloffs
  (RSI(2) < 5) in stocks above their 200-day average, sell the bounce when
  price closes back over its 5-day average. Max 10 days per trade, 6×ATR
  catastrophe stop checked on the close. Long only.
- **Universe:** 45 stocks (20 Amsterdam, 25 US), max 3 positions,
  candidates ranked by ML confidence. No buying when market breadth is
  broken (less than half the universe above its 200-day average).
- **The brain:** a GradientBoosting classifier retrains on the SQLite trade
  journal as trades close, and skips setups that resemble past losers —
  including learning *which stocks* suit the strategy (`ticker_winrate`).
- **Costs:** Interactive Brokers-like fees simulated (€2/order + slippage).
  Degiro has no official API, which is why IBKR is the go-live target.
- The backtest is **walk-forward**: the model only ever knows the past,
  never the future, so the learning is honest.

## Commands

```
pip install -r requirements.txt

python -m bot train       # 6-year walk-forward backtest (the bot's training ground)
python -m bot paper       # one daily paper-trading step on live prices
python -m bot report      # performance + learning progress
python -m bot dashboard   # regenerate bot_data/dashboard.html
python -m bot day         # day-trading experiment (spoiler: it loses)
python -m bot reset       # wipe the journal, start from scratch
```

Tuning lives in [bot/config.py](bot/config.py): starting cash, universe,
exits, fees, and how strict the brain is (`confidence_threshold`).

## Cloud operation

A GitHub Actions workflow (`.github/workflows/paper.yml`) runs the daily
paper step every weekday at 22:00 UTC and commits the updated journal and
dashboard back to this repo. Open `bot_data/dashboard.html` for the equity
curve, open positions, recent trades, and per-stock P/L.

## Honest performance status

6-year walk-forward result: **about breakeven** (-0.4%/yr) after realistic
costs, with a reproducible random seed. The ticker-learning feature is
worth roughly +3.5%/yr versus not having it. This bot is a learning
project — real money is explicitly out of scope until it proves a durable
edge with months of live paper results.
