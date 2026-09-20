from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .metrics import performance_metrics
from .models import BacktestResult, PortfolioConfig, StrategyName
from .strategies import target_weights


@dataclass
class _State:
    cash: float
    shares: dict[str, int]


def _rebalance_dates(index: pd.DatetimeIndex) -> set[pd.Timestamp]:
    months = pd.Series(index=index, data=index).groupby(index.to_period("M")).first()
    return set(months.iloc[1:].tolist())


def _execute(state: _State, prices: pd.Series, weights: pd.Series, config: PortfolioConfig,
             date: pd.Timestamp, trades: list[dict]) -> None:
    current_value = state.cash + sum(state.shares.get(symbol, 0) * float(prices[symbol])
                                     for symbol in prices.index)
    target_values = weights.reindex(prices.index, fill_value=0.0) * current_value
    target_shares = {symbol: int(target_values[symbol] // prices[symbol]) for symbol in prices.index}
    # Whole-share rounding plus fees must never turn the simulator into an accidental margin account.
    while True:
        projected_cash = state.cash
        for symbol in prices.index:
            delta = target_shares[symbol] - state.shares.get(symbol, 0)
            price = float(prices[symbol])
            execution_price = price * (1 + config.slippage_rate if delta > 0 else 1 - config.slippage_rate)
            notional = abs(delta) * execution_price
            projected_cash -= delta * execution_price + notional * config.cost_rate
        if projected_cash >= -1e-9:
            break
        candidates = [symbol for symbol in prices.index
                      if target_shares[symbol] > state.shares.get(symbol, 0)]
        if not candidates:
            raise RuntimeError("rebalance cannot satisfy no-leverage constraint")
        reduce_symbol = max(candidates, key=lambda symbol: target_shares[symbol] * prices[symbol])
        target_shares[reduce_symbol] -= 1
    symbols = set(state.shares) | set(target_shares)
    for symbol in sorted(symbols):
        old = state.shares.get(symbol, 0)
        new = target_shares.get(symbol, 0)
        delta = new - old
        if delta == 0:
            continue
        price = float(prices[symbol])
        # Buys pay slippage; sells receive slightly worse execution. Both pay the modeled round-trip costs.
        execution_price = price * (1 + config.slippage_rate if delta > 0 else 1 - config.slippage_rate)
        notional = abs(delta) * execution_price
        fee = notional * config.cost_rate
        state.cash -= delta * execution_price + fee
        state.shares[symbol] = new
        trades.append({"date": date, "symbol": symbol, "shares": delta,
                       "price": execution_price, "notional": notional, "fee": fee})


def run_backtest(prices: pd.DataFrame, strategy: StrategyName,
                 config: PortfolioConfig | None = None) -> BacktestResult:
    """Run a causal monthly rebalanced backtest using next-day opens for execution."""
    config = config or PortfolioConfig()
    if prices.empty:
        raise ValueError("prices cannot be empty")
    open_panel = prices.pivot(index="date", columns="symbol", values="open").sort_index()
    close_panel = prices.pivot(index="date", columns="symbol", values="adj_close").sort_index().ffill()
    common = open_panel.index.intersection(close_panel.index)
    open_panel, close_panel = open_panel.loc[common], close_panel.loc[common]
    symbols = list(close_panel.columns)
    rebalance_dates = _rebalance_dates(common)
    state = _State(config.initial_capital, {symbol: 0 for symbol in symbols})
    weights_log: list[pd.Series] = []
    holdings_log: list[pd.Series] = []
    equity_values: list[float] = []
    trades: list[dict] = []
    active_weights = pd.Series(0.0, index=symbols)
    for position, date in enumerate(common):
        initial_static = position == 0 and strategy in {"buy_hold", "equal_weight", "balanced"}
        scheduled_rebalance = date in rebalance_dates and position > 0 and strategy != "buy_hold"
        if initial_static or scheduled_rebalance:
            history = close_panel.iloc[:position]
            active_weights = target_weights(history, strategy, config).reindex(symbols, fill_value=0.0)
            _execute(state, open_panel.iloc[position], active_weights, config, date, trades)
        close_prices = close_panel.loc[date]
        value = state.cash + sum(state.shares[symbol] * float(close_prices[symbol]) for symbol in symbols)
        equity_values.append(value)
        weights_log.append(active_weights.copy())
        holdings_log.append(pd.Series(state.shares, dtype=float))
    equity = pd.Series(equity_values, index=common, name="equity")
    weights = pd.DataFrame(weights_log, index=common).fillna(0.0)
    holdings = pd.DataFrame(holdings_log, index=common).fillna(0.0)
    trade_frame = pd.DataFrame(trades, columns=["date", "symbol", "shares", "price", "notional", "fee"])
    metrics = performance_metrics(equity, trade_frame, config.initial_capital)
    return BacktestResult(strategy, equity, weights, holdings, trade_frame, metrics)


def walk_forward(prices: pd.DataFrame, strategies: tuple[StrategyName, ...],
                 config: PortfolioConfig | None = None, train_years: int = 3,
                 test_months: int = 6) -> pd.DataFrame:
    """Evaluate fixed candidates on sequential out-of-sample windows.

    No parameters are fitted from the test window. The function is intentionally a reporting primitive, not an
    optimizer: selection must be made by the caller using only prior windows.
    """
    config = config or PortfolioConfig()
    dates = pd.DatetimeIndex(sorted(prices["date"].unique()))
    rows: list[dict] = []
    start = dates.min() + pd.DateOffset(years=train_years)
    while start < dates.max():
        end = start + pd.DateOffset(months=test_months)
        window = prices[(prices["date"] >= start - pd.DateOffset(years=train_years)) &
                        (prices["date"] < end)]
        test_end = min(end, dates.max())
        for strategy in strategies:
            result = run_backtest(window, strategy, config)
            test_curve = result.equity.loc[result.equity.index >= start]
            test_trades = result.trades.loc[result.trades["date"] >= start]
            if len(test_curve) < 2:
                start = end
                continue
            test_metrics = performance_metrics(test_curve, test_trades, float(test_curve.iloc[0]))
            rows.append({"test_start": test_curve.index[0], "test_end": test_end,
                         "strategy": strategy, **test_metrics})
        start = end
    return pd.DataFrame(rows)
