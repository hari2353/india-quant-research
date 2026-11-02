import pandas as pd

from india_quant.models import PortfolioConfig
from india_quant.strategies import target_weights


def test_forecast_tilt_returns_valid_weights():
    prices = pd.DataFrame({"NIFTYBEES.NS": range(100, 400),
                           "GOLDBEES.NS": range(100, 400),
                           "LIQUIDBEES.NS": range(100, 400)},
                          index=pd.bdate_range("2020-01-01", periods=300))
    weights = target_weights(prices, "forecast_tilt", PortfolioConfig())
    assert weights.max() <= 0.70 + 1e-9
    assert weights.sum() <= 0.95 + 1e-9
    assert (weights >= 0).all()


def test_forecast_tilt_falls_back_to_balanced_shape():
    prices = pd.DataFrame({"a": range(100, 200)}, index=pd.bdate_range("2020-01-01", periods=100))
    weights = target_weights(prices, "forecast_tilt", PortfolioConfig())
    assert isinstance(weights, pd.Series)

