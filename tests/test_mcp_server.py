"""Unit tests for the MCP server tool functions (offline, transport monkeypatched)."""

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from india_quant.data import make_fixture_prices

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = REPO_ROOT / "mcp" / "server.py"


def _load_server():
    spec = importlib.util.spec_from_file_location("india_quant_mcp_server", SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


server = _load_server()


def _chart_payload(price: float, currency: str = "INR", time: int = 1731480000) -> dict:
    return {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": price,
                        "currency": currency,
                        "regularMarketTime": time,
                    }
                }
            ]
        }
    }


def test_get_quote_returns_meta_price(monkeypatch):
    monkeypatch.setattr(server, "_fetch_chart", lambda symbol: _chart_payload(250.5))
    out = server.get_quote(["NIFTYBEES.NS"])
    assert out["NIFTYBEES.NS"] == {"price": 250.5, "currency": "INR", "time": 1731480000}


def test_get_quote_rejects_empty_symbol(monkeypatch):
    monkeypatch.setattr(server, "_fetch_chart", lambda symbol: _chart_payload(1.0))
    with pytest.raises(ValueError, match="symbol"):
        server.get_quote([""])


def test_list_universe_returns_three_roles():
    out = server.list_universe()
    symbols = [row["symbol"] for row in out["universe"]]
    assert symbols == ["NIFTYBEES.NS", "GOLDBEES.NS", "LIQUIDBEES.NS"]
    assert all(row["role"] for row in out["universe"])


def test_get_history_returns_iso_rows(monkeypatch):
    frame = make_fixture_prices(days=5)
    recorded = {}

    def fake_download(symbols, start, end):
        recorded["args"] = (tuple(symbols), start, end)
        return frame

    monkeypatch.setattr(server, "download_yahoo_daily", fake_download)
    rows = server.get_history(["NIFTYBEES.NS"], "2020-01-01", "2020-01-05")
    assert recorded["args"] == (("NIFTYBEES.NS",), date(2020, 1, 1), date(2020, 1, 5))
    assert set(rows[0]) == {"date", "symbol", "open", "high", "low", "close", "adj_close", "volume"}
    assert rows[0]["date"] == "2020-01-01"


def test_get_history_enforces_symbol_cap():
    with pytest.raises(ValueError, match="at most 5"):
        server.get_history([f"S{i}.NS" for i in range(6)], "2024-01-01", "2024-02-01")


def test_get_history_rejects_bad_dates():
    with pytest.raises(ValueError, match="start"):
        server.get_history(["NIFTYBEES.NS"], "2024-02-01", "2024-01-01")
    with pytest.raises(ValueError, match="start"):
        server.get_history(["NIFTYBEES.NS"], "not-a-date", "2024-02-01")


def test_get_history_span_cap():
    with pytest.raises(ValueError, match="3 years"):
        server.get_history(["NIFTYBEES.NS"], "2020-01-01", "2024-06-01")


def test_get_history_empty_yahoo_result(monkeypatch):
    def fake_download(symbols, start, end):
        raise ValueError("Yahoo returned no data for BOGUS.NS")

    monkeypatch.setattr(server, "download_yahoo_daily", fake_download)
    with pytest.raises(ValueError, match="NIFTYBEES.NS"):
        server.get_history(["BOGUS.NS", "NIFTYBEES.NS"], "2024-01-01", "2024-02-01")
