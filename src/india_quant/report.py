from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import run_backtest, walk_forward
from .models import PortfolioConfig, StrategyName
from .overfit import deflated_sharpe, pbo
from .stress import bootstrap_drawdowns


def research_report(prices: pd.DataFrame, out: Path, config: PortfolioConfig | None = None) -> dict:
    config = config or PortfolioConfig()
    strategies: tuple[StrategyName, ...] = (
        "buy_hold",
        "equal_weight",
        "balanced",
        "defensive_rotation",
        "forecast_tilt",
        "event_defensive",
    )
    results = {strategy: run_backtest(prices, strategy, config) for strategy in strategies}
    summary = pd.DataFrame({strategy: result.metrics for strategy, result in results.items()}).T
    wf = walk_forward(prices, strategies, config)
    stress = {strategy: bootstrap_drawdowns(result.equity) for strategy, result in results.items()}
    guard, guard_reason = _overfit_guard(results, strategies)
    out.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out / "summary.csv")
    wf.to_csv(out / "walk_forward.csv", index=False)
    for strategy, result in results.items():
        result.equity.to_csv(out / f"{strategy}_equity.csv", header=True)
        result.trades.to_csv(out / f"{strategy}_trades.csv", index=False)
    payload = {
        "config": config.__dict__,
        "summary": summary.to_dict(orient="index"),
        "stress": stress,
        "overfit": guard,
    }
    if guard_reason:
        payload["overfit_note"] = guard_reason
    (out / "report.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload


def _overfit_guard(results: dict, strategies: tuple[StrategyName, ...]) -> tuple[dict, str]:
    """The README's rule, computed: DSR per candidate, PBO across them.

    Thin history is omitted with a reason, never faked."""
    dsr: dict[str, float] = {}
    for strategy in strategies:
        equity = results[strategy].equity
        daily = equity.pct_change().dropna()
        if len(daily) < 60:
            return {"pbo": None, "deflated_sharpe": {}}, (
                f"overfit guard omitted: {len(daily)} daily observations for "
                f"{strategy} (< 60 required); add history"
            )
        dsr[strategy] = deflated_sharpe(daily, trials=len(strategies))
    joint = pd.DataFrame(
        {strategy: results[strategy].equity.pct_change().dropna() for strategy in strategies}
    ).dropna()
    if joint.shape[0] < 64:
        return {"pbo": None, "deflated_sharpe": dsr}, (
            f"pbo omitted: {joint.shape[0]} aligned daily observations (< 64 required)"
        )
    return {"pbo": pbo(joint), "deflated_sharpe": dsr}, ""


def tearsheet(
    prices: pd.DataFrame, strategy: StrategyName, out: Path, config: PortfolioConfig | None = None
) -> dict:
    """One candidate's quantstats-parity sheet as bounded Markdown."""
    from .metrics import monthly_returns, omega_ratio, sortino_ratio, tail_ratio, var_95

    result = run_backtest(prices, strategy, config)
    metrics = dict(result.metrics)
    daily = result.equity.pct_change().dropna()
    extras = {
        "sortino": sortino_ratio(result.equity),
        "omega": omega_ratio(result.equity),
        "tail_ratio": tail_ratio(result.equity),
        "var_95": var_95(result.equity),
        "deflated_sharpe": deflated_sharpe(daily, trials=1),
    }
    metrics.update(extras)
    monthly = monthly_returns(result.equity)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# tearsheet — {strategy}",
        "",
        "| metric | value |",
        "|---|---|",
    ]
    for key in (
        "final_value",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe",
        "deflated_sharpe",
        "sortino",
        "omega",
        "tail_ratio",
        "var_95",
        "max_drawdown",
        "calmar",
        "turnover",
        "trade_count",
    ):
        lines.append(f"| {key} | {metrics.get(key, float('nan')):.4f} |")
    lines += ["", "## monthly returns", "", "| year | month | return |", "|---|---|---|"]
    for _, row in monthly.tail(24).iterrows():
        lines.append(f"| {int(row['year'])} | {int(row['month'])} | {row['return']:.4f} |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"strategy": strategy, "metrics": metrics}
