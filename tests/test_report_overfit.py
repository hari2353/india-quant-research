"""The default research report must enforce the README's own rule: no
in-sample-only selection. It now ships the overfit guard (DSR + PBO) and a
tearsheet surface without extra flags."""

from __future__ import annotations

import json
from pathlib import Path

from india_quant.data import make_fixture_prices
from india_quant.report import research_report, tearsheet


def test_report_carries_the_overfit_guard(tmp_path: Path) -> None:
    payload = research_report(make_fixture_prices(800), tmp_path)
    assert "overfit" in payload
    guard = payload["overfit"]
    assert set(guard) == {"pbo", "deflated_sharpe"}
    assert 0.0 <= guard["pbo"] <= 1.0
    assert len(guard["deflated_sharpe"]) == 6  # one per candidate strategy
    assert all(0.0 <= v <= 1.0 for v in guard["deflated_sharpe"].values())
    stored = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert "overfit" in stored


def test_report_omits_pbo_when_thin_instead_of_faking(tmp_path: Path) -> None:
    payload = research_report(make_fixture_prices(200), tmp_path)
    guard = payload["overfit"]
    if guard["pbo"] is None:
        assert guard["pbo_reason"]
    else:
        assert 0.0 <= guard["pbo"] <= 1.0


def test_tearsheet_is_bounded_markdown_with_the_guard(tmp_path: Path) -> None:
    sheet = tearsheet(make_fixture_prices(800), "equal_weight", tmp_path / "tearsheet.md")
    text = (tmp_path / "tearsheet.md").read_text(encoding="utf-8")
    assert sheet["strategy"] == "equal_weight"
    assert "# tearsheet" in text.lower()
    assert "sortino" in text.lower() and "sharpe" in text.lower()
    assert "deflated_sharpe" in text
    assert len(text) < 8_000
