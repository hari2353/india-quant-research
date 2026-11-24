"""The overfit guard: the standard answer to "the optimizer picked an
in-sample artifact" (Bailey & López de Prado 2014).

- ``deflated_sharpe``: the probability a strategy's Sharpe still clears the
  expected MAXIMUM Sharpe across T tried candidates — multiple-testing
  corrected, skew/kurtosis adjusted.
- ``pbo``: probability of backtest overfitting via CSCV — combinatorially
  split the joint return history, rank candidates in- and out-of-sample,
  count how often the IS-best rank below-median OOS.

Numpy + stdlib only (no scipy), deterministic, and thin data is refused
instead of reporting fake confidence.
"""

from __future__ import annotations

import itertools
import math
from statistics import NormalDist

import numpy as np
import pandas as pd

_MIN_OBS = 60
_NORM = NormalDist()


def _daily(returns: pd.Series | np.ndarray) -> np.ndarray:
    values = np.asarray(returns, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) < _MIN_OBS:
        raise ValueError(f"at least {_MIN_OBS} return observations are required, got {len(values)}")
    return values


def _moments(values: np.ndarray) -> tuple[float, float, float]:
    """Sharpe, bias-corrected skew, bias-corrected Pearson kurtosis."""
    n = len(values)
    mean, std = float(values.mean()), float(values.std(ddof=1))
    sr = mean / std if std else 0.0
    centered = values - mean
    m2 = float(np.mean(centered**2))
    if m2 <= 0:
        return sr, 0.0, 3.0
    m3 = float(np.mean(centered**3))
    m4 = float(np.mean(centered**4))
    g1 = m3 / m2**1.5
    g2 = m4 / m2**2 - 3.0
    skew = g1 * math.sqrt(n * (n - 1)) / (n - 2) if n > 2 else 0.0
    kurt = (((n + 1) * g2 + 6) * (n - 1)) / ((n - 2) * (n - 3)) + 3.0 if n > 3 else 3.0
    return sr, skew, max(kurt, 1.0 + 1e-9)


def _sr_hurdle(sr_std: float, trials: int) -> float:
    """The SR* hurdle: the expected maximum SR across T trials
    (Bailey & López de Prado 2014, eq. for the multiple-testing barrier,
    Euler–Mascheroni γ)."""
    if trials <= 1:
        return 0.0
    gamma = 0.5772156649015329
    z1 = _NORM.inv_cdf(1.0 - 1.0 / trials)
    z2 = _NORM.inv_cdf(1.0 - 1.0 / (trials * math.e))
    return sr_std * ((1 - gamma) * z1 + gamma * z2)


def deflated_sharpe(returns: pd.Series | np.ndarray, *, trials: int, freq: int = 252) -> float:
    """Probability (0..1] that the true SR clears the trials-adjusted hurdle.

    ``trials`` counts the candidates tried against the same data — the
    multiple-testing burden. The DSR statistic standardizes the gap between
    the observed SR and the expected maximum SR across trials, corrected
    for skew and kurtosis; returned as a one-sided probability.
    """
    values = _daily(returns)
    if trials < 1:
        raise ValueError("trials must be >= 1")
    sr, skew, kurt = _moments(values)
    # σ(SR) across trials, estimated from this trial's own sampling error
    sr_std = math.sqrt((1 - skew * sr + (kurt - 1) / 4.0 * sr * sr) / max(len(values) - 1, 1))
    sr_star = _sr_hurdle(sr_std, trials)
    denom = math.sqrt(max(1 - skew * sr + (kurt - 1) / 4.0 * sr * sr, 1e-12))
    dsr_stat = (sr - sr_star) * math.sqrt(max(len(values) - 1, 1)) / denom
    return float(_NORM.cdf(dsr_stat))


def _avg_rank(values: np.ndarray) -> np.ndarray:
    """Average ranks, 1-based (ties share the mean rank)."""
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    sorted_values = values[order]
    start = 0
    for index in range(1, len(values) + 1):
        if index == len(values) or sorted_values[index] != sorted_values[start]:
            ranks[order[start:index]] = (start + 1 + index) / 2.0
            start = index
    return ranks


def pbo(frame: pd.DataFrame, *, splits: int = 16) -> float:
    """Probability of backtest overfitting via CSCV over ``frame`` columns.

    ``frame``: one column per candidate, one row per (aligned) period
    return. Even ``splits``; every C(splits, splits/2) train/test
    partition; a combination counts toward overfitting when the
    in-sample-best candidates land below the out-of-sample median.
    """
    if frame.shape[1] < 2:
        raise ValueError("pbo needs at least two candidates")
    if splits < 4 or splits % 2:
        raise ValueError("splits must be an even number >= 4")
    values = frame.to_numpy(dtype=float)
    if len(values) < splits * 4:
        raise ValueError(f"pbo needs at least {splits * 4} rows, got {len(values)}")
    per = len(values) // splits
    if per < 4:
        raise ValueError(f"too few rows per split ({per}); add history")
    blocks = [values[i * per : (i + 1) * per] for i in range(splits)]
    k = values.shape[1]
    combos = list(itertools.combinations(range(splits), splits // 2))
    strikes = 0
    judged = 0
    for combo in combos:
        is_mask = np.zeros(splits, dtype=bool)
        is_mask[list(combo)] = True
        is_sharpes = []
        oos_sharpes = []
        for candidate in range(k):
            is_returns = np.concatenate([blocks[i] for i in range(splits) if is_mask[i]])[
                :, candidate
            ]
            oos_returns = np.concatenate([blocks[i] for i in range(splits) if not is_mask[i]])[
                :, candidate
            ]
            is_std = is_returns.std(ddof=1)
            oos_std = oos_returns.std(ddof=1)
            is_sharpes.append(float(is_returns.mean() / is_std) if is_std else 0.0)
            oos_sharpes.append(float(oos_returns.mean() / oos_std) if oos_std else 0.0)
        is_rank = _avg_rank(np.asarray(is_sharpes))  # k = best IS
        oos_rank = _avg_rank(np.asarray(oos_sharpes))  # k = best OOS
        relative = (oos_rank - 0.5) / k  # (0,1); near 1 = best OOS
        logits = np.log(relative / (1 - relative))
        best_is = is_rank > k / 2  # the IS winners...
        strikes += int(np.sum(logits[best_is] < 0))  # ...below the OOS median
        judged += int(best_is.sum())
    return float(strikes / judged) if judged else 0.0
