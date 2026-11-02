import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock

from forecast import naive_forecast, forecast_series, forecast_signal


def test_naive_forecast_shape():
    s = pd.Series([100.0, 101.0, 102.0, 103.0])
    f = naive_forecast(s)
    assert f.model == "naive"
    assert f.point == 103.0
    assert f.lower <= f.point <= f.upper


def test_forecast_signal_bounded():
    s = pd.Series([100.0, 100.0, 100.0, 110.0])
    v = forecast_signal(s, backend="naive")
    assert -1.0 <= v <= 1.0


def test_forecast_series_falls_back_to_naive_when_timesfm_missing():
    with patch.dict("sys.modules", {"timesfm": None}):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        f = forecast_series(s, backend="auto")
        assert f.model == "naive"


def test_forecast_series_backend_naive_explicit():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    f = forecast_series(s, backend="naive")
    assert f.model == "naive"
    assert f.point == 5.0

