"""Performance reporting from the trade journal."""
import pandas as pd

from .journal import Journal


def summarize(trades: list[dict]) -> dict | None:
    if not trades:
        return None
    df = pd.DataFrame(trades)
    wins = df[df["pnl"] > 0]
    losses = df[df["pnl"] <= 0]
    gross_win = wins["pnl"].sum()
    gross_loss = abs(losses["pnl"].sum())
    return {
        "trades": len(df),
        "win_rate": len(wins) / len(df),
        "total_pnl": df["pnl"].sum(),
        "avg_win": wins["pnl"].mean() if len(wins) else 0.0,
        "avg_loss": losses["pnl"].mean() if len(losses) else 0.0,
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else float("inf"),
        "by_setup": df.groupby("setup")["pnl"].agg(["count", "sum", "mean"]),
        "by_exit": df.groupby("exit_reason")["pnl"].agg(["count", "sum"]),
    }


def print_report(journal: Journal, mode: str | None = None,
                 equity_curve: pd.Series | None = None,
                 starting_cash: float | None = None) -> None:
    trades = journal.all_trades(mode)
    s = summarize(trades)
    if s is None:
        print("No closed trades yet.")
        return

    print(f"\n=== Results ({mode or 'all'}) ===")
    print(f"Closed trades:   {s['trades']}")
    print(f"Win rate:        {s['win_rate']:.1%}")
    print(f"Total P/L:       EUR {s['total_pnl']:+,.2f}")
    print(f"Avg win:         EUR {s['avg_win']:+,.2f}")
    print(f"Avg loss:        EUR {s['avg_loss']:+,.2f}")
    print(f"Profit factor:   {s['profit_factor']:.2f}")

    if equity_curve is not None and starting_cash:
        final = float(equity_curve.iloc[-1])
        years = max((equity_curve.index[-1] - equity_curve.index[0]).days / 365.25, 0.1)
        cagr = (final / starting_cash) ** (1 / years) - 1
        peak = equity_curve.cummax()
        max_dd = ((equity_curve - peak) / peak).min()
        print(f"Final equity:    EUR {final:,.2f}  (started {starting_cash:,.0f})")
        print(f"Yearly return:   {cagr:+.1%}")
        print(f"Max drawdown:    {max_dd:.1%}")

    print("\nPer setup:")
    print(s["by_setup"].to_string())
    print("\nPer exit reason:")
    print(s["by_exit"].to_string())


def print_learning_progress(journal: Journal, mode: str = "backtest",
                            chunk: int = 50) -> None:
    """Show win rate over time — is the bot actually getting better?"""
    trades = journal.all_trades(mode)
    if len(trades) < chunk:
        return
    print(f"\n=== Learning curve (win rate per {chunk} trades, in order) ===")
    for i in range(0, len(trades) - chunk + 1, chunk):
        batch = trades[i:i + chunk]
        wr = sum(1 for t in batch if t["pnl"] > 0) / len(batch)
        pnl = sum(t["pnl"] for t in batch)
        bar = "#" * int(wr * 40)
        print(f"  trades {i + 1:>4}-{i + chunk:<4}  win {wr:5.1%}  "
              f"P/L {pnl:+9.2f}  {bar}")
