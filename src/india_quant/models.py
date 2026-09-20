from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

StrategyName = Literal["buy_hold", "equal_weight", "balanced", "defensive_rotation"]


@dataclass(frozen=True)
class PortfolioConfig:
    initial_capital: float = 50_000.0
    cost_rate: float = 0.0015
    slippage_rate: float = 0.0005
    rebalance_month_end: bool = True
    max_asset_weight: float = 0.70
    min_cash_buffer: float = 0.05
    primary_symbol: str = "NIFTYBEES.NS"

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if not 0 <= self.cost_rate < 1 or not 0 <= self.slippage_rate < 1:
            raise ValueError("cost and slippage rates must be in [0, 1)")
        if not 0 < self.max_asset_weight <= 1:
            raise ValueError("max_asset_weight must be in (0, 1]")
        if not 0 <= self.min_cash_buffer < 1:
            raise ValueError("min_cash_buffer must be in [0, 1)")


@dataclass(frozen=True)
class BacktestResult:
    strategy: StrategyName
    equity: pd.Series
    weights: pd.DataFrame
    holdings: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict[str, float]


RESEARCH_UNIVERSE = ("NIFTYBEES.NS", "GOLDBEES.NS", "LIQUIDBEES.NS")
