"""Market-steal additions: the overfit guard (deflated Sharpe ratio + PBO
via CSCV — Bailey & López de Prado) and quantstats-parity tearsheet metrics.
The README's research rules already forbid selecting by in-sample return
alone; these make that rule a computed check instead of a promise."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from india_quant.data import make_fixture_prices
from india_quant.metrics import monthly_returns, omega_ratio, sortino_ratio, tail_ratio, var_95
from india_quant.overfit import deflated_sharpe, pbo


# ── tearsheet metrics ────────────────────────────────────────────────────────
def _equity(growth: float = 0.0004, days: int = 300, seed: int = 3) -> pd.Series:
    rng = np.random.default_rng(seed)
    returns = rng.normal(growth, 0.01, days)
    return pd.Series(np.cumprod(1 + returns), index=pd.bdate_range("2024-01-01", periods=days))


def test_sortino_penalizes_only_downside() -> None:
    equity = _equity()
    assert sortino_ratio(equity) > -5.0
    # downside dev ≤ total vol ⇒ sortino ≥ sharpe by construction here
    daily = equity.pct_change().dropna()
    from india_quant.metrics import performance_metrics  # sanity anchor

    sharpe = performance_metrics(equity, pd.DataFrame(), 1.0)["sharpe"]
    assert sortino_ratio(equity) >= sharpe - 1e-6


def test_omega_ratio_is_ratio_of_gains_to_losses() -> None:
    returns = np.array([0.02, 0.01, 0.03, -0.01, -0.02])
    equity = pd.Series(np.cumprod(1 + returns), index=pd.bdate_range("2024-01-01", periods=5))
    omega = omega_ratio(equity)
    # the first seeded return is consumed by pct_change (no prior day)
    assert omega == pytest.approx((0.01 + 0.03) / (0.01 + 0.02))


def test_tail_ratio_and_var_are_bounded() -> None:
    equity = _equity()
    daily = equity.pct_change().dropna()
    tail = tail_ratio(equity)
    assert tail > 0  # right-tail / left-tail magnitude ratio
    var = var_95(equity)
    assert -1.0 < var <= 0.0
    assert var == pytest.approx(min(np.quantile(daily, 0.05), 0.0))  # the honest quantile


def test_monthly_returns_table_is_shaped_and_bounded() -> None:
    table = monthly_returns(_equity(days=400))
    assert isinstance(table, pd.DataFrame)
    assert len(table) <= 26 and len(table) >= 12  # ~months rows
    assert set(table.columns) == {"year", "month", "return"}


# ── overfit guard ────────────────────────────────────────────────────────────
def test_deflated_sharpe_shrinks_when_many_trials_are_tried() -> None:
    equity = _equity()
    daily = equity.pct_change().dropna()
    alone = deflated_sharpe(daily, trials=1)
    crowded = deflated_sharpe(daily, trials=100)
    assert alone >= crowded  # more trials ⇒ harder to pass
    assert 0.0 < alone <= 1.0 and 0.0 < crowded <= 1.0


def test_deflated_sharpe_is_low_for_zero_skill() -> None:
    # a zero-skill strategy against a crowded trial count must not certify
    rng = np.random.default_rng(11)
    flat = pd.Series(rng.normal(0.0, 0.01, 400))
    assert deflated_sharpe(flat, trials=10) < 0.75
    assert deflated_sharpe(flat, trials=500) < 0.6  # harder hurdle, lower pass probability


def test_pbo_flags_lucky_in_sample_winners() -> None:
    rng = np.random.default_rng(5)
    # a strong IS streak that never repeats OOS: the IS winner keeps being
    # struck below the OOS median, so the panel is judged unreliable
    base = rng.normal(0.0005, 0.01, (400,))
    columns = {
        "s0": pd.Series(np.concatenate([base[:200] + 0.05, base[200:] - 0.05])),
        "s1": pd.Series(base + rng.normal(0, 0.002, 400)),
        "s2": pd.Series(base + rng.normal(0, 0.002, 400)),
        "s3": pd.Series(base + rng.normal(0, 0.002, 400)),
    }  # even panel: the IS-winner half is unambiguous
    value = pbo(pd.DataFrame(columns))
    assert 0.5 < value <= 1.0


def test_pbo_rewards_consistently_skilled_candidates() -> None:
    # the same two skilled candidates must top BOTH halves of every split
    rng = np.random.default_rng(9)
    columns = {
        "skilled_a": pd.Series(rng.normal(0.002, 0.003, 800)),
        "skilled_b": pd.Series(rng.normal(0.0015, 0.003, 800)),
        "noise_c": pd.Series(rng.normal(0.0002, 0.01, 800)),
        "noise_d": pd.Series(rng.normal(0.0002, 0.01, 800)),
    }
    assert pbo(pd.DataFrame(columns)) < 0.3


def test_pbo_identical_candidates_count_nothing() -> None:
    same = pd.Series(np.linspace(1, 2, 400) ** 1.001)
    frame = pd.DataFrame({"a": same, "b": same.copy(), "c": same.copy()})
    assert pbo(frame) == 0.0


def test_thin_data_is_rejected_not_faked() -> None:
    with pytest.raises(ValueError):
        deflated_sharpe(pd.Series([0.0] * 10), trials=3)
    with pytest.raises(ValueError):
        pbo(pd.DataFrame({"a": pd.Series(np.arange(30) / 100), "b": pd.Series(np.arange(30) / 99)}))
