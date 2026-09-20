from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from .models import RESEARCH_UNIVERSE, PortfolioConfig, StrategyName
from .strategies import target_weights


class BrokerError(RuntimeError):
    """Raised when broker state or an order operation cannot be trusted."""


class BrokerClient(Protocol):
    def positions(self) -> list[dict[str, Any]]: ...

    def quotes(self, symbols: list[str]) -> dict[str, float]: ...

    def place_order(self, order: dict[str, Any]) -> str: ...


@dataclass(frozen=True)
class LiveConfig:
    api_key: str
    access_token: str
    capital_limit: float = 50_000.0
    max_order_value: float = 15_000.0
    max_total_order_value: float = 50_000.0
    max_data_age_days: int = 2
    order_type: str = "LIMIT"
    product: str = "CNC"
    execute_live: bool = False
    kill_switch: bool = True
    allow_unmanaged_positions: bool = False

    @classmethod
    def from_env(cls) -> LiveConfig:
        api_key = os.environ.get("KITE_API_KEY", "")
        access_token = os.environ.get("KITE_ACCESS_TOKEN", "")
        return cls(
            api_key=api_key,
            access_token=access_token,
            capital_limit=float(os.environ.get("INDIA_QUANT_LIVE_CAPITAL", "50000")),
            max_order_value=float(os.environ.get("INDIA_QUANT_MAX_ORDER_VALUE", "15000")),
            max_total_order_value=float(os.environ.get("INDIA_QUANT_MAX_TOTAL_ORDER_VALUE", "50000")),
            max_data_age_days=int(os.environ.get("INDIA_QUANT_MAX_DATA_AGE_DAYS", "2")),
            order_type=os.environ.get("INDIA_QUANT_ORDER_TYPE", "LIMIT").upper(),
            product=os.environ.get("INDIA_QUANT_PRODUCT", "CNC").upper(),
            execute_live=os.environ.get("INDIA_QUANT_LIVE_TRADING") == "I_UNDERSTAND_LIVE_RISK",
            kill_switch=os.environ.get("INDIA_QUANT_KILL_SWITCH", "ON").upper() != "OFF",
            allow_unmanaged_positions=os.environ.get("INDIA_QUANT_ALLOW_UNMANAGED_POSITIONS") == "YES",
        )

    def validate_for_execution(self) -> None:
        if not self.api_key or not self.access_token:
            raise BrokerError("KITE_API_KEY and KITE_ACCESS_TOKEN are required")
        if self.kill_switch:
            raise BrokerError("kill switch is active; set INDIA_QUANT_KILL_SWITCH=OFF explicitly")
        if not self.execute_live:
            raise BrokerError("live execution gate is not enabled")
        if self.product != "CNC":
            raise BrokerError("only CNC delivery orders are supported")
        if self.order_type not in {"LIMIT", "MARKET"}:
            raise BrokerError("order type must be LIMIT or MARKET")
        if self.order_type == "MARKET" and os.environ.get("INDIA_QUANT_ALLOW_MARKET_ORDERS") != "YES":
            raise BrokerError("market orders require INDIA_QUANT_ALLOW_MARKET_ORDERS=YES")
        if self.capital_limit <= 0 or self.max_order_value <= 0 or self.max_total_order_value <= 0:
            raise BrokerError("live limits must be positive")


class KiteBroker:
    """Thin official Kite Connect adapter; import is lazy so tests need no broker package or credentials."""

    def __init__(self, config: LiveConfig):
        try:
            from kiteconnect import KiteConnect
        except ImportError as exc:
            raise BrokerError("install the optional broker dependency: pip install -e .[broker]") from exc
        if not config.api_key or not config.access_token:
            raise BrokerError("KITE_API_KEY and KITE_ACCESS_TOKEN are required")
        self.config = config
        self.client = KiteConnect(api_key=config.api_key)
        self.client.set_access_token(config.access_token)

    @staticmethod
    def login_url(api_key: str) -> str:
        try:
            from kiteconnect import KiteConnect
        except ImportError as exc:
            raise BrokerError("install the optional broker dependency: pip install -e .[broker]") from exc
        return KiteConnect(api_key=api_key).login_url()

    def positions(self) -> list[dict[str, Any]]:
        return list(self.client.positions().get("net", []))

    def quotes(self, symbols: list[str]) -> dict[str, float]:
        payload = self.client.ltp([f"NSE:{symbol}" for symbol in symbols])
        return {symbol: float(payload[f"NSE:{symbol}"]["last_price"]) for symbol in symbols}

    def place_order(self, order: dict[str, Any]) -> str:
        return str(self.client.place_order(**order))


@dataclass(frozen=True)
class PlannedOrder:
    symbol: str
    side: str
    quantity: int
    limit_price: float
    value: float
    leg: int = 0


@dataclass(frozen=True)
class TradePlan:
    strategy: StrategyName
    run_date: str
    source_date: str
    capital_limit: float
    current_positions: dict[str, int]
    target_positions: dict[str, int]
    orders: tuple[PlannedOrder, ...]
    unmanaged_positions: tuple[str, ...]
    hash: str


def _broker_symbol(symbol: str) -> str:
    return symbol.removesuffix(".NS")


def normalize_positions(raw: list[dict[str, Any]]) -> tuple[dict[str, int], tuple[str, ...]]:
    positions: dict[str, int] = {}
    unmanaged: list[str] = []
    managed = {_broker_symbol(symbol) for symbol in RESEARCH_UNIVERSE}
    for row in raw:
        if row.get("exchange") != "NSE":
            continue
        symbol = str(row.get("tradingsymbol", ""))
        quantity = int(row.get("quantity", 0))
        if symbol in managed:
            positions[symbol] = positions.get(symbol, 0) + quantity
        elif quantity:
            unmanaged.append(symbol)
    return positions, tuple(sorted(set(unmanaged)))


def build_trade_plan(prices: pd.DataFrame, strategy: StrategyName, broker: BrokerClient,
                     config: LiveConfig, run_date: pd.Timestamp | str | None = None) -> TradePlan:
    """Build a plan from prior history, broker positions and current broker quotes.

    This function never submits an order. The source file must contain the latest completed session and must not
    be older than the configured data-age limit.
    """
    run_timestamp = pd.Timestamp(run_date or prices["date"].max()).normalize()
    source_date = pd.Timestamp(prices["date"].max()).normalize()
    age = (run_timestamp - source_date).days
    if age < 0 or age > config.max_data_age_days:
        raise BrokerError(f"market data is stale: source={source_date.date()} run={run_timestamp.date()}")
    history = prices[prices["date"] <= source_date].pivot(index="date", columns="symbol", values="adj_close").sort_index().ffill()
    current = prices[prices["date"].eq(source_date)].set_index("symbol")
    if set(RESEARCH_UNIVERSE) - set(current.index):
        raise BrokerError("market data does not contain the complete managed universe")
    broker_positions, unmanaged = normalize_positions(broker.positions())
    if unmanaged and not config.allow_unmanaged_positions:
        raise BrokerError(f"unmanaged NSE positions block execution: {', '.join(unmanaged)}")
    symbols = [_broker_symbol(symbol) for symbol in RESEARCH_UNIVERSE]
    quotes = broker.quotes(symbols)
    weights = target_weights(history.iloc[:-1], strategy, PortfolioConfig(initial_capital=config.capital_limit))
    target = {symbol: int((weights.get(f"{symbol}.NS", 0.0) * config.capital_limit) // quotes[symbol]) for symbol in symbols}
    current_positions = {symbol: broker_positions.get(symbol, 0) for symbol in symbols}
    orders: list[PlannedOrder] = []
    for symbol in symbols:
        delta = target[symbol] - current_positions[symbol]
        if delta:
            side = "BUY" if delta > 0 else "SELL"
            remaining = abs(delta)
            leg = 0
            while remaining:
                quantity = min(remaining, max(1, int(config.max_order_value // quotes[symbol])))
                orders.append(PlannedOrder(symbol, side, quantity, quotes[symbol], quantity * quotes[symbol], leg))
                remaining -= quantity
                leg += 1
        orders.sort(key=lambda order: (order.side != "SELL", order.symbol))
    if sum(order.value for order in orders) > config.max_total_order_value:
        raise BrokerError("plan exceeds max total order value")
    if any(order.value > config.max_order_value + 1e-9 for order in orders):
        raise BrokerError("plan contains an order above max order value")
    unsigned = {
        "strategy": strategy, "run_date": str(run_timestamp.date()), "source_date": str(source_date.date()),
        "capital_limit": config.capital_limit, "current_positions": current_positions,
        "target_positions": target, "orders": [asdict(order) for order in orders],
        "unmanaged_positions": list(unmanaged),
    }
    digest = hashlib.sha256(json.dumps(unsigned, sort_keys=True).encode("utf-8")).hexdigest()
    unsigned["orders"] = tuple(orders)
    return TradePlan(**unsigned, hash=digest)


LIVE_SCHEMA = """
CREATE TABLE IF NOT EXISTS live_submissions (
    plan_hash TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    leg INTEGER NOT NULL,
    broker_order_id TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(plan_hash, symbol, side, quantity, leg)
);
CREATE TABLE IF NOT EXISTS audit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    plan_hash TEXT,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class LiveLedger:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.executescript(LIVE_SCHEMA)
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(live_submissions)")}
        if columns and "leg" not in columns:
            raise BrokerError("live ledger schema is outdated; use a new live/live.db before execution")
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def audit(self, event_type: str, payload: dict[str, Any], plan_hash: str | None = None) -> None:
        self.connection.execute(
            "INSERT INTO audit_events(event_type, plan_hash, payload, created_at) VALUES (?, ?, ?, ?)",
            (event_type, plan_hash, json.dumps(payload, sort_keys=True, default=str), datetime.now(timezone.utc).isoformat()),
        )
        self.connection.commit()

    def submitted(self, plan_hash: str, order: PlannedOrder) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM live_submissions WHERE plan_hash = ? AND symbol = ? AND side = ? AND quantity = ? AND leg = ?",
            (plan_hash, order.symbol, order.side, order.quantity, order.leg),
        ).fetchone()
        return row is not None

    def record(self, plan_hash: str, order: PlannedOrder, broker_order_id: str | None, status: str) -> None:
        self.connection.execute(
            "INSERT OR IGNORE INTO live_submissions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (plan_hash, order.symbol, order.side, order.quantity, order.leg, broker_order_id, status,
             datetime.now(timezone.utc).isoformat()),
        )
        self.connection.commit()


def save_plan(plan: TradePlan, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(plan), indent=2, default=str), encoding="utf-8")


def load_plan(path: Path) -> TradePlan:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["orders"] = tuple(PlannedOrder(**order) for order in payload["orders"])
    return TradePlan(**payload)


def approval_matches(plan: TradePlan, path: Path) -> bool:
    return path.exists() and path.read_text(encoding="utf-8").strip() == plan.hash


def execute_plan(plan: TradePlan, broker: BrokerClient, ledger: LiveLedger, config: LiveConfig,
                 approval_path: Path) -> list[dict[str, str]]:
    config.validate_for_execution()
    if not approval_matches(plan, approval_path):
        raise BrokerError("approval file does not match the plan hash")
    current, unmanaged = normalize_positions(broker.positions())
    if unmanaged and not config.allow_unmanaged_positions:
        raise BrokerError(f"unmanaged positions block execution: {', '.join(unmanaged)}")
    expected = {symbol: current.get(symbol, 0) for symbol in plan.current_positions}
    if expected != plan.current_positions:
        raise BrokerError("broker positions changed since plan creation; rebuild the plan")
    ledger.audit("preflight_passed", {"plan": asdict(plan)}, plan.hash)
    results: list[dict[str, str]] = []
    for order in plan.orders:
        if ledger.submitted(plan.hash, order):
            results.append({"symbol": order.symbol, "status": "already_submitted"})
            continue
        payload = {
            "exchange": "NSE", "tradingsymbol": order.symbol, "transaction_type": order.side,
            "quantity": order.quantity, "order_type": config.order_type, "product": config.product,
            "validity": "DAY", "tag": f"iq{plan.hash[:12]}l{order.leg}",
        }
        if config.order_type == "LIMIT":
            payload["price"] = order.limit_price
        try:
            broker_order_id = broker.place_order(payload)
        except Exception as exc:
            ledger.audit("order_failed", {"order": payload, "error": repr(exc)}, plan.hash)
            ledger.record(plan.hash, order, None, "failed")
            raise BrokerError(f"broker rejected {order.side} {order.quantity} {order.symbol}") from exc
        ledger.record(plan.hash, order, broker_order_id, "submitted")
        ledger.audit("order_submitted", {"order": payload, "broker_order_id": broker_order_id}, plan.hash)
        results.append({"symbol": order.symbol, "status": "submitted", "order_id": broker_order_id})
    ledger.audit("execution_complete", {"count": len(results)}, plan.hash)
    return results
