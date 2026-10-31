from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from .broker import (
    BrokerError,
    KiteBroker,
    LiveConfig,
    LiveLedger,
    build_trade_plan,
    execute_plan,
    load_plan,
    save_plan,
)
from .data import download_yahoo_daily, load_prices, save_prices
from .models import RESEARCH_UNIVERSE, PortfolioConfig
from .paper import PaperLedger
from .report import research_report


def main() -> None:
    parser = argparse.ArgumentParser(prog="india-quant")
    sub = parser.add_subparsers(dest="command", required=True)
    download = sub.add_parser("download")
    download.add_argument("--out", type=Path, default=Path("data/prices.csv"))
    download.add_argument("--years", type=int, default=10)
    backtest = sub.add_parser("backtest")
    backtest.add_argument("--prices", type=Path, required=True)
    backtest.add_argument("--out", type=Path, default=Path("reports"))
    paper = sub.add_parser("paper-run")
    paper.add_argument("--prices", type=Path, required=True)
    paper.add_argument("--db", type=Path, default=Path("paper/paper.db"))
    paper.add_argument("--out", type=Path, default=Path("paper/reports"))
    paper.add_argument("--date", type=str)
    paper.add_argument("--replay", action="store_true")
    analyze = sub.add_parser("paper-analyze")
    analyze.add_argument("--db", type=Path, default=Path("paper/paper.db"))
    analyze.add_argument("--out", type=Path, default=None)
    live_plan = sub.add_parser("live-plan")
    live_plan.add_argument("--prices", type=Path, required=True)
    live_plan.add_argument("--plan", type=Path, default=Path("live/plan.json"))
    live_plan.add_argument("--strategy", choices=["equal_weight", "balanced"], default="balanced")
    live_plan.add_argument("--date", type=str)
    approve = sub.add_parser("approve-plan")
    approve.add_argument("--plan", type=Path, required=True)
    approve.add_argument("--approval", type=Path, required=True)
    live_execute = sub.add_parser("live-execute")
    live_execute.add_argument("--plan", type=Path, required=True)
    live_execute.add_argument("--approval", type=Path, required=True)
    live_execute.add_argument("--db", type=Path, default=Path("live/live.db"))
    args = parser.parse_args()
    if args.command == "download":
        end = datetime.now(timezone.utc).date()
        prices = download_yahoo_daily(RESEARCH_UNIVERSE, end - timedelta(days=365 * args.years), end)
        save_prices(prices, args.out)
        print(f"saved {len(prices):,} rows to {args.out}")
    elif args.command == "backtest":
        payload = research_report(load_prices(args.prices), args.out, PortfolioConfig())
        for strategy, metrics in payload["summary"].items():
            print(f"{strategy}: CAGR={float(metrics['cagr']):.2%} maxDD={float(metrics['max_drawdown']):.2%} "
                  f"final=Rs {float(metrics['final_value']):,.0f}")
    elif args.command == "paper-run":
        prices = load_prices(args.prices)
        ledger = PaperLedger(args.db)
        try:
            strategies = ("equal_weight", "balanced")
            dates = sorted(prices["date"].unique()) if args.replay else [pd.Timestamp(args.date).normalize() if args.date else prices["date"].max()]
            for date_value in dates:
                for strategy in strategies:
                    result = ledger.process_date(prices, strategy, date_value, PortfolioConfig())
                    print(f"{result.date.date()} {strategy}: {result.status} {result.reason} "
                          f"equity=Rs {result.equity:,.2f} orders={result.order_count}")
            ledger.export(args.out, strategies)
        finally:
            ledger.close()
    elif args.command == "paper-analyze":
        ledger = PaperLedger(args.db)
        try:
            rejections = [dict(r) for r in ledger.error_analysis()]
            runs = [dict(r) for r in ledger.run_status()]
            for row in rejections:
                print(f"{row['strategy']}: rejected {row['reason']} x{row['count']}")
            print(f"runs: {len(runs)} ledgered")
            if args.out:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                args.out.write_text(json.dumps({"rejections": rejections, "runs": runs},
                                               indent=2, default=str), encoding="utf-8")
        finally:
            ledger.close()
    elif args.command == "live-plan":
        config = LiveConfig.from_env()
        try:
            broker = KiteBroker(config)
            plan = build_trade_plan(load_prices(args.prices), args.strategy, broker, config, args.date)
            save_plan(plan, args.plan)
            print(f"saved plan {args.plan} hash={plan.hash} orders={len(plan.orders)}")
            for order in plan.orders:
                print(f"{order.side} {order.quantity} {order.symbol} @ Rs {order.limit_price:.2f}")
        except BrokerError as exc:
            parser.error(str(exc))
    elif args.command == "approve-plan":
        plan = load_plan(args.plan)
        args.approval.parent.mkdir(parents=True, exist_ok=True)
        args.approval.write_text(plan.hash, encoding="utf-8")
        print(f"approved plan hash {plan.hash}")
    else:
        plan = load_plan(args.plan)
        config = LiveConfig.from_env()
        ledger = LiveLedger(args.db)
        try:
            broker = KiteBroker(config)
            results = execute_plan(plan, broker, ledger, config, args.approval)
            print(json.dumps(results, indent=2))
        except BrokerError as exc:
            parser.error(str(exc))
        finally:
            ledger.close()


if __name__ == "__main__":
    main()
