import pandas as pd

from india_quant.models import PortfolioConfig
from india_quant.strategies import target_weights


def test_strategy_does_not_allocate_before_warmup():
    prices = pd.DataFrame({"a": range(100, 250), "b": range(100, 250)},
                          index=pd.bdate_range("2020-01-01", periods=150))
    weights = target_weights(prices, "defensive_rotation", PortfolioConfig())
    assert weights.sum() == 0


def test_weights_have_cash_buffer_and_cap():
    prices = pd.DataFrame({"a": range(100, 400), "b": range(100, 400), "c": range(100, 400)},
                          index=pd.bdate_range("2020-01-01", periods=300))
    weights = target_weights(prices, "defensive_rotation", PortfolioConfig())
    assert weights.max() <= 0.70 + 1e-9
    assert weights.sum() <= 0.95 + 1e-9
