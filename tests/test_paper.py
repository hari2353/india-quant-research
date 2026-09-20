import pandas as pd

from india_quant.data import make_fixture_prices
from india_quant.models import PortfolioConfig
from india_quant.paper import PaperLedger, PaperRiskConfig


def _prices(days: int = 500) -> pd.DataFrame:
    prices = make_fixture_prices(days)
    prices["date"] = pd.to_datetime(prices["date"]).dt.normalize()
    return prices


def test_paper_run_is_idempotent_and_persists_positions(tmp_path):
    prices = _prices()
    ledger = PaperLedger(tmp_path / "paper.db")
    try:
        date = prices["date"].iloc[0]
        first = ledger.process_date(prices, "balanced", date, PortfolioConfig())
        second = ledger.process_date(prices, "balanced", date, PortfolioConfig())
        assert first == second
        count = ledger.connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        assert count == 1
        assert ledger.connection.execute("SELECT COUNT(*) FROM positions").fetchone()[0] == 3
    finally:
        ledger.close()


def test_paper_replay_has_no_negative_cash(tmp_path):
    prices = _prices(800)
    ledger = PaperLedger(tmp_path / "paper.db")
    try:
        for date in sorted(prices["date"].unique()):
            ledger.process_date(prices, "equal_weight", date, PortfolioConfig())
        assert ledger.connection.execute("SELECT MIN(cash) FROM runs").fetchone()[0] >= -1e-9
        assert ledger.connection.execute("SELECT COUNT(*) FROM fills").fetchone()[0] > 0
    finally:
        ledger.close()


def test_paper_risk_gate_halts_and_does_not_place_orders(tmp_path):
    prices = _prices(500)
    ledger = PaperLedger(tmp_path / "paper.db")
    try:
        dates = sorted(prices["date"].unique())
        ledger.process_date(prices, "balanced", dates[0], PortfolioConfig())
        initial_orders = ledger.connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        result = ledger.process_date(
            prices, "balanced", dates[-1], PortfolioConfig(),
            PaperRiskConfig(max_data_gap_days=5),
        )
        assert result.status == "halted"
        assert result.reason == "halted:data_gap_limit"
        assert ledger.connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == initial_orders
    finally:
        ledger.close()
