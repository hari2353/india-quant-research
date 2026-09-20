import pandas as pd

from india_quant.metrics import performance_metrics
from india_quant.stress import bootstrap_drawdowns


def test_metrics_include_drawdown_and_cagr():
    equity = pd.Series([100, 110, 99, 120], index=pd.date_range("2020-01-01", periods=4))
    metrics = performance_metrics(equity, pd.DataFrame(columns=["notional"]), 100)
    assert metrics["max_drawdown"] < 0
    assert metrics["final_value"] == 120


def test_bootstrap_is_reproducible():
    equity = pd.Series((1.001 ** i for i in range(100)), index=pd.date_range("2020-01-01", periods=100))
    assert bootstrap_drawdowns(equity, simulations=100, seed=7) == bootstrap_drawdowns(equity, simulations=100, seed=7)
