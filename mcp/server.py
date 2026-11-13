"""Read-only India ETF market data over MCP (stdio).

Wraps the research Yahoo adapter in india_quant.data. No order or broker surface.
Data is delayed and unlicensed: personal research only, see README.
"""

from __future__ import annotations

import json
import time
from datetime import date
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from india_quant.data import download_yahoo_daily

UNIVERSE: dict[str, str] = {
    "NIFTYBEES.NS": "Indian large-cap equity ETF",
    "GOLDBEES.NS": "Gold ETF",
    "LIQUIDBEES.NS": "Liquid/low-duration parking asset",
}
MAX_SYMBOLS = 5
MAX_SPAN_DAYS = 1100  # ~3 years
_DATA_POLICY = (
    "Yahoo Finance research data: delayed and unlicensed, personal research only. "
    "Not a production feed; do not use for live trading."
)

mcp = FastMCP(
    "india-quant-research",
    instructions=(
        "Read-only market data for a small Indian ETF portfolio (NSE) plus any other "
        "Yahoo ticker. Tools: get_quote (latest price), get_history (cleaned daily "
        "OHLCV, max 5 symbols / 3 years), list_universe (research ETFs and roles). "
        + _DATA_POLICY
    ),
)


def _valid_symbols_hint() -> str:
    return f"Example valid symbols: {', '.join(UNIVERSE)}."


def _fetch_chart(symbol: str) -> dict:
    """Fetch the public Yahoo chart payload for one symbol (research transport)."""
    now = int(time.time())
    period1 = now - 7 * 86400
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{quote(symbol)}?period1={period1}&period2={now + 86400}&interval=1d"
    )
    request = Request(url, headers={"User-Agent": "india-quant-research/0.1"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def get_quote(symbols: list[str]) -> dict[str, dict[str, Any]]:
    """Latest price per symbol from the Yahoo chart endpoint.

    Returns {"SYMBOL": {"price": float, "currency": str, "time": epoch_seconds,
    "previous_close": float (when Yahoo provides it)}}.
    """
    quotes: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        symbol = (symbol or "").strip()
        if not symbol:
            raise ValueError(
                "each symbol must be a non-empty Yahoo ticker. " + _valid_symbols_hint()
            )
        payload = _fetch_chart(symbol)
        result = payload.get("chart", {}).get("result") or []
        if not result:
            raise ValueError(f"Yahoo returned no data for {symbol}. " + _valid_symbols_hint())
        meta = result[0].get("meta", {})
        quote_out: dict[str, Any] = {
            "price": float(meta["regularMarketPrice"]),
            "currency": str(meta.get("currency", "")),
            "time": int(meta.get("regularMarketTime", 0)),
        }
        if meta.get("previousClose") is not None:
            quote_out["previous_close"] = float(meta["previousClose"])
        quotes[symbol] = quote_out
    return quotes


def get_history(symbols: list[str], start: str, end: str) -> list[dict[str, Any]]:
    """Cleaned daily OHLCV rows for the given symbols between start and end (inclusive).

    Dates are YYYY-MM-DD. Max 5 symbols and a 3-year span per call. Rows carry
    date, symbol, open, high, low, close, adj_close, volume. Data is anomaly-cleaned
    and continuity-checked by the research pipeline.
    """
    if len(symbols) > MAX_SYMBOLS:
        raise ValueError(f"request at most {MAX_SYMBOLS} symbols per call")
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except (TypeError, ValueError) as error:
        raise ValueError(f"start and end must be YYYY-MM-DD dates: {error}") from error
    if start_date > end_date:
        raise ValueError("start must not be after end")
    if (end_date - start_date).days > MAX_SPAN_DAYS:
        raise ValueError(f"date span is limited to 3 years ({MAX_SPAN_DAYS} days)")
    try:
        prices = download_yahoo_daily(tuple(symbols), start_date, end_date)
    except ValueError as error:
        raise ValueError(f"{error} {_valid_symbols_hint()}") from error
    rows = prices.to_dict("records")
    for row in rows:
        row["date"] = row["date"].date().isoformat() if hasattr(row["date"], "date") else str(row["date"])
    return rows


def list_universe() -> dict[str, Any]:
    """The research universe: each ETF symbol and its role in the portfolio."""
    return {
        "universe": [{"symbol": symbol, "role": role} for symbol, role in UNIVERSE.items()],
        "note": _DATA_POLICY,
    }


mcp.tool(get_quote, annotations=ToolAnnotations(readOnlyHint=True))
mcp.tool(get_history, annotations=ToolAnnotations(readOnlyHint=True))
mcp.tool(list_universe, annotations=ToolAnnotations(readOnlyHint=True))

if __name__ == "__main__":
    mcp.run()
