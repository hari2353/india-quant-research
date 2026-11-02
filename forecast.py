"""Time-series foundation model adapter for india-quant (T13 follow-up).

Provides zero-shot forecasts of a price series. TimesFM (Google, pip
`timesfm[torch]`) is the primary backend; Kronos (MIT, HuggingFace) is a
secondary backend guarded behind an import. If neither is available, a naive
last-value forecast is used so the pipeline never blocks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd


@dataclass
class Forecast:
    point: float          # point forecast for the next step
    lower: float          # lower quantile
    upper: float          # upper quantile
    model: str            # which backend produced it


def naive_forecast(series: pd.Series) -> Forecast:
    """Last-value fallback: point = last close, quantiles = +/- 1 std of returns."""
    last = float(series.iloc[-1])
    rets = series.pct_change().dropna()
    std = float(rets.std()) if len(rets) > 1 else 0.0
    return Forecast(point=last, lower=last * (1 - std), upper=last * (1 + std),
                    model="naive")


def timesfm_forecast(series: pd.Series, horizon: int = 1) -> Forecast:
    """Zero-shot forecast via TimesFM 2.5. Falls back to naive on any failure."""
    try:
        import timesfm
        model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
            "google/timesfm-2.5-200m-pytorch")
        model.compile(timesfm.ForecastConfig(
            max_context=min(512, len(series)), max_horizon=horizon,
            normalize_inputs=True, use_continuous_quantile_head=True,
            force_flip_invariance=True, infer_is_positive=True,
            fix_quantile_crossing=True))
        point, quantile = model.forecast(horizon, [series.to_numpy(dtype=float)])
        p = float(point[0, -1])
        lo = float(quantile[0, -1, 0]) if quantile.ndim == 3 else float(quantile[0, -1])
        hi = float(quantile[0, -1, -1]) if quantile.ndim == 3 else p
        return Forecast(point=p, lower=lo, upper=hi, model="timesfm-2.5")
    except Exception:
        return naive_forecast(series)


def forecast_series(series: pd.Series, backend: str = "auto") -> Forecast:
    """Dispatch to the requested backend; 'auto' prefers TimesFM then naive."""
    s = series.dropna().astype(float)
    if len(s) < 5:
        return naive_forecast(s)
    if backend == "naive":
        return naive_forecast(s)
    if backend == "timesfm":
        return timesfm_forecast(s)
    # auto
    try:
        import timesfm  # noqa: F401
        return timesfm_forecast(s)
    except Exception:
        return naive_forecast(s)


def forecast_signal(series: pd.Series, backend: str = "auto") -> float:
    """Return a signed strength in [-1, 1]: positive if forecast > last price."""
    f = forecast_series(series, backend=backend)
    last = float(series.iloc[-1])
    if last == 0:
        return 0.0
    delta = (f.point - last) / last
    return max(-1.0, min(1.0, delta * 10.0))

