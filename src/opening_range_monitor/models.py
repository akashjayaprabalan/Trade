from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

SignalSide = Literal["BUY", "SELL", "HOLD"]
TradeSide = Literal["LONG", "SHORT"]
SessionName = Literal["pre_market", "regular", "after_hours", "closed"]


@dataclass(frozen=True)
class MarketBar:
    ticker: str
    timestamp: pd.Timestamp
    session: SessionName
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Signal:
    timestamp: pd.Timestamp
    ticker: str
    signal: SignalSide
    rule_name: str
    price: float
    opening_price: float | None
    opening_range_high: float | None
    opening_range_low: float | None
    volume_ratio: float | None
    roc_pct: float | None
    reason: str


@dataclass(frozen=True)
class Trade:
    ticker: str
    side: TradeSide
    entry_timestamp: pd.Timestamp
    exit_timestamp: pd.Timestamp
    entry_price: float
    exit_price: float
    return_pct: float
    exit_reason: str
    signal_rule: str


@dataclass(frozen=True)
class BacktestResult:
    trades: list[Trade]
    win_rate: float
    average_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
