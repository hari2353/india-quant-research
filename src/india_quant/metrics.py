from __future__ import annotations

import numpy as np
import pandas as pd


def performance_metrics(equity: pd.Series, trades: pd.DataFrame, initial: float) -> dict[str, float]:
    equity = equity.dropna()
    daily = equity.pct_change().fillna(0.0)
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1 / 365.25)
    total = equity.iloc[-1] / initial - 1.0
    cagr = (equity.iloc[-1] / initial) ** (1 / years) - 1.0
    volatility = float(daily.std(ddof=1) * np.sqrt(252)) if len(daily) > 1 else 0.0
    sharpe = float((daily.mean() / daily.std(ddof=1)) * np.sqrt(252)) if daily.std(ddof=1) else 0.0
    drawdown = equity / equity.cummax() - 1.0
    max_drawdown = float(drawdown.min())
    turnover = float(trades["notional"].sum() / equity.mean()) if not trades.empty else 0.0
    return {
        "final_value": float(equity.iloc[-1]),
        "total_return": float(total),
        "cagr": float(cagr),
        "annualized_volatility": volatility,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "calmar": float(cagr / abs(max_drawdown)) if max_drawdown else 0.0,
        "turnover": turnover,
        "trade_count": float(len(trades)),
    }


def _daily_returns(equity: pd.Series) -> pd.Series:
    return equity.pct_change().dropna()


def sortino_ratio(equity: pd.Series, *, freq: int = 252, mar: float = 0.0) -> float:
    """Downside-deviation Sharpe: only returns below MAR count as risk."""
    daily = _daily_returns(equity)
    if daily.empty:
        return 0.0
    downside = daily[daily < mar] - mar
    ddev = float(np.sqrt(np.mean(downside**2))) if len(downside) else 0.0
    if not ddev:
        return 0.0
    return float((daily.mean() - mar) / ddev * np.sqrt(freq))


def omega_ratio(equity: pd.Series, *, mar: float = 0.0) -> float:
    """Gains above MAR divided by losses below MAR (probability-weighted)."""
    daily = _daily_returns(equity)
    gains = daily[daily > mar] - mar
    losses = mar - daily[daily <= mar]
    if losses.sum() == 0:
        return float("inf") if gains.sum() else 0.0
    return float(gains.sum() / losses.sum())


def tail_ratio(equity: pd.Series, *, quantile: float = 0.95) -> float:
    """Right-tail magnitude vs left-tail magnitude of the daily returns."""
    daily = _daily_returns(equity)
    if daily.empty:
        return 0.0
    right = abs(float(np.quantile(daily, quantile)))
    left = abs(float(np.quantile(daily, 1 - quantile)))
    return float(right / left) if left else 0.0


def var_95(equity: pd.Series, *, quantile: float = 0.05) -> float:
    """Historical daily Value-at-Risk as a non-positive loss fraction."""
    daily = _daily_returns(equity)
    if daily.empty:
        return 0.0
    return float(min(np.quantile(daily, quantile), 0.0))


def monthly_returns(equity: pd.Series) -> pd.DataFrame:
    """One row per calendar month: the compounded monthly return."""
    equity = equity.dropna()
    if equity.empty:
        return pd.DataFrame(columns=["year", "month", "return"])
    monthly = equity.resample("ME").last()
    start = float(equity.iloc[0])
    values = []
    prior = start
    for timestamp, value in monthly.items():
        values.append({"year": int(timestamp.year), "month": int(timestamp.month),
                       "return": float(value / prior - 1.0) if prior else 0.0})
        prior = float(value)
    return pd.DataFrame(values)
