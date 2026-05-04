from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

import pandas as pd
import pandas_market_calendars as mcal

from opening_range_monitor.models import SessionName

ET = ZoneInfo("America/New_York")
PRE_MARKET_START = time(4, 0)
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)
AFTER_HOURS_END = time(20, 0)


def as_et(timestamp: pd.Timestamp | datetime | str) -> pd.Timestamp:
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        return ts.tz_localize(ET)
    return ts.tz_convert(ET)


def _at_et(day: date, wall_time: time) -> pd.Timestamp:
    return pd.Timestamp(datetime.combine(day, wall_time), tz=ET)


@lru_cache(maxsize=256)
def market_open_close(day: date) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    calendar = mcal.get_calendar("NYSE")
    schedule = calendar.schedule(start_date=day, end_date=day)
    if schedule.empty:
        return None
    row = schedule.iloc[0]
    return as_et(row["market_open"]), as_et(row["market_close"])


def session_for_timestamp(timestamp: pd.Timestamp | datetime | str) -> SessionName:
    ts = as_et(timestamp)
    bounds = market_open_close(ts.date())
    if bounds is None:
        return "closed"

    market_open, market_close = bounds
    pre_market_start = _at_et(ts.date(), PRE_MARKET_START)
    after_hours_end = _at_et(ts.date(), AFTER_HOURS_END)

    if pre_market_start <= ts < market_open:
        return "pre_market"
    if market_open <= ts <= market_close:
        return "regular"
    if market_close < ts <= after_hours_end:
        return "after_hours"
    return "closed"


def is_analysis_window(timestamp: pd.Timestamp | datetime | str, window_minutes: int) -> bool:
    ts = as_et(timestamp)
    bounds = market_open_close(ts.date())
    if bounds is None:
        return False
    market_open, _ = bounds
    return market_open <= ts < market_open + timedelta(minutes=window_minutes)


def market_status(now: pd.Timestamp | datetime | str | None = None, window_minutes: int = 30) -> dict[str, object]:
    current = as_et(now or pd.Timestamp.now(tz=ET))
    bounds = market_open_close(current.date())
    if bounds is None:
        return {
            "is_open": False,
            "in_analysis_window": False,
            "session": "closed",
            "market_open": None,
            "market_close": None,
            "now": current,
        }

    market_open, market_close = bounds
    return {
        "is_open": market_open <= current <= market_close,
        "in_analysis_window": is_analysis_window(current, window_minutes),
        "session": session_for_timestamp(current),
        "market_open": market_open,
        "market_close": market_close,
        "now": current,
    }
