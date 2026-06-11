"""Command-line interface.

  python -m bot train     -- learn from years of history (walk-forward backtest)
  python -m bot paper     -- one daily paper-trading step on live prices
  python -m bot report    -- performance + what the brain has learned
  python -m bot reset     -- wipe the journal and start learning from scratch
"""
import argparse
import os

from .config import Config
from .data import load_universe
from .journal import Journal


def cmd_train(cfg: Config, refresh: bool):
    from .backtest import run_backtest
    from .report import print_learning_progress, print_report

    print(f"Downloading {cfg.history_years}y of history for "
          f"{len(cfg.universe)} tickers...")
    data = load_universe(cfg.universe, cfg.history_years, cfg.cache_dir,
                         refresh=refresh)
    print(f"Loaded {len(data)} tickers. Running walk-forward simulation...\n")

    journal = Journal(cfg.db_path)
    result = run_backtest(cfg, data, journal)

    print(f"\nBrain retrained {result['retrain_count']} times during the run, "
          f"skipped {result['skipped_by_brain']} low-confidence setups.")
    print_report(journal, "backtest", result["equity_curve"], cfg.starting_cash)
    print_learning_progress(journal, "backtest")

    lessons = result["brain"].lessons()
    if lessons:
        print("\n=== What the brain learned to look at (feature importance) ===")
        for name, imp in lessons:
            print(f"  {name:<12} {'#' * int(imp * 100)} {imp:.0%}")


def cmd_paper(cfg: Config):
    from .paper import run_paper_day
    run_paper_day(cfg)


def cmd_day(cfg: Config, refresh: bool):
    from .daytrade import run_daytrade
    run_daytrade(cfg, refresh)


def cmd_dashboard(cfg: Config):
    from .dashboard import render_dashboard
    path = render_dashboard(cfg)
    print(f"Dashboard written to {path} — open it in your browser.")


def cmd_report(cfg: Config):
    from .report import print_learning_progress, print_report
    journal = Journal(cfg.db_path)
    print_report(journal, None)
    print_learning_progress(journal, "backtest")


def cmd_reset(cfg: Config):
    if os.path.exists(cfg.db_path):
        os.remove(cfg.db_path)
        print("Journal wiped. The bot starts learning from scratch.")
    else:
        print("Nothing to reset.")


def main():
    parser = argparse.ArgumentParser(prog="bot")
    sub = parser.add_subparsers(dest="command", required=True)
    p_train = sub.add_parser("train", help="learn from historical data")
    p_train.add_argument("--refresh", action="store_true",
                         help="re-download market data instead of using cache")
    sub.add_parser("paper", help="daily paper-trading step with live prices")
    p_day = sub.add_parser("day", help="day-trading experiment (ORB, 5-min bars)")
    p_day.add_argument("--refresh", action="store_true",
                       help="re-download intraday data instead of using cache")
    sub.add_parser("report", help="show performance and learning progress")
    sub.add_parser("dashboard", help="generate the HTML dashboard")
    sub.add_parser("reset", help="wipe the journal and start over")
    args = parser.parse_args()

    cfg = Config()
    if args.command == "train":
        cmd_train(cfg, args.refresh)
    elif args.command == "paper":
        cmd_paper(cfg)
    elif args.command == "day":
        cmd_day(cfg, args.refresh)
    elif args.command == "report":
        cmd_report(cfg)
    elif args.command == "dashboard":
        cmd_dashboard(cfg)
    elif args.command == "reset":
        cmd_reset(cfg)


if __name__ == "__main__":
    main()
