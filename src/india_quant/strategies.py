from __future__ import annotations

import numpy as np
import pandas as pd

from .models import PortfolioConfig, StrategyName


def _cap_and_normalize(weights: pd.Series, config: PortfolioConfig) -> pd.Series:
    weights = weights.clip(lower=0.0)
    if weights.sum() == 0:
        return weights
    weights = weights / weights.sum() * (1.0 - config.min_cash_buffer)
    for _ in range(10):
        over = weights > config.max_asset_weight
        if not over.any():
            break
        excess = float((weights[over] - config.max_asset_weight).sum())
        weights[over] = config.max_asset_weight
        under = ~over
        if under.any() and weights[under].sum() > 0:
            weights[under] += excess * weights[under] / weights[under].sum()
    return weights


def target_weights(history: pd.DataFrame, strategy: StrategyName, config: PortfolioConfig) -> pd.Series:
    """Return weights based only on history ending before the execution date."""
    symbols = list(history.columns)
    if not symbols:
        return pd.Series(dtype=float)
    if strategy == "buy_hold":
        weights = pd.Series(0.0, index=symbols)
        primary = config.primary_symbol if config.primary_symbol in weights.index else symbols[0]
        weights[primary] = 1.0 - config.min_cash_buffer
        return weights
    if strategy == "equal_weight":
        return pd.Series((1.0 - config.min_cash_buffer) / len(symbols), index=symbols)
    if strategy == "balanced":
        target = {"NIFTYBEES.NS": 0.60, "GOLDBEES.NS": 0.20, "LIQUIDBEES.NS": 0.15}
        weights = pd.Series({symbol: target.get(symbol, 0.0) for symbol in symbols})
        return _cap_and_normalize(weights, config)

    if len(history) < 200:
        return pd.Series(0.0, index=symbols)
    returns = history.pct_change().dropna()
    momentum = history.iloc[-1] / history.iloc[-126] - 1.0
    trend_ok = history.iloc[-1] > history.iloc[-200:].mean()
    volatility = returns.iloc[-63:].std().replace(0, np.nan)
    score = momentum / volatility
    score = score.where(trend_ok, -np.inf).replace([np.inf, -np.inf], np.nan).dropna()
    if score.empty:
        return pd.Series(0.0, index=symbols)
    selected = score.nlargest(min(2, len(score)))
    positive = selected[selected > 0]
    if positive.empty:
        return pd.Series(0.0, index=symbols)
    inverse_vol = 1.0 / volatility[positive.index]
    weights = pd.Series(0.0, index=symbols)
    weights.loc[positive.index] = inverse_vol / inverse_vol.sum()
    return _cap_and_normalize(weights, config)
