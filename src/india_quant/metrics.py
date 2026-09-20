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
