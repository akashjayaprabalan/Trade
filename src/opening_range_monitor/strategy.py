from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd

from opening_range_monitor.config import AppConfig
from opening_range_monitor.market import as_et, market_open_close
from opening_range_monitor.models import Signal, SignalSide


@dataclass(frozen=True)
class RuleCandidate:
    side: SignalSide
    rule_name: str
    reason: str


def evaluate_signals(bars: pd.DataFrame, config: AppConfig) -> list[Signal]:
    if bars.empty:
        return []
    signals: list[Signal] = []
    for ticker, ticker_frame in bars.groupby("ticker", sort=True):
        signals.extend(evaluate_ticker_signals(ticker_frame, config, str(ticker)))
    return sorted(signals, key=lambda signal: (signal.ticker, signal.timestamp))


def evaluate_ticker_signals(ticker_bars: pd.DataFrame, config: AppConfig, ticker: str | None = None) -> list[Signal]:
    window = analysis_window_frame(ticker_bars, config)
    if window.empty:
        return []

    ticker_name = ticker or str(window.iloc[0]["ticker"])
    opening_price = float(window.iloc[0]["open"])
    baseline_range_end = min(config.opening_range_minutes, len(window))
    baseline = window.iloc[:baseline_range_end]
    baseline_volume = float(baseline["volume"].replace(0, pd.NA).dropna().mean() or 0)

    signals: list[Signal] = []
    for position, (_, bar) in enumerate(window.iterrows()):
        current_baseline = window.iloc[: min(config.opening_range_minutes, position + 1)]
        opening_range_high = float(current_baseline["high"].max())
        opening_range_low = float(current_baseline["low"].min())
        price = float(bar["close"])
        volume_ratio = _safe_ratio(float(bar["volume"]), baseline_volume)
        roc_pct = _roc_pct(window, position, config.momentum_lookback_minutes)

        if position + 1 < config.opening_range_minutes:
            signals.append(
                Signal(
                    timestamp=as_et(bar["timestamp"]),
                    ticker=ticker_name,
                    signal="HOLD",
                    rule_name="opening_range",
                    price=price,
                    opening_price=opening_price,
                    opening_range_high=opening_range_high,
                    opening_range_low=opening_range_low,
                    volume_ratio=volume_ratio,
                    roc_pct=roc_pct,
                    reason=f"Collecting opening range ({position + 1}/{config.opening_range_minutes} bars).",
                )
            )
            continue

        completed_baseline = window.iloc[: config.opening_range_minutes]
        opening_range_high = float(completed_baseline["high"].max())
        opening_range_low = float(completed_baseline["low"].min())
        candidates = _rule_candidates(
            bar=bar,
            price=price,
            opening_price=opening_price,
            opening_range_high=opening_range_high,
            opening_range_low=opening_range_low,
            volume_ratio=volume_ratio,
            roc_pct=roc_pct,
            config=config,
        )
        signal, rule_name, reason = _combine_candidates(candidates)
        signals.append(
            Signal(
                timestamp=as_et(bar["timestamp"]),
                ticker=ticker_name,
                signal=signal,
                rule_name=rule_name,
                price=price,
                opening_price=opening_price,
                opening_range_high=opening_range_high,
                opening_range_low=opening_range_low,
                volume_ratio=volume_ratio,
                roc_pct=roc_pct,
                reason=reason,
            )
        )
    return signals


def analysis_window_frame(ticker_bars: pd.DataFrame, config: AppConfig) -> pd.DataFrame:
    if ticker_bars.empty:
        return ticker_bars.copy()

    frame = ticker_bars.copy()
    frame["timestamp"] = [as_et(ts) for ts in frame["timestamp"]]
    frame = frame[frame["session"].eq("regular")].sort_values("timestamp").reset_index(drop=True)
    if frame.empty:
        return frame

    first_timestamp = as_et(frame.iloc[0]["timestamp"])
    bounds = market_open_close(first_timestamp.date())
    if bounds is None:
        market_open = first_timestamp
    else:
        market_open, _ = bounds
    window_end = market_open + timedelta(minutes=config.analysis_window_minutes)
    return frame[(frame["timestamp"] >= market_open) & (frame["timestamp"] < window_end)].reset_index(drop=True)


def _rule_candidates(
    bar: pd.Series,
    price: float,
    opening_price: float,
    opening_range_high: float,
    opening_range_low: float,
    volume_ratio: float | None,
    roc_pct: float | None,
    config: AppConfig,
) -> list[RuleCandidate]:
    candidates: list[RuleCandidate] = []
    has_volume = volume_ratio is not None and volume_ratio >= config.volume_multiplier

    breakout_factor = config.breakout_threshold_pct / 100
    if has_volume and price > opening_range_high * (1 + breakout_factor):
        candidates.append(
            RuleCandidate(
                side="BUY",
                rule_name="breakout",
                reason="Price cleared the opening-range high with volume confirmation.",
            )
        )
    if has_volume and price < opening_range_low * (1 - breakout_factor):
        candidates.append(
            RuleCandidate(
                side="SELL",
                rule_name="breakout",
                reason="Price broke the opening-range low with volume confirmation.",
            )
        )

    if roc_pct is not None and has_volume:
        if roc_pct >= config.momentum_threshold_pct and price > opening_price:
            candidates.append(
                RuleCandidate(
                    side="BUY",
                    rule_name="momentum",
                    reason="Positive short-term ROC continued above the opening price.",
                )
            )
        if roc_pct <= -config.momentum_threshold_pct and price < opening_price:
            candidates.append(
                RuleCandidate(
                    side="SELL",
                    rule_name="momentum",
                    reason="Negative short-term ROC continued below the opening price.",
                )
            )

    reversal_factor = config.reversal_threshold_pct / 100
    if float(bar["low"]) <= opening_range_low * (1 - reversal_factor) and price > opening_price:
        candidates.append(
            RuleCandidate(
                side="BUY",
                rule_name="reversal",
                reason="Price rejected the opening-range low and closed back above the opening price.",
            )
        )
    if float(bar["high"]) >= opening_range_high * (1 + reversal_factor) and price < opening_price:
        candidates.append(
            RuleCandidate(
                side="SELL",
                rule_name="reversal",
                reason="Price rejected the opening-range high and closed back below the opening price.",
            )
        )
    return candidates


def _combine_candidates(candidates: list[RuleCandidate]) -> tuple[SignalSide, str, str]:
    if not candidates:
        return "HOLD", "none", "No strategy rule triggered."

    sides = {candidate.side for candidate in candidates}
    if "BUY" in sides and "SELL" in sides:
        rules = ", ".join(f"{candidate.rule_name}:{candidate.side}" for candidate in candidates)
        return "HOLD", "conflict", f"Conflicting rules detected ({rules})."

    side = candidates[0].side
    rule_names = "+".join(dict.fromkeys(candidate.rule_name for candidate in candidates))
    reasons = " ".join(candidate.reason for candidate in candidates)
    return side, rule_names, reasons


def _roc_pct(frame: pd.DataFrame, position: int, lookback: int) -> float | None:
    if position - lookback < 0:
        return None
    prior_close = float(frame.iloc[position - lookback]["close"])
    if prior_close == 0:
        return None
    current_close = float(frame.iloc[position]["close"])
    return ((current_close / prior_close) - 1) * 100


def _safe_ratio(value: float, baseline: float) -> float | None:
    if baseline <= 0:
        return None
    return value / baseline
