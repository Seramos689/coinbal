#!/usr/bin/env python3
"""
Real-time TradingView-style Chart – Dash Web Version
====================================================
Uses:
  - Dash + dash_tvlwc (TradingView Lightweight Charts component)
  - Binance public data via the shared data_feed module
  - Technical indicators from the shared indicators module

Run:
  cd web_app
  pip install -r requirements_web.txt
  python app.py

Then open http://127.0.0.1:8050
"""

import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# Allow importing from parent utils/
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import dash
from dash import html, dcc, Input, Output, State, callback, no_update, clientside_callback
import dash_tvlwc
import pandas as pd

from utils.data_feed import BinanceDataFeed
from utils.indicators import (
    add_sma,
    add_ema,
    add_bollinger,
    prepare_indicator_line,
)

# ============================================================
# CONFIG
# ============================================================
DEFAULT_SYMBOL = "BTC/USDT"
DEFAULT_TIMEFRAME = "1m"
HISTORY_LIMIT = 400
UPDATE_INTERVAL_MS = 2000          # how often we push new data to the chart

# Global state (simple in-memory store for the latest candle)
# In production you would use Redis / a proper cache
_latest_bar = None
_feed = None
_history_df = None


def df_to_candles(df: pd.DataFrame) -> list:
    """Convert DataFrame to the list-of-dicts format expected by dash_tvlwc."""
    records = []
    for _, row in df.iterrows():
        t = row["time"]
        if isinstance(t, datetime):
            # Lightweight Charts accepts Unix timestamp (seconds) or ISO string
            time_val = int(t.timestamp())
        else:
            time_val = t
        records.append({
            "time": time_val,
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row.get("volume", 0)),
        })
    return records


def df_to_line(df: pd.DataFrame, column: str) -> list:
    """Convert indicator column to line series data."""
    records = []
    for _, row in df.iterrows():
        if pd.isna(row[column]):
            continue
        t = row["time"]
        time_val = int(t.timestamp()) if isinstance(t, datetime) else t
        records.append({"time": time_val, "value": float(row[column])})
    return records


def load_initial_data(symbol: str, timeframe: str):
    """Fetch history, compute indicators, return series list for the chart."""
    global _feed, _history_df, _latest_bar

    _feed = BinanceDataFeed(symbol=symbol, timeframe=timeframe)
    df = _feed.fetch_historical(limit=HISTORY_LIMIT)

    # Indicators
    df = add_sma(df, 20)
    df = add_sma(df, 50)
    df = add_ema(df, 12)
    df = add_ema(df, 26)
    df = add_bollinger(df, 20)

    _history_df = df.copy()
    _latest_bar = df.iloc[-1].to_dict()

    # Build series list for dash_tvlwc
    series = [
        {
            "id": "price",
            "type": "candlestick",
            "data": df_to_candles(df),
            "options": {
                "upColor": "#26a69a",
                "downColor": "#ef5350",
                "borderUpColor": "#26a69a",
                "borderDownColor": "#ef5350",
                "wickUpColor": "#26a69a",
                "wickDownColor": "#ef5350",
            },
        },
        {
            "id": "volume",
            "type": "histogram",
            "data": [
                {
                    "time": int(row["time"].timestamp()) if isinstance(row["time"], datetime) else row["time"],
                    "value": float(row["volume"]),
                    "color": "rgba(38,166,154,0.5)" if row["close"] >= row["open"] else "rgba(239,83,80,0.5)",
                }
                for _, row in df.iterrows()
            ],
            "options": {"priceFormat": {"type": "volume"}, "priceScaleId": ""},
            "pane": 1,          # second pane
        },
        {
            "id": "sma20",
            "type": "line",
            "data": df_to_line(df, "SMA_20"),
            "options": {"color": "#f0b90b", "lineWidth": 2},
        },
        {
            "id": "sma50",
            "type": "line",
            "data": df_to_line(df, "SMA_50"),
            "options": {"color": "#e91e63", "lineWidth": 2},
        },
        {
            "id": "bb_upper",
            "type": "line",
            "data": df_to_line(df, "BB_UPPER_20"),
            "options": {"color": "rgba(33,150,243,0.6)", "lineWidth": 1},
        },
        {
            "id": "bb_lower",
            "type": "line",
            "data": df_to_line(df, "BB_LOWER_20"),
            "options": {"color": "rgba(33,150,243,0.6)", "lineWidth": 1},
        },
    ]
    return series


# ============================================================
# Dash App
# ============================================================
app = dash.Dash(
    __name__,
    title="TradingView Real-time Chart",
    update_title=None,
    suppress_callback_exceptions=True,
)

# Dark theme CSS
app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                margin: 0;
                padding: 0;
                background-color: #0d1117;
                color: #e6edf3;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            }
            .header {
                display: flex;
                align-items: center;
                gap: 16px;
                padding: 12px 20px;
                background: #161b22;
                border-bottom: 1px solid #30363d;
            }
            .header h1 {
                margin: 0;
                font-size: 1.25rem;
                font-weight: 600;
                color: #f0b90b;
            }
            .controls {
                display: flex;
                gap: 10px;
                align-items: center;
                margin-left: auto;
            }
            .controls select, .controls button {
                background: #21262d;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 0.9rem;
            }
            .controls button {
                cursor: pointer;
                background: #238636;
                border-color: #238636;
            }
            .controls button:hover {
                background: #2ea043;
            }
            .status {
                font-size: 0.85rem;
                color: #8b949e;
                padding: 4px 20px;
            }
            .chart-container {
                padding: 8px;
                height: calc(100vh - 90px);
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""

# Initial series (loaded once at startup)
print("Loading initial market data …")
try:
    INITIAL_SERIES = load_initial_data(DEFAULT_SYMBOL, DEFAULT_TIMEFRAME)
    print(f"Loaded {len(INITIAL_SERIES[0]['data'])} candles for {DEFAULT_SYMBOL}")
except Exception as e:
    print(f"Warning: could not load live data ({e}). Using empty chart.")
    INITIAL_SERIES = [{"id": "price", "type": "candlestick", "data": []}]


app.layout = html.Div([
    # Header
    html.Div([
        html.H1("📈 Real-time TradingView Chart"),
        html.Div([
            dcc.Dropdown(
                id="symbol-dropdown",
                options=[
                    {"label": "BTC/USDT", "value": "BTC/USDT"},
                    {"label": "ETH/USDT", "value": "ETH/USDT"},
                    {"label": "SOL/USDT", "value": "SOL/USDT"},
                    {"label": "BNB/USDT", "value": "BNB/USDT"},
                    {"label": "XRP/USDT", "value": "XRP/USDT"},
                ],
                value=DEFAULT_SYMBOL,
                clearable=False,
                style={"width": "140px", "color": "#000"},
            ),
            dcc.Dropdown(
                id="timeframe-dropdown",
                options=[
                    {"label": "1m", "value": "1m"},
                    {"label": "5m", "value": "5m"},
                    {"label": "15m", "value": "15m"},
                    {"label": "1h", "value": "1h"},
                    {"label": "4h", "value": "4h"},
                    {"label": "1d", "value": "1d"},
                ],
                value=DEFAULT_TIMEFRAME,
                clearable=False,
                style={"width": "90px", "color": "#000"},
            ),
            html.Button("Reload", id="reload-btn", n_clicks=0),
        ], className="controls"),
    ], className="header"),

    # Status line
    html.Div(id="status-bar", className="status", children="Connecting …"),

    # Chart
    html.Div([
        dash_tvlwc.Tvlwc(
            id="tv-chart",
            series=INITIAL_SERIES,
            width="100%",
            height=700,
            chartOptions={
                "layout": {
                    "background": {"type": "solid", "color": "#0d1117"},
                    "textColor": "#e6edf3",
                },
                "grid": {
                    "vertLines": {"color": "rgba(42,46,57,0.6)"},
                    "horzLines": {"color": "rgba(42,46,57,0.6)"},
                },
                "crosshair": {"mode": 0},
                "rightPriceScale": {"borderColor": "#30363d"},
                "timeScale": {
                    "borderColor": "#30363d",
                    "timeVisible": True,
                    "secondsVisible": False,
                },
            },
        ),
    ], className="chart-container"),

    # Hidden stores & interval for real-time updates
    dcc.Store(id="series-store", data=INITIAL_SERIES),
    dcc.Interval(id="update-interval", interval=UPDATE_INTERVAL_MS, n_intervals=0),
    dcc.Store(id="last-price-store", data=None),
])


# ----------------------------------------------------------
# Callbacks
# ----------------------------------------------------------

@callback(
    Output("tv-chart", "series"),
    Output("status-bar", "children"),
    Output("series-store", "data"),
    Input("reload-btn", "n_clicks"),
    Input("symbol-dropdown", "value"),
    Input("timeframe-dropdown", "value"),
    prevent_initial_call=False,
)
def reload_chart(n_clicks, symbol, timeframe):
    """Full reload when symbol / timeframe changes or Reload is clicked."""
    try:
        series = load_initial_data(symbol, timeframe)
        last_close = series[0]["data"][-1]["close"] if series[0]["data"] else 0
        status = f"{symbol} · {timeframe} · Last close: {last_close:,.2f} · {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC"
        return series, status, series
    except Exception as e:
        return no_update, f"Error loading data: {e}", no_update


@callback(
    Output("tv-chart", "series", allow_duplicate=True),
    Output("status-bar", "children", allow_duplicate=True),
    Input("update-interval", "n_intervals"),
    State("series-store", "data"),
    State("symbol-dropdown", "value"),
    prevent_initial_call=True,
)
def live_update(n, current_series, symbol):
    """
    Periodically fetch the latest candle from Binance REST
    (simpler & more reliable than keeping a long-lived WebSocket
    inside a multi-worker Dash process) and patch the chart.
    """
    if not current_series or not _feed:
        return no_update, no_update

    try:
        # Fetch only the most recent candle
        latest = _feed.exchange.fetch_ohlcv(symbol, timeframe=_feed.timeframe, limit=2)
        if not latest:
            return no_update, no_update

        # Use the last (possibly still-forming) candle
        ts, o, h, l, c, v = latest[-1]
        bar = {
            "time": int(ts / 1000),
            "open": float(o),
            "high": float(h),
            "low": float(l),
            "close": float(c),
            "volume": float(v),
        }

        # Deep-copy the series list so Dash detects the change
        import copy
        series = copy.deepcopy(current_series)

        # Update or append the price candle
        price_data = series[0]["data"]
        if price_data and price_data[-1]["time"] == bar["time"]:
            price_data[-1] = bar          # update forming candle
        else:
            price_data.append(bar)        # new candle

        # Keep volume in sync (pane 1)
        if len(series) > 1 and series[1]["id"] == "volume":
            vol_color = "rgba(38,166,154,0.5)" if bar["close"] >= bar["open"] else "rgba(239,83,80,0.5)"
            vol_point = {"time": bar["time"], "value": bar["volume"], "color": vol_color}
            vol_data = series[1]["data"]
            if vol_data and vol_data[-1]["time"] == bar["time"]:
                vol_data[-1] = vol_point
            else:
                vol_data.append(vol_point)

        status = (
            f"{symbol} · {_feed.timeframe} · "
            f"O:{bar['open']:,.2f} H:{bar['high']:,.2f} "
            f"L:{bar['low']:,.2f} C:{bar['close']:,.2f} · "
            f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC"
        )
        return series, status

    except Exception as e:
        return no_update, f"Live update error: {e}"

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8050))
    print("\n" + "=" * 55)
    print("  Dash TradingView Real-time Chart")
    print(f"  Open → http://0.0.0.0:{port}")
    print("=" * 55 + "\n")
    app.run(debug=False, host="0.0.0.0", port=port)
