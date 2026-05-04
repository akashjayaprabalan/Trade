from __future__ import annotations

from opening_range_monitor.strategy import evaluate_signals

from tests.conftest import make_bars


def test_breakout_buy_signal(base_config) -> None:
    bars = make_bars(
        [100.0, 100.1, 100.0, 101.0],
        highs=[100.2, 100.3, 100.2, 101.2],
        lows=[99.8, 99.9, 99.8, 100.7],
        volumes=[1000, 1000, 1000, 2200],
    )

    signals = evaluate_signals(bars, base_config)

    assert signals[-1].signal == "BUY"
    assert "breakout" in signals[-1].rule_name


def test_reversal_sell_signal(base_config) -> None:
    bars = make_bars(
        [100.0, 100.1, 100.0, 99.6],
        highs=[100.2, 100.4, 100.2, 101.0],
        lows=[99.8, 99.9, 99.8, 99.55],
        volumes=[1000, 1000, 1000, 1000],
    )

    signals = evaluate_signals(bars, base_config)

    assert signals[-1].signal == "SELL"
    assert signals[-1].rule_name == "reversal"


def test_momentum_continuation_signal(base_config) -> None:
    bars = make_bars(
        [100.0, 100.1, 100.2, 100.45],
        highs=[100.2, 100.25, 100.35, 100.5],
        lows=[99.8, 99.9, 100.0, 100.2],
        volumes=[1000, 1000, 1000, 1800],
    )

    signals = evaluate_signals(bars, base_config)

    assert signals[-1].signal == "BUY"
    assert "momentum" in signals[-1].rule_name


def test_conflicting_rules_hold(base_config) -> None:
    bars = make_bars(
        [101.2, 101.1, 101.3, 100.5],
        opens=[100.0, 101.2, 101.1, 101.3],
        highs=[102.0, 102.0, 102.0, 101.0],
        lows=[101.0, 101.0, 101.0, 100.0],
        volumes=[1000, 1000, 1000, 1800],
    )

    signals = evaluate_signals(bars, base_config)

    assert signals[-1].signal == "HOLD"
    assert signals[-1].rule_name == "conflict"
    assert "Conflicting rules" in signals[-1].reason


def test_opening_range_collection_is_hold(base_config) -> None:
    bars = make_bars([100.0, 100.1])

    signals = evaluate_signals(bars, base_config)

    assert [signal.signal for signal in signals] == ["HOLD", "HOLD"]
    assert signals[-1].reason == "Collecting opening range (2/3 bars)."
