import numpy as np
import pandas as pd
import pytest

from india_quant.backtest import run_backtest
from india_quant.models import PortfolioConfig
from india_quant.strategies import target_weights


def _history(last: str, days: int = 260) -> pd.DataFrame:
    index = pd.bdate_range(end=last, periods=days)
    return pd.DataFrame(
        {
            "NIFTYBEES.NS": np.linspace(250.0, 260.0, days),
            "GOLDBEES.NS": np.linspace(70.0, 72.0, days),
            "LIQUIDBEES.NS": np.full(days, 1000.0),
        },
        index=index,
    )


def test_event_window_shifts_equity_into_liquid():
    config = PortfolioConfig()
    near = target_weights(_history("2026-01-30"), "event_defensive", config)
    calm = target_weights(_history("2026-03-16"), "event_defensive", config)
    baseline = target_weights(_history("2026-03-16"), "balanced", config)
    # as_of 2026-01-31 sees the Feb 1 Budget and Feb 6 MPC: 20% of the
    # NIFTYBEES sleeve moves to LIQUIDBEES, gold untouched.
    assert near["NIFTYBEES.NS"] == pytest.approx(0.8 * calm["NIFTYBEES.NS"])
    assert near["GOLDBEES.NS"] == pytest.approx(calm["GOLDBEES.NS"])
    assert near["LIQUIDBEES.NS"] > calm["LIQUIDBEES.NS"]
    assert near.sum() == pytest.approx(calm.sum())
    assert near.max() <= config.max_asset_weight + 1e-9
    # Outside the event window the strategy is exactly balanced.
    assert calm.sort_index().equals(baseline.sort_index())


def test_event_strategy_needs_no_warmup_and_fires_on_mpc_window():
    # 30-day history ending 2026-02-04: as_of 2026-02-05 sees the Feb 6 MPC.
    near = target_weights(_history("2026-02-04", days=30), "event_defensive", PortfolioConfig())
    assert not near.empty
    # The cap/normalize pass is identity here because target weights already
    # sum to 1 - min_cash_buffer (0.95), so the shifted sleeve is exact.
    assert near["NIFTYBEES.NS"] == pytest.approx(0.48)
    assert near["LIQUIDBEES.NS"] == pytest.approx(0.27)
    assert near["GOLDBEES.NS"] == pytest.approx(0.20)


def test_backtest_event_defensive_diverges_from_balanced_in_event_month():
    dates = pd.bdate_range("2025-11-03", "2026-03-31")
    rows = []
    for symbol, level in (("NIFTYBEES.NS", 250.0), ("GOLDBEES.NS", 70.0), ("LIQUIDBEES.NS", 1000.0)):
        path = level * (1.0 + 0.0002 * np.arange(len(dates)))
        rows.append(pd.DataFrame({"date": dates, "symbol": symbol, "open": path, "adj_close": path}))
    prices = pd.concat(rows, ignore_index=True)
    config = PortfolioConfig()
    defensive = run_backtest(prices, "event_defensive", config)
    balanced = run_backtest(prices, "balanced", config)
    # The Jan-30 rebalance date falls inside the Feb 1 Budget / Feb 6 MPC window.
    assert not defensive.weights["NIFTYBEES.NS"].equals(balanced.weights["NIFTYBEES.NS"])
    assert (defensive.equity > 0).all() and (balanced.equity > 0).all()
    first = run_backtest(prices, "event_defensive", config)
    assert first.equity.equals(defensive.equity)
