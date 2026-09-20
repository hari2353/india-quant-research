from __future__ import annotations

import numpy as np
import pandas as pd


def bootstrap_drawdowns(equity: pd.Series, simulations: int = 1000, seed: int = 7) -> dict[str, float]:
    """Block-bootstrap daily returns and report probabilistic drawdown risk."""
    returns = equity.pct_change().dropna().to_numpy()
    if len(returns) < 20:
        raise ValueError("at least 20 return observations are required")
    rng = np.random.default_rng(seed)
    block = max(2, min(20, len(returns) // 10))
    paths = []
    for _ in range(simulations):
        sampled: list[float] = []
        while len(sampled) < len(returns):
            start = int(rng.integers(0, len(returns) - block + 1))
            sampled.extend(returns[start:start + block])
        curve = np.cumprod(1 + np.asarray(sampled[:len(returns)]))
        paths.append(float((curve / np.maximum.accumulate(curve) - 1).min()))
    drawdowns = np.asarray(paths)
    return {
        "p05_max_drawdown": float(np.quantile(drawdowns, 0.05)),
        "median_max_drawdown": float(np.quantile(drawdowns, 0.50)),
        "p95_max_drawdown": float(np.quantile(drawdowns, 0.95)),
        "probability_loss": float(np.mean(drawdowns < -0.10)),
    }
