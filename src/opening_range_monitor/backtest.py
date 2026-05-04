from __future__ import annotations

import math

import numpy as np
import pandas as pd

from opening_range_monitor.config import AppConfig
from opening_range_monitor.market import as_et
from opening_range_monitor.models import BacktestResult, Trade, TradeSide
from opening_range_monitor.strategy import analysis_window_frame, evaluate_ticker_signals


def run_backtest(bars: pd.DataFrame, config: AppConfig) -> BacktestResult:
    if bars.empty:
        return _result([])

    trades: list[Trade] = []
    for ticker, ticker_frame in bars.groupby("ticker", sort=True):
        trades.extend(_backtest_ticker(ticker_frame, config, str(ticker)))
    return _result(trades)


def _backtest_ticker(ticker_bars: pd.DataFrame, config: AppConfig, ticker: str) -> list[Trade]:
    window = analysis_window_frame(ticker_bars, config)
    signals = evaluate_ticker_signals(ticker_bars, config, ticker)
    if len(window) < 2 or not signals:
        return []

    trades: list[Trade] = []
    position: dict[str, object] | None = None
    i = 0
    while i < len(signals):
        signal = signals[i]
        bar = window.iloc[i]

        if position is None:
            if signal.signal in {"BUY", "SELL"} and i + 1 < len(window):
                entry_bar = window.iloc[i + 1]
                position = {
                    "side": "LONG" if signal.signal == "BUY" else "SHORT",
                    "entry_timestamp": as_et(entry_bar["timestamp"]),
                    "entry_price": float(entry_bar["open"]),
                    "entry_index": i + 1,
                    "signal_rule": signal.rule_name,
                }
                i += 1
                continue
            i += 1
            continue

        if i < int(position["entry_index"]):
            i += 1
            continue

        exit_price, exit_reason = _exit_for_bar(position, bar, signal, config)
        if exit_price is not None and exit_reason is not None:
            trades.append(_close_trade(ticker, position, bar, exit_price, exit_reason))
            position = None
        i += 1

    if position is not None:
        last_bar = window.iloc[-1]
        trades.append(_close_trade(ticker, position, last_bar, float(last_bar["close"]), "window_close"))
    return trades


def _exit_for_bar(
    position: dict[str, object],
    bar: pd.Series,
    signal,
    config: AppConfig,
) -> tuple[float | None, str | None]:
    side = str(position["side"])
    entry_price = float(position["entry_price"])
    stop = config.stop_loss_pct / 100
    target = config.take_profit_pct / 100

    if side == "LONG":
        stop_price = entry_price * (1 - stop)
        target_price = entry_price * (1 + target)
        if float(bar["low"]) <= stop_price:
            return stop_price, "stop_loss"
        if float(bar["high"]) >= target_price:
            return target_price, "take_profit"
        if signal.signal == "SELL":
            return float(bar["close"]), "opposite_signal"
    else:
        stop_price = entry_price * (1 + stop)
        target_price = entry_price * (1 - target)
        if float(bar["high"]) >= stop_price:
            return stop_price, "stop_loss"
        if float(bar["low"]) <= target_price:
            return target_price, "take_profit"
        if signal.signal == "BUY":
            return float(bar["close"]), "opposite_signal"
    return None, None


def _close_trade(
    ticker: str,
    position: dict[str, object],
    exit_bar: pd.Series,
    exit_price: float,
    exit_reason: str,
) -> Trade:
    side = position["side"]
    entry_price = float(position["entry_price"])
    if side == "LONG":
        return_pct = ((exit_price / entry_price) - 1) * 100
    else:
        return_pct = ((entry_price / exit_price) - 1) * 100
    return Trade(
        ticker=ticker,
        side=side,  # type: ignore[arg-type]
        entry_timestamp=position["entry_timestamp"],  # type: ignore[arg-type]
        exit_timestamp=as_et(exit_bar["timestamp"]),
        entry_price=entry_price,
        exit_price=float(exit_price),
        return_pct=float(return_pct),
        exit_reason=exit_reason,
        signal_rule=str(position["signal_rule"]),
    )


def _result(trades: list[Trade]) -> BacktestResult:
    if not trades:
        return BacktestResult(
            trades=[],
            win_rate=0.0,
            average_return_pct=0.0,
            max_drawdown_pct=0.0,
            sharpe_ratio=0.0,
        )

    returns = np.array([trade.return_pct / 100 for trade in trades], dtype=float)
    win_rate = float((returns > 0).mean() * 100)
    average_return_pct = float(returns.mean() * 100)
    equity = np.cumprod(1 + returns)
    running_peak = np.maximum.accumulate(equity)
    drawdowns = (equity / running_peak) - 1
    max_drawdown_pct = float(abs(drawdowns.min()) * 100)
    sharpe_ratio = _sharpe(returns)
    return BacktestResult(
        trades=trades,
        win_rate=win_rate,
        average_return_pct=average_return_pct,
        max_drawdown_pct=max_drawdown_pct,
        sharpe_ratio=sharpe_ratio,
    )


def _sharpe(returns: np.ndarray) -> float:
    if len(returns) < 2:
        return 0.0
    std = returns.std(ddof=1)
    if std == 0 or math.isnan(std):
        return 0.0
    return float((returns.mean() / std) * math.sqrt(len(returns)))
