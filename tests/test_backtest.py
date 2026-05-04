from __future__ import annotations

from opening_range_monitor.backtest import run_backtest
from opening_range_monitor.config import AppConfig

from tests.conftest import make_bars


def test_backtest_enters_next_bar_and_exits_at_target(base_config) -> None:
    bars = make_bars(
        [100.0, 100.1, 100.0, 101.0, 101.8],
        opens=[100.0, 100.0, 100.1, 100.0, 101.0],
        highs=[100.2, 100.3, 100.2, 101.2, 102.0],
        lows=[99.8, 99.9, 99.8, 100.7, 100.8],
        volumes=[1000, 1000, 1000, 2200, 1000],
    )

    result = run_backtest(bars, base_config)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.side == "LONG"
    assert trade.entry_price == 101.0
    assert trade.exit_reason == "take_profit"
    assert round(trade.return_pct, 2) == 0.5
    assert result.win_rate == 100.0


def test_backtest_stop_loss_exit(base_config) -> None:
    bars = make_bars(
        [100.0, 100.1, 100.0, 101.0, 100.2],
        opens=[100.0, 100.0, 100.1, 100.0, 101.0],
        highs=[100.2, 100.3, 100.2, 101.2, 101.1],
        lows=[99.8, 99.9, 99.8, 100.7, 100.0],
        volumes=[1000, 1000, 1000, 2200, 1000],
    )

    result = run_backtest(bars, base_config)

    assert result.trades[0].exit_reason == "stop_loss"
    assert round(result.trades[0].return_pct, 2) == -0.5


def test_backtest_opposite_signal_exit() -> None:
    config = AppConfig(
        tickers=["TEST"],
        analysis_window_minutes=10,
        opening_range_minutes=3,
        breakout_threshold_pct=0.2,
        volume_multiplier=1.2,
        momentum_lookback_minutes=2,
        momentum_threshold_pct=0.2,
        reversal_threshold_pct=0.2,
        stop_loss_pct=5.0,
        take_profit_pct=5.0,
    )
    bars = make_bars(
        [100.0, 100.1, 100.0, 101.0, 99.0],
        opens=[100.0, 100.0, 100.1, 100.0, 101.0],
        highs=[100.2, 100.3, 100.2, 101.2, 101.1],
        lows=[99.8, 99.9, 99.8, 100.7, 98.8],
        volumes=[1000, 1000, 1000, 2200, 2200],
    )

    result = run_backtest(bars, config)

    assert result.trades[0].exit_reason == "opposite_signal"


def test_backtest_window_close_exit() -> None:
    config = AppConfig(
        tickers=["TEST"],
        analysis_window_minutes=10,
        opening_range_minutes=3,
        breakout_threshold_pct=0.2,
        volume_multiplier=1.2,
        momentum_lookback_minutes=2,
        momentum_threshold_pct=0.2,
        reversal_threshold_pct=0.2,
        stop_loss_pct=5.0,
        take_profit_pct=5.0,
    )
    bars = make_bars(
        [100.0, 100.1, 100.0, 101.0, 101.2],
        opens=[100.0, 100.0, 100.1, 100.0, 101.0],
        highs=[100.2, 100.3, 100.2, 101.2, 101.3],
        lows=[99.8, 99.9, 99.8, 100.7, 100.9],
        volumes=[1000, 1000, 1000, 2200, 1000],
    )

    result = run_backtest(bars, config)

    assert result.trades[0].exit_reason == "window_close"


def test_backtest_metrics_include_drawdown_and_sharpe(base_config) -> None:
    bars = make_bars(
        [100.0, 100.1, 100.0, 101.0, 100.2, 99.0, 98.0, 99.0],
        opens=[100.0, 100.0, 100.1, 100.0, 101.0, 100.2, 99.0, 98.0],
        highs=[100.2, 100.3, 100.2, 101.2, 101.1, 100.3, 99.1, 99.2],
        lows=[99.8, 99.9, 99.8, 100.7, 100.0, 98.8, 97.8, 97.9],
        volumes=[1000, 1000, 1000, 2200, 1000, 2200, 1000, 2200],
    )

    result = run_backtest(bars, base_config)

    assert result.average_return_pct != 0
    assert result.max_drawdown_pct >= 0
    assert isinstance(result.sharpe_ratio, float)
