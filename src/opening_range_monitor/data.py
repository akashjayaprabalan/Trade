from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
import yfinance as yf

from opening_range_monitor.market import ET, as_et, market_open_close, session_for_timestamp

BAR_COLUMNS = ["ticker", "timestamp", "session", "open", "high", "low", "close", "volume"]


def empty_bars_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=BAR_COLUMNS)


class YahooFinanceDataClient:
    def fetch_intraday(
        self,
        tickers: list[str],
        period: str = "1d",
        interval: str = "1m",
        include_prepost: bool = True,
    ) -> pd.DataFrame:
        if not tickers:
            return empty_bars_frame()
        try:
            raw = yf.download(
                tickers=" ".join(tickers),
                period=period,
                interval=interval,
                prepost=include_prepost,
                group_by="ticker",
                progress=False,
                auto_adjust=False,
                threads=True,
            )
        except Exception:
            return empty_bars_frame()
        return normalize_yfinance_download(raw, tickers)


def normalize_yfinance_download(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    if raw is None or raw.empty:
        return empty_bars_frame()

    frames = []
    if isinstance(raw.columns, pd.MultiIndex):
        level_zero = set(str(value).upper() for value in raw.columns.get_level_values(0))
        level_one = set(str(value).upper() for value in raw.columns.get_level_values(1))
        for ticker in tickers:
            ticker_upper = ticker.upper()
            if ticker_upper in level_zero:
                ticker_frame = raw[ticker_upper].copy()
            elif ticker_upper in level_one:
                ticker_frame = raw.xs(ticker_upper, level=1, axis=1).copy()
            else:
                continue
            frames.append(_normalize_single_ticker_frame(ticker_frame, ticker_upper))
    else:
        frames.append(_normalize_single_ticker_frame(raw.copy(), tickers[0].upper()))

    if not frames:
        return empty_bars_frame()

    bars = pd.concat(frames, ignore_index=True)
    bars = bars.dropna(subset=["open", "high", "low", "close"])
    bars = bars.sort_values(["ticker", "timestamp"]).reset_index(drop=True)
    return bars[BAR_COLUMNS]


def _normalize_single_ticker_frame(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    frame = frame.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    required = ["open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        return empty_bars_frame()

    normalized = frame[required].copy()
    normalized["ticker"] = ticker
    normalized["timestamp"] = [as_et(ts) for ts in normalized.index]
    normalized["session"] = [session_for_timestamp(ts) for ts in normalized["timestamp"]]
    normalized["volume"] = normalized["volume"].fillna(0).astype(float)
    return normalized[BAR_COLUMNS]


def generate_demo_bars(tickers: list[str], minutes: int = 75, day: pd.Timestamp | None = None) -> pd.DataFrame:
    target_day = (day or pd.Timestamp.now(tz=ET)).date()
    bounds = market_open_close(target_day)
    if bounds is None:
        target_day = pd.Timestamp("2024-01-02", tz=ET).date()
        bounds = market_open_close(target_day)
    market_open, _ = bounds
    timestamps = [market_open + timedelta(minutes=offset) for offset in range(minutes)]

    frames = []
    for index, ticker in enumerate(tickers):
        base = 100 + index * 35
        seed = sum(ord(char) for char in ticker)
        rng = np.random.default_rng(seed)
        drift = np.linspace(0, 1.4 + index * 0.25, minutes)
        wave = np.sin(np.linspace(0, 5, minutes)) * (0.55 + index * 0.05)
        noise = rng.normal(0, 0.08, minutes).cumsum()
        close = base + drift + wave + noise
        open_ = np.r_[close[0] - 0.08, close[:-1]]
        high = np.maximum(open_, close) + rng.uniform(0.04, 0.35, minutes)
        low = np.minimum(open_, close) - rng.uniform(0.04, 0.35, minutes)
        volume = rng.integers(85_000, 190_000, minutes).astype(float)
        volume[6:12] *= 2.4

        frames.append(
            pd.DataFrame(
                {
                    "ticker": ticker.upper(),
                    "timestamp": timestamps,
                    "session": ["regular"] * minutes,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)[BAR_COLUMNS]
