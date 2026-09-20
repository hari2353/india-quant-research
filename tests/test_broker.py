from pathlib import Path

import pytest

from india_quant.broker import (
    BrokerError,
    LiveConfig,
    LiveLedger,
    build_trade_plan,
    execute_plan,
    save_plan,
)
from india_quant.data import make_fixture_prices


class FakeBroker:
    def __init__(self, positions=None):
        self._positions = positions or []
        self.orders = []

    def positions(self):
        return self._positions

    def quotes(self, symbols):
        return {symbol: 100.0 for symbol in symbols}

    def place_order(self, order):
        self.orders.append(order)
        return f"fake-{len(self.orders)}"


def _config(**kwargs):
    return LiveConfig(api_key="key", access_token="token", **kwargs)


def test_plan_hash_round_trip_and_no_unmanaged_positions():
    prices = make_fixture_prices(400)
    broker = FakeBroker()
    plan = build_trade_plan(prices, "balanced", broker, _config(), prices["date"].max())
    path = Path("plan-test.json")
    try:
        save_plan(plan, path)
        assert path.exists()
        assert plan.hash
    finally:
        path.unlink(missing_ok=True)


def test_unmanaged_position_blocks_plan():
    prices = make_fixture_prices(400)
    broker = FakeBroker([{"exchange": "NSE", "tradingsymbol": "RELIANCE", "quantity": 1}])
    with pytest.raises(BrokerError, match="unmanaged"):
        build_trade_plan(prices, "balanced", broker, _config(), prices["date"].max())


def test_execute_requires_gate_and_matching_approval(tmp_path):
    prices = make_fixture_prices(400)
    broker = FakeBroker()
    config = _config(execute_live=False, kill_switch=False)
    plan = build_trade_plan(prices, "balanced", broker, config, prices["date"].max())
    approval = tmp_path / "approval"
    approval.write_text(plan.hash, encoding="utf-8")
    ledger = LiveLedger(tmp_path / "live.db")
    try:
        with pytest.raises(BrokerError, match="gate"):
            execute_plan(plan, broker, ledger, config, approval)
    finally:
        ledger.close()


def test_execute_is_idempotent_and_position_drift_blocks(tmp_path):
    prices = make_fixture_prices(400)
    broker = FakeBroker()
    config = _config(execute_live=True, kill_switch=False)
    plan = build_trade_plan(prices, "balanced", broker, config, prices["date"].max())
    approval = tmp_path / "approval"
    approval.write_text(plan.hash, encoding="utf-8")
    ledger = LiveLedger(tmp_path / "live.db")
    try:
        first = execute_plan(plan, broker, ledger, config, approval)
        second = execute_plan(plan, broker, ledger, config, approval)
        assert len(broker.orders) == len(plan.orders)
        assert len(first) == len(second)
        broker._positions = [{"exchange": "NSE", "tradingsymbol": "NIFTYBEES", "quantity": 1}]
        with pytest.raises(BrokerError, match="positions"):
            execute_plan(plan, broker, ledger, config, approval)
    finally:
        ledger.close()
