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


def test_error_analysis_groups_rejections_and_runs(tmp_path):
    ledger = PaperLedger(tmp_path / "paper.db")
    try:
        conn = ledger.connection
        conn.execute("INSERT INTO accounts VALUES ('s', 50000.0, '2026-01-01')")
        conn.execute(
            "INSERT INTO runs (strategy, run_date, status, reason, cash, equity, source_hash, created_at) "
            "VALUES ('s', '2026-01-05', 'rebalance_filled', 'ok', 1000.0, 50000.0, 'h', '2026-01-05')")
        for symbol, quantity, status, reason in [
            ("NIFTYBEES.NS", 10, "rejected", "below_min_price"),
            ("NIFTYBEES.NS", 10, "rejected", "below_min_price"),
            ("GOLDBEES.NS", 1, "filled", "rebalance"),
        ]:
            conn.execute(
                "INSERT INTO orders (strategy, run_date, symbol, side, quantity, requested_price, status, reason) "
                "VALUES ('s', '2026-01-05', ?, 'buy', ?, 1.0, ?, ?)",
                (symbol, quantity, status, reason))
        conn.commit()
        groups = [dict(r) for r in ledger.error_analysis()]
        assert groups[0] == {"strategy": "s", "reason": "below_min_price", "count": 2}
        assert all(g["reason"] != "filled" for g in groups)  # filled orders excluded
        runs = [dict(r) for r in ledger.run_status()]
        assert runs[0]["status"] == "rebalance_filled" and runs[0]["equity"] == 50000.0
    finally:
        ledger.close()


def test_error_analysis_is_empty_for_fresh_ledger(tmp_path):
    ledger = PaperLedger(tmp_path / "paper.db")
    try:
        assert ledger.error_analysis() == []
        assert ledger.run_status() == []
    finally:
        ledger.close()
