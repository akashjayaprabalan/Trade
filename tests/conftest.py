from __future__ import annotations

from datetime import timedelta

import pandas as pd
import pytest

from opening_range_monitor.config import AppConfig
from opening_range_monitor.market import ET


@pytest.fixture
def base_config() -> AppConfig:
    return AppConfig(
        tickers=["TEST"],
        analysis_window_minutes=10,
        opening_range_minutes=3,
        poll_interval_seconds=60,
        breakout_threshold_pct=0.2,
        volume_multiplier=1.2,
        momentum_lookback_minutes=2,
        momentum_threshold_pct=0.2,
        reversal_threshold_pct=0.2,
        stop_loss_pct=0.5,
        take_profit_pct=0.5,
    )


def make_bars(
    closes: list[float],
    *,
    opens: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
    ticker: str = "TEST",
) -> pd.DataFrame:
    start = pd.Timestamp("2024-01-02 09:30", tz=ET)
    rows = []
    for index, close in enumerate(closes):
        open_price = opens[index] if opens else (closes[index - 1] if index else close)
        high = highs[index] if highs else max(open_price, close) + 0.2
        low = lows[index] if lows else min(open_price, close) - 0.2
        volume = volumes[index] if volumes else 1000.0
        rows.append(
            {
                "ticker": ticker,
                "timestamp": start + timedelta(minutes=index),
                "session": "regular",
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )
    return pd.DataFrame(rows)
