from pathlib import Path

import pandas as pd

from india_quant.data import (
    _apply_split_adjustments,
    clean_price_anomalies,
    load_prices,
    make_fixture_prices,
    save_prices,
    to_panel,
    validate_price_continuity,
)


def test_split_adjustment_removes_price_discontinuity():
    prices = pd.DataFrame({"open": [100.0, 10.0], "high": [100.0, 10.0], "low": [100.0, 10.0],
                           "close": [100.0, 10.0], "adj_close": [100.0, 10.0]},
                          index=pd.to_datetime(["2020-01-01", "2020-01-02"]))
    adjusted = _apply_split_adjustments(
        prices,
        {"split": {"date": int(pd.Timestamp("2020-01-02").timestamp()), "numerator": 10,
                    "denominator": 1}},
    )
    assert adjusted.loc[pd.Timestamp("2020-01-01"), "close"] == 10


def test_isolated_bad_print_is_repaired():
    frame = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=3), "symbol": ["X"] * 3,
                          "open": [100.0, 10.0, 102.0], "high": [100.0, 10.0, 102.0],
                          "low": [100.0, 10.0, 102.0], "close": [100.0, 10.0, 102.0],
                          "adj_close": [100.0, 10.0, 102.0]})
    cleaned = clean_price_anomalies(frame)
    assert 10.0 < cleaned.loc[1, "close"] < 102.0


def test_short_bad_print_run_is_repaired():
    frame = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=4), "symbol": ["X"] * 4,
                          "open": [100.0, 10.0, 11.0, 102.0], "high": [100.0, 10.0, 11.0, 102.0],
                          "low": [100.0, 10.0, 11.0, 102.0], "close": [100.0, 10.0, 11.0, 102.0],
                          "adj_close": [100.0, 10.0, 11.0, 102.0]})
    cleaned = clean_price_anomalies(frame)
    validate_price_continuity(cleaned)
    assert cleaned.loc[1, "close"] > 40.0


def test_fixture_is_wide_and_round_trips(tmp_path: Path):
    prices = make_fixture_prices(250)
    path = tmp_path / "prices.csv"
    save_prices(prices, path)
    loaded = load_prices(path)
    panel = to_panel(loaded)
    assert set(panel.columns) == {"NIFTYBEES.NS", "GOLDBEES.NS", "LIQUIDBEES.NS"}
    assert len(loaded) == len(prices)
