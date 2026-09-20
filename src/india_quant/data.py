from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd

PRICE_COLUMNS = ["open", "high", "low", "close", "adj_close"]


def _apply_split_adjustments(frame: pd.DataFrame, events: dict) -> pd.DataFrame:
    """Make historical OHLC prices continuous across stock splits."""
    adjusted = frame.copy()
    for event in events.values():
        event_date = pd.to_datetime(int(event["date"]), unit="s").normalize()
        numerator = float(event["numerator"])
        denominator = float(event["denominator"])
        if numerator <= 0 or denominator <= 0:
            raise ValueError("split ratios must be positive")
        historical = adjusted.index < event_date
        adjusted.loc[historical, PRICE_COLUMNS] *= denominator / numerator
    return adjusted


def clean_price_anomalies(frame: pd.DataFrame) -> pd.DataFrame:
    """Repair isolated bad prints that immediately revert on the next session.

    This does not infer a trading signal. It protects research from a known data-quality failure mode where an
    ETF print is off by a factor for exactly one day and would otherwise create a fictional drawdown.
    """
    cleaned = frame.copy()
    for symbol, group in cleaned.groupby("symbol", sort=False):
        ordered = group.sort_values("date")
        close = ordered["close"].astype(float)
        bad_positions: set[int] = set()
        values = close.to_numpy()
        # A split-like provider error can last for a few sessions. Only repair a short run that returns to
        # approximately the pre-error level; a genuine crash remains untouched because it does not revert.
        for start in range(len(values) - 2):
            base = values[start]
            for end in range(start + 2, min(start + 5, len(values))):
                future = values[end]
                interior = values[start + 1:end]
                if not 0.5 <= future / base <= 2.0:
                    continue
                low_factor = (interior / base < 0.4).all()
                high_factor = (interior / base > 2.5).all()
                if low_factor or high_factor:
                    bad_positions.update(range(start + 1, end))
                    break
        sorted_positions = sorted(bad_positions)
        blocks: list[list[int]] = []
        for row_position in sorted_positions:
            if not blocks or row_position != blocks[-1][-1] + 1:
                blocks.append([row_position])
            else:
                blocks[-1].append(row_position)
        for block in blocks:
            if block[0] == 0 or block[-1] == len(ordered) - 1:
                continue
            before = ordered.iloc[block[0] - 1][PRICE_COLUMNS].to_numpy(dtype=float)
            after = ordered.iloc[block[-1] + 1][PRICE_COLUMNS].to_numpy(dtype=float)
            replacement = (before + after) / 2.0
            for row_position in block:
                position = ordered.index[row_position]
                cleaned.loc[position, PRICE_COLUMNS] = replacement
    return cleaned


def validate_price_continuity(prices: pd.DataFrame, max_abs_return: float = 0.30) -> None:
    """Fail closed when a cleaned research dataset still contains an extreme one-day discontinuity."""
    ordered = prices.sort_values(["symbol", "date"])
    returns = ordered.groupby("symbol")["close"].pct_change().dropna()
    if returns.abs().max() > max_abs_return:
        raise ValueError("price data contains an unresolved discontinuity")


def download_yahoo_daily(symbols: tuple[str, ...], start: date, end: date) -> pd.DataFrame:
    """Download adjusted daily OHLC data through Yahoo's public chart endpoint.

    This adapter is for personal research only. The caller is responsible for checking provider terms and
    using a licensed feed for live trading or redistribution.
    """
    frames: list[pd.DataFrame] = []
    period1 = int(datetime.combine(start, datetime.min.time()).timestamp())
    period2 = int(datetime.combine(end + timedelta(days=1), datetime.min.time()).timestamp())
    for symbol in symbols:
        url = (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{quote(symbol)}?period1={period1}&period2={period2}&interval=1d&events=div%2Csplits"
        )
        request = Request(url, headers={"User-Agent": "india-quant-research/0.1"})
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
        result = payload["chart"]["result"]
        if not result:
            raise ValueError(f"Yahoo returned no data for {symbol}")
        chart = result[0]
        quote_data = chart["indicators"]["quote"][0]
        adjusted = chart["indicators"].get("adjclose", [{"adjclose": quote_data["close"]}])[0]["adjclose"]
        frame = pd.DataFrame(
            {
                "open": quote_data["open"],
                "high": quote_data["high"],
                "low": quote_data["low"],
                "close": quote_data["close"],
                "adj_close": adjusted,
                "volume": quote_data["volume"],
            },
            index=pd.to_datetime(chart["timestamp"], unit="s", utc=True).tz_convert(None).normalize(),
        )
        frame = _apply_split_adjustments(frame, chart.get("events", {}).get("splits", {}))
        frame["symbol"] = symbol
        frames.append(frame)
    combined = pd.concat(frames).reset_index(names="date")
    combined = clean_price_anomalies(combined)
    combined = combined.dropna(subset=["open", "close", "adj_close"])
    validate_price_continuity(combined)
    return combined.sort_values(["date", "symbol"]).reset_index(drop=True)


def save_prices(prices: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prices.to_csv(path, index=False)


def load_prices(path: Path) -> pd.DataFrame:
    prices = pd.read_csv(path, parse_dates=["date"])
    required = {"date", "symbol", "open", "close", "adj_close"}
    missing = required.difference(prices.columns)
    if missing:
        raise ValueError(f"price file missing columns: {sorted(missing)}")
    prices["date"] = pd.to_datetime(prices["date"]).dt.normalize()
    prices = clean_price_anomalies(prices)
    validate_price_continuity(prices)
    return prices.sort_values(["date", "symbol"]).reset_index(drop=True)


def to_panel(prices: pd.DataFrame, column: str = "adj_close") -> pd.DataFrame:
    panel = prices.pivot(index="date", columns="symbol", values=column).sort_index()
    return panel.ffill().dropna(how="all")


def make_fixture_prices(days: int = 800) -> pd.DataFrame:
    """Create deterministic prices for tests without network access."""
    index = pd.bdate_range("2020-01-01", periods=days)
    n = len(index)
    t = pd.Series(range(n), index=index, dtype=float)
    equity = 100 * (1 + 0.00025 + 0.008 * ((t % 31) == 0)).cumprod()
    gold = 100 * (1 + 0.00012 + 0.003 * ((t % 47) == 0)).cumprod()
    liquid = pd.Series(100 * (1 + 0.00004) ** pd.Series(range(n), dtype=float).to_numpy(), index=index)
    rows = []
    for symbol, series in (("NIFTYBEES.NS", equity), ("GOLDBEES.NS", gold), ("LIQUIDBEES.NS", liquid)):
        for dt, close in series.items():
            rows.append({"date": dt, "symbol": symbol, "open": float(close * 0.999),
                         "high": float(close * 1.002), "low": float(close * 0.998),
                         "close": float(close), "adj_close": float(close), "volume": 1_000_000})
    return pd.DataFrame(rows)
