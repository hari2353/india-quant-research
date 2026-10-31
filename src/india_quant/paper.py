from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .metrics import performance_metrics
from .models import PortfolioConfig, StrategyName
from .strategies import target_weights


@dataclass(frozen=True)
class PaperRiskConfig:
    max_daily_loss: float = 0.08
    max_drawdown: float = 0.25
    max_data_gap_days: int = 5


@dataclass(frozen=True)
class PaperRun:
    strategy: StrategyName
    date: pd.Timestamp
    status: str
    reason: str
    cash: float
    equity: float
    order_count: int


SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    strategy TEXT PRIMARY KEY,
    initial_capital REAL NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    strategy TEXT NOT NULL,
    run_date TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    cash REAL NOT NULL,
    equity REAL NOT NULL,
    source_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (strategy, run_date)
);
CREATE TABLE IF NOT EXISTS positions (
    strategy TEXT NOT NULL,
    run_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    shares INTEGER NOT NULL,
    price REAL NOT NULL,
    market_value REAL NOT NULL,
    PRIMARY KEY (strategy, run_date, symbol)
);
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy TEXT NOT NULL,
    run_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    requested_price REAL NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fills (
    fill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,
    fee REAL NOT NULL,
    slippage REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS runs_by_strategy_date ON runs(strategy, run_date);
CREATE INDEX IF NOT EXISTS orders_by_strategy_date ON orders(strategy, run_date);
CREATE VIEW IF NOT EXISTS paper_rejections AS
    SELECT strategy, run_date, symbol, side, quantity, requested_price, reason
    FROM orders
    WHERE status <> 'filled';
"""


def _date(value: pd.Timestamp | str) -> str:
    return pd.Timestamp(value).normalize().strftime("%Y-%m-%d")


def _source_hash(prices: pd.DataFrame, run_date: pd.Timestamp) -> str:
    rows = prices[prices["date"].eq(run_date)].sort_values("symbol")
    payload = rows.to_json(orient="records", date_format="iso")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PaperLedger:
    """Persistent, local-only paper-trading ledger."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def _latest_run(self, strategy: StrategyName, before: pd.Timestamp | None = None) -> sqlite3.Row | None:
        query = "SELECT * FROM runs WHERE strategy = ?"
        params: list[str] = [strategy]
        if before is not None:
            query += " AND run_date < ?"
            params.append(_date(before))
        query += " ORDER BY run_date DESC LIMIT 1"
        return self.connection.execute(query, params).fetchone()

    def _holdings(self, strategy: StrategyName, run_date: str) -> dict[str, int]:
        rows = self.connection.execute(
            "SELECT symbol, shares FROM positions WHERE strategy = ? AND run_date = ?",
            (strategy, run_date),
        ).fetchall()
        return {row["symbol"]: int(row["shares"]) for row in rows}

    def _account(self, strategy: StrategyName, config: PortfolioConfig) -> None:
        self.connection.execute(
            "INSERT OR IGNORE INTO accounts(strategy, initial_capital, created_at) VALUES (?, ?, datetime('now'))",
            (strategy, config.initial_capital),
        )

    def _risk_gate(self, strategy: StrategyName, run_date: pd.Timestamp, equity: float,
                   previous_equity: float | None, risk: PaperRiskConfig) -> tuple[bool, str]:
        if previous_equity and equity / previous_equity - 1.0 <= -risk.max_daily_loss:
            return False, "daily_loss_limit"
        account = self.connection.execute(
            "SELECT initial_capital FROM accounts WHERE strategy = ?", (strategy,)
        ).fetchone()
        if account and equity / float(account["initial_capital"]) - 1.0 <= -risk.max_drawdown:
            return False, "max_drawdown_limit"
        previous_date = self._latest_run(strategy, run_date)
        if previous_date:
            gap = (run_date - pd.Timestamp(previous_date["run_date"])).days
            if gap > risk.max_data_gap_days:
                return False, "data_gap_limit"
        return True, "risk_checks_passed"

    def process_date(self, prices: pd.DataFrame, strategy: StrategyName,
                     run_date: pd.Timestamp | str, config: PortfolioConfig | None = None,
                     risk: PaperRiskConfig | None = None) -> PaperRun:
        """Process one date exactly once, using that date's open for fills and close for valuation."""
        config = config or PortfolioConfig()
        risk = risk or PaperRiskConfig()
        run_timestamp = pd.Timestamp(run_date).normalize()
        source_hash = _source_hash(prices, run_timestamp)
        existing = self.connection.execute(
            "SELECT * FROM runs WHERE strategy = ? AND run_date = ?", (strategy, _date(run_timestamp))
        ).fetchone()
        if existing:
            return PaperRun(strategy, run_timestamp, existing["status"], existing["reason"],
                            existing["cash"], existing["equity"], self._order_count(strategy, _date(run_timestamp)))

        current = prices[prices["date"].eq(run_timestamp)].set_index("symbol")
        if current.empty:
            raise ValueError(f"no prices available for {run_timestamp.date()}")
        if current[["open", "close"]].isna().any().any():
            raise ValueError("paper run requires non-null open and close prices")
        self._account(strategy, config)
        previous = self._latest_run(strategy, run_timestamp)
        previous_equity = float(previous["equity"]) if previous else None
        cash = float(previous["cash"]) if previous else config.initial_capital
        shares = self._holdings(strategy, previous["run_date"]) if previous else {symbol: 0 for symbol in current.index}
        for symbol in current.index:
            shares.setdefault(symbol, 0)
        open_prices = current["open"].astype(float)
        close_prices = current["close"].astype(float)
        equity_at_open = cash + sum(shares[symbol] * open_prices[symbol] for symbol in current.index)
        allowed, reason = self._risk_gate(strategy, run_timestamp, equity_at_open, previous_equity, risk)

        historical = prices[prices["date"] < run_timestamp]
        rebalance = previous is None or pd.Timestamp(previous["run_date"]).month != run_timestamp.month
        order_count = 0
        if allowed and rebalance:
            panel = historical.pivot(index="date", columns="symbol", values="adj_close").sort_index().ffill()
            if panel.empty:
                panel = pd.DataFrame(columns=current.index, index=pd.DatetimeIndex([]), dtype=float)
            weights = target_weights(panel, strategy, config).reindex(current.index, fill_value=0.0)
            target_values = weights * equity_at_open
            target_shares = {symbol: int(target_values[symbol] // open_prices[symbol]) for symbol in current.index}
            target_shares = self._fit_no_leverage(cash, shares, target_shares, open_prices, config)
            # Sell first so the ledger remains valid even when a rebalance changes instruments.
            for symbol in current.index:
                delta = target_shares[symbol] - shares[symbol]
                if delta < 0:
                    cash, shares[symbol] = self._fill(strategy, run_timestamp, symbol, delta, cash,
                                                       shares[symbol], open_prices[symbol], config)
                    order_count += 1
            for symbol in current.index:
                delta = target_shares[symbol] - shares[symbol]
                if delta > 0:
                    cash, shares[symbol] = self._fill(strategy, run_timestamp, symbol, delta, cash,
                                                       shares[symbol], open_prices[symbol], config)
                    order_count += 1
            reason = "rebalance_filled"
        elif not allowed:
            reason = f"halted:{reason}"
        else:
            reason = "no_rebalance"

        equity = cash + sum(shares[symbol] * close_prices[symbol] for symbol in current.index)
        run_status = "processed" if allowed else "halted"
        with self.connection:
            self.connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                (strategy, _date(run_timestamp), run_status, reason, cash, equity, source_hash),
            )
            for symbol in current.index:
                self.connection.execute(
                    "INSERT INTO positions VALUES (?, ?, ?, ?, ?, ?)",
                    (strategy, _date(run_timestamp), symbol, shares[symbol], close_prices[symbol],
                     shares[symbol] * close_prices[symbol]),
                )
        return PaperRun(strategy, run_timestamp, run_status, reason, cash, equity, order_count)

    def _fit_no_leverage(self, cash: float, shares: dict[str, int], target: dict[str, int],
                         prices: pd.Series, config: PortfolioConfig) -> dict[str, int]:
        while True:
            projected = cash
            for symbol in prices.index:
                delta = target[symbol] - shares[symbol]
                execution = prices[symbol] * (1 + config.slippage_rate if delta > 0 else 1 - config.slippage_rate)
                projected -= delta * execution + abs(delta * execution) * config.cost_rate
            if projected >= -1e-9:
                return target
            candidates = [symbol for symbol in prices.index if target[symbol] > shares[symbol]]
            if not candidates:
                raise RuntimeError("paper rebalance cannot satisfy no-leverage constraint")
            symbol = max(candidates, key=lambda name: target[name] * prices[name])
            target[symbol] -= 1

    def _fill(self, strategy: StrategyName, run_date: pd.Timestamp, symbol: str, delta: int,
              cash: float, old_shares: int, price: float, config: PortfolioConfig) -> tuple[float, int]:
        execution = price * (1 + config.slippage_rate if delta > 0 else 1 - config.slippage_rate)
        notional = abs(delta * execution)
        fee = notional * config.cost_rate
        new_cash = cash - delta * execution - fee
        if new_cash < -1e-9:
            raise RuntimeError("paper fill would create negative cash")
        side = "BUY" if delta > 0 else "SELL"
        reason = "simulated_open_fill"
        cursor = self.connection.execute(
            "INSERT INTO orders(strategy, run_date, symbol, side, quantity, requested_price, status, reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (strategy, _date(run_date), symbol, side, abs(delta), price, "filled", reason),
        )
        self.connection.execute(
            "INSERT INTO fills(order_id, quantity, price, fee, slippage) VALUES (?, ?, ?, ?, ?)",
            (cursor.lastrowid, abs(delta), execution, fee, abs(delta * (execution - price))),
        )
        return new_cash, old_shares + delta

    def _order_count(self, strategy: StrategyName, run_date: str) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS count FROM orders WHERE strategy = ? AND run_date = ?",
            (strategy, run_date),
        ).fetchone()
        return int(row["count"])

    def summary(self, strategy: StrategyName) -> dict[str, float | int | str]:
        rows = self.connection.execute(
            "SELECT run_date, equity FROM runs WHERE strategy = ? ORDER BY run_date", (strategy,)
        ).fetchall()
        if not rows:
            raise ValueError(f"no paper runs for {strategy}")
        equity = pd.Series({pd.Timestamp(row["run_date"]): row["equity"] for row in rows}, dtype=float)
        trades = pd.read_sql_query("SELECT * FROM orders WHERE strategy = ? ORDER BY run_date",
                                   self.connection, params=(strategy,))
        metrics = performance_metrics(equity, trades.rename(columns={"quantity": "notional"}), equity.iloc[0])
        return {"strategy": strategy, **metrics, "runs": len(rows)}

    def export(self, out: Path, strategies: tuple[StrategyName, ...]) -> None:
        out.mkdir(parents=True, exist_ok=True)
        summaries = [self.summary(strategy) for strategy in strategies if self._latest_run(strategy)]
        pd.DataFrame(summaries).to_csv(out / "paper_summary.csv", index=False)
        (out / "paper_summary.json").write_text(json.dumps(summaries, indent=2, default=str), encoding="utf-8")

    def error_analysis(self) -> list[sqlite3.Row]:
        """Rejected orders grouped by (strategy, reason) — error-analysis memory."""
        return list(self.connection.execute(
            "SELECT strategy, reason, COUNT(*) AS count FROM paper_rejections "
            "GROUP BY strategy, reason ORDER BY count DESC, reason"))

    def run_status(self) -> list[sqlite3.Row]:
        """Every ledger run: date, gate outcome and equity — the audit trail."""
        return list(self.connection.execute(
            "SELECT strategy, run_date, status, reason, equity FROM runs "
            "ORDER BY run_date, strategy"))
