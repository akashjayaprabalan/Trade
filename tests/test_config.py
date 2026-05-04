from __future__ import annotations

import pytest

from opening_range_monitor.config import AppConfig, load_config


def test_default_config_matches_mvp_defaults() -> None:
    config = load_config("configs/default.yaml")

    assert config.tickers == ["AAPL", "TSLA", "NVDA"]
    assert config.analysis_window_minutes == 30
    assert config.opening_range_minutes == 5
    assert config.breakout_threshold_pct == 0.5
    assert config.volume_multiplier == 1.5
    assert config.alerts.channels == ["log"]


def test_config_normalizes_tickers_and_rejects_empty_lists() -> None:
    config = AppConfig(tickers=[" aapl ", "AAPL", " tsla "])

    assert config.tickers == ["AAPL", "TSLA"]

    with pytest.raises(ValueError):
        AppConfig(tickers=[" ", ""])


def test_config_rejects_opening_range_equal_to_analysis_window() -> None:
    with pytest.raises(ValueError):
        AppConfig(tickers=["AAPL"], analysis_window_minutes=5, opening_range_minutes=5)
