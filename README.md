# Opening Range Monitor

Local Streamlit MVP for monitoring US equity opening-range price action, generating short-term BUY/SELL/HOLD signals, and backtesting simple paper trades on intraday bars.

## Quick Start

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
streamlit run src/opening_range_monitor/app.py
```

## Notes

- Market data is fetched with `yfinance` and may be delayed or rate-limited.
- Signals are analytics only. The app does not place trades.
- If Yahoo returns no data, the dashboard can fall back to deterministic demo bars so the UI remains usable.
