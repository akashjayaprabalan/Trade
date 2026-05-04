from __future__ import annotations

import logging
import time
from dataclasses import asdict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from opening_range_monitor.alerts import AlertManager
from opening_range_monitor.backtest import run_backtest
from opening_range_monitor.config import AppConfig, load_config
from opening_range_monitor.data import YahooFinanceDataClient, generate_demo_bars
from opening_range_monitor.market import market_status
from opening_range_monitor.models import BacktestResult, Signal
from opening_range_monitor.strategy import evaluate_signals

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    st.set_page_config(page_title="Opening Range Monitor", layout="wide")
    st.title("Opening Range Monitor")
    st.caption("Analytical signals only. No trade execution.")

    base_config = load_config()
    config = sidebar_config(base_config)
    client = YahooFinanceDataClient()

    live_tab, backtest_tab, config_tab = st.tabs(["Live Monitor", "Backtest", "Config"])
    with live_tab:
        render_live_monitor(client, config)
    with backtest_tab:
        render_backtest(client, config)
    with config_tab:
        render_config(config)


def sidebar_config(base_config: AppConfig) -> AppConfig:
    st.sidebar.header("Settings")
    tickers_text = st.sidebar.text_input("Tickers", value=", ".join(base_config.tickers))
    tickers = [ticker.strip() for ticker in tickers_text.split(",") if ticker.strip()]
    analysis_window = st.sidebar.slider("Analysis window", 10, 60, base_config.analysis_window_minutes, 5)
    opening_range = st.sidebar.slider(
        "Opening range",
        1,
        max(1, min(30, analysis_window - 1)),
        min(base_config.opening_range_minutes, analysis_window - 1),
        1,
    )
    poll_interval = st.sidebar.number_input(
        "Poll seconds",
        min_value=5,
        max_value=600,
        value=base_config.poll_interval_seconds,
        step=5,
    )
    breakout = st.sidebar.number_input(
        "Breakout %",
        min_value=0.0,
        value=base_config.breakout_threshold_pct,
        step=0.1,
    )
    volume = st.sidebar.number_input(
        "Volume x",
        min_value=0.0,
        value=base_config.volume_multiplier,
        step=0.1,
    )
    momentum = st.sidebar.number_input(
        "Momentum %",
        min_value=0.0,
        value=base_config.momentum_threshold_pct,
        step=0.1,
    )
    reversal = st.sidebar.number_input(
        "Reversal %",
        min_value=0.0,
        value=base_config.reversal_threshold_pct,
        step=0.1,
    )
    stop = st.sidebar.number_input("Stop %", min_value=0.01, value=base_config.stop_loss_pct, step=0.1)
    target = st.sidebar.number_input("Target %", min_value=0.01, value=base_config.take_profit_pct, step=0.1)

    return AppConfig(
        tickers=tickers,
        analysis_window_minutes=int(analysis_window),
        opening_range_minutes=int(opening_range),
        poll_interval_seconds=int(poll_interval),
        breakout_threshold_pct=float(breakout),
        volume_multiplier=float(volume),
        momentum_lookback_minutes=base_config.momentum_lookback_minutes,
        momentum_threshold_pct=float(momentum),
        reversal_threshold_pct=float(reversal),
        stop_loss_pct=float(stop),
        take_profit_pct=float(target),
        alerts=base_config.alerts,
    )


def render_live_monitor(client: YahooFinanceDataClient, config: AppConfig) -> None:
    status = market_status(window_minutes=config.analysis_window_minutes)
    source = st.radio("Data source", ["Yahoo Finance", "Demo fallback"], horizontal=True)
    auto_refresh = st.toggle("Auto refresh", value=False)
    refresh_clicked = st.button("Refresh", type="primary")

    bars = load_bars(client, config, period="1d", use_demo=source == "Demo fallback")
    signals = evaluate_signals(bars, config)
    latest = latest_signals(signals)
    alert_messages = AlertManager.from_config(config.alerts).dispatch(
        [signal for signal in latest if signal.signal in {"BUY", "SELL"}]
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Session", str(status["session"]).replace("_", " ").title())
    col2.metric("Market Open", fmt_timestamp(status["market_open"]))
    col3.metric("Analysis Window", "Active" if status["in_analysis_window"] else "Idle")
    col4.metric("Bars", f"{len(bars):,}")

    if bars.empty:
        st.warning("No intraday bars available.")
        return

    render_signal_table(latest)
    if alert_messages:
        st.info("\n".join(alert_messages))

    selected_ticker = st.selectbox("Chart ticker", config.tickers)
    render_price_chart(bars, signals, selected_ticker)

    if auto_refresh and not refresh_clicked:
        time.sleep(config.poll_interval_seconds)
        st.rerun()


def render_backtest(client: YahooFinanceDataClient, config: AppConfig) -> None:
    period = st.selectbox("Backtest period", ["1d", "5d", "7d"], index=1)
    source = st.radio("Backtest data source", ["Yahoo Finance", "Demo fallback"], horizontal=True)
    bars = load_bars(client, config, period=period, use_demo=source == "Demo fallback")
    result = run_backtest(bars, config)

    render_metrics(result)
    render_trades(result)
    if not bars.empty:
        selected_ticker = st.selectbox("Backtest chart ticker", config.tickers, key="backtest_ticker")
        render_price_chart(bars, evaluate_signals(bars, config), selected_ticker)


def render_config(config: AppConfig) -> None:
    st.json(config.model_dump())


@st.cache_data(ttl=45, show_spinner=False)
def _fetch_cached(tickers: tuple[str, ...], period: str) -> pd.DataFrame:
    return YahooFinanceDataClient().fetch_intraday(list(tickers), period=period)


def load_bars(client: YahooFinanceDataClient, config: AppConfig, period: str, use_demo: bool) -> pd.DataFrame:
    if use_demo:
        return generate_demo_bars(config.tickers, minutes=max(75, config.analysis_window_minutes + 15))
    bars = _fetch_cached(tuple(config.tickers), period)
    if bars.empty:
        st.warning("Yahoo Finance returned no usable bars. Showing demo data.")
        return generate_demo_bars(config.tickers, minutes=max(75, config.analysis_window_minutes + 15))
    return bars


def latest_signals(signals: list[Signal]) -> list[Signal]:
    latest: dict[str, Signal] = {}
    for signal in signals:
        latest[signal.ticker] = signal
    return list(latest.values())


def render_signal_table(signals: list[Signal]) -> None:
    if not signals:
        st.warning("No signals generated for the current window.")
        return
    data = [
        {
            "Ticker": signal.ticker,
            "Signal": signal.signal,
            "Rule": signal.rule_name,
            "Price": round(signal.price, 2),
            "Volume x": round(signal.volume_ratio or 0, 2),
            "ROC %": round(signal.roc_pct or 0, 2),
            "Reason": signal.reason,
        }
        for signal in signals
    ]
    st.dataframe(pd.DataFrame(data), width="stretch", hide_index=True)


def render_metrics(result: BacktestResult) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Trades", str(len(result.trades)))
    col2.metric("Win Rate", f"{result.win_rate:.1f}%")
    col3.metric("Avg Return", f"{result.average_return_pct:.2f}%")
    col4.metric("Max Drawdown", f"{result.max_drawdown_pct:.2f}%")
    st.metric("Sharpe", f"{result.sharpe_ratio:.2f}")


def render_trades(result: BacktestResult) -> None:
    if not result.trades:
        st.warning("No trades matched the current rules.")
        return
    st.dataframe(pd.DataFrame(asdict(trade) for trade in result.trades), width="stretch", hide_index=True)


def render_price_chart(bars: pd.DataFrame, signals: list[Signal], ticker: str) -> None:
    ticker_bars = bars[bars["ticker"].eq(ticker)].sort_values("timestamp")
    if ticker_bars.empty:
        st.warning(f"No bars available for {ticker}.")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=ticker_bars["timestamp"],
            y=ticker_bars["close"],
            mode="lines",
            name="Close",
            line={"color": "#2563eb", "width": 2},
        )
    )

    ticker_signals = [signal for signal in signals if signal.ticker == ticker and signal.signal != "HOLD"]
    for side, color, symbol in [("BUY", "#16a34a", "triangle-up"), ("SELL", "#dc2626", "triangle-down")]:
        side_signals = [signal for signal in ticker_signals if signal.signal == side]
        if not side_signals:
            continue
        fig.add_trace(
            go.Scatter(
                x=[signal.timestamp for signal in side_signals],
                y=[signal.price for signal in side_signals],
                mode="markers",
                name=side,
                marker={"color": color, "symbol": symbol, "size": 12},
                text=[signal.reason for signal in side_signals],
            )
        )

    fig.update_layout(
        height=440,
        margin={"l": 24, "r": 24, "t": 24, "b": 24},
        legend={"orientation": "h", "y": 1.08},
        xaxis_title=None,
        yaxis_title="Price",
    )
    st.plotly_chart(fig, width="stretch")


def fmt_timestamp(value: object) -> str:
    if value is None:
        return "Closed"
    return pd.Timestamp(value).strftime("%I:%M %p ET")


if __name__ == "__main__":
    main()
