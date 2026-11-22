"""Risk metrics for quant research (cross-pollinated from microsoft/qlib).

Pure-Python, dependency-free risk measures over a return series. Returns are
treated as per-period (e.g. daily) returns; annualization is left to the
caller so the functions stay honest about their inputs.
"""
from __future__ import annotations

import math


def _require_non_empty(values: list[float], name: str = "returns") -> None:
    if not values:
        raise ValueError(f"{name} must be non-empty")


def sharpe(returns: list[float], *, risk_free: float = 0.0) -> float:
    _require_non_empty(returns)
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    std = math.sqrt(variance)
    if std == 0:
        return 0.0
    return round((mean - risk_free) / std, 6)


def sortino(returns: list[float], *, risk_free: float = 0.0) -> float:
    _require_non_empty(returns)
    mean = sum(returns) / len(returns)
    downside = [min(r - risk_free, 0.0) for r in returns]
    downside_var = sum(v * v for v in downside) / len(returns)
    downside_std = math.sqrt(downside_var)
    if downside_std == 0:
        return 0.0
    return round((mean - risk_free) / downside_std, 6)


def max_drawdown(equity: list[float]) -> float:
    _require_non_empty(equity, "equity")
    peak = equity[0]
    worst = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            drawdown = (peak - value) / peak
            worst = max(worst, drawdown)
    return round(worst, 6)


def var(returns: list[float], *, level: float = 0.95) -> float:
    _require_non_empty(returns)
    if not 0.0 < level < 1.0:
        raise ValueError("level must be in (0, 1)")
    ordered = sorted(returns)
    index = max(0, math.ceil(len(ordered) * (1 - level)) - 1)
    return round(ordered[index], 6)


def cvar(returns: list[float], *, level: float = 0.95) -> float:
    _require_non_empty(returns)
    if not 0.0 < level < 1.0:
        raise ValueError("level must be in (0, 1)")
    threshold = var(returns, level=level)
    tail = [r for r in returns if r <= threshold]
    if not tail:
        return threshold
    return round(sum(tail) / len(tail), 6)
