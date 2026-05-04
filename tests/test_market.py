from __future__ import annotations

import pandas as pd

from opening_range_monitor.market import ET, is_analysis_window, market_status, session_for_timestamp


def test_session_labeling_for_market_day() -> None:
    assert session_for_timestamp(pd.Timestamp("2024-01-02 08:00", tz=ET)) == "pre_market"
    assert session_for_timestamp(pd.Timestamp("2024-01-02 09:30", tz=ET)) == "regular"
    assert session_for_timestamp(pd.Timestamp("2024-01-02 17:00", tz=ET)) == "after_hours"


def test_weekend_is_closed() -> None:
    assert session_for_timestamp(pd.Timestamp("2024-01-06 10:00", tz=ET)) == "closed"


def test_analysis_window_detection() -> None:
    assert is_analysis_window(pd.Timestamp("2024-01-02 09:45", tz=ET), 30)
    assert not is_analysis_window(pd.Timestamp("2024-01-02 10:05", tz=ET), 30)
    assert not is_analysis_window(pd.Timestamp("2024-01-06 09:45", tz=ET), 30)


def test_market_status_before_open() -> None:
    status = market_status(pd.Timestamp("2024-01-02 08:45", tz=ET), window_minutes=30)

    assert status["is_open"] is False
    assert status["in_analysis_window"] is False
    assert status["session"] == "pre_market"
