from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .backtest import run_backtest, walk_forward
from .models import PortfolioConfig, StrategyName
from .stress import bootstrap_drawdowns


def research_report(prices: pd.DataFrame, out: Path, config: PortfolioConfig | None = None) -> dict:
    config = config or PortfolioConfig()
    strategies: tuple[StrategyName, ...] = ("buy_hold", "equal_weight", "balanced", "defensive_rotation")
    results = {strategy: run_backtest(prices, strategy, config) for strategy in strategies}
    summary = pd.DataFrame({strategy: result.metrics for strategy, result in results.items()}).T
    wf = walk_forward(prices, strategies, config)
    stress = {strategy: bootstrap_drawdowns(result.equity) for strategy, result in results.items()}
    out.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out / "summary.csv")
    wf.to_csv(out / "walk_forward.csv", index=False)
    for strategy, result in results.items():
        result.equity.to_csv(out / f"{strategy}_equity.csv", header=True)
        result.trades.to_csv(out / f"{strategy}_trades.csv", index=False)
    payload = {"config": config.__dict__, "summary": summary.to_dict(orient="index"), "stress": stress}
    (out / "report.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload
