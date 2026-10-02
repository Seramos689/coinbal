#!/usr/bin/env python3
"""
Real-time TradingView-style Chart – Complete Python Project
===========================================================
Uses:
  - lightweight-charts  (TradingView Lightweight Charts wrapper)
  - Binance public data via ccxt + WebSocket
  - Technical indicators (SMA, EMA, RSI, Bollinger, MACD)

How to run:
  1. pip install -r requirements.txt
  2. python main.py

Press Ctrl+C to quit.
"""

import sys
import time
from datetime import datetime, timezone

import pandas as pd
from lightweight_charts import Chart

from utils.data_feed import BinanceDataFeed
from utils.indicators import (
    add_sma,
    add_ema,
    add_rsi,
    add_bollinger,
    add_macd,
    prepare_indicator_line,
)


# ============================================================
# CONFIGURATION – change these to your liking
# ============================================================
SYMBOL = "BTC/USDT"          # Binance spot symbol
TIMEFRAME = "1m"             # 1m, 5m, 15m, 1h, 4h, 1d …
HISTORY_LIMIT = 500          # number of historical candles to load
SHOW_VOLUME = True
SHOW_SMA = True
SHOW_EMA = True
SHOW_BOLLINGER = True
SHOW_RSI = False             # RSI is usually better on a separate pane (advanced)
DARK_THEME = True


def create_chart() -> Chart:
    """Create and style the main chart."""
    chart = Chart(
        width=1400,
        height=800,
        toolbox=True,            # enables drawing tools
        # scale_candles_only=True,
    )

    if DARK_THEME:
        chart.layout(
            background_color="#131722",
            text_color="#d1d4dc",
            font_size=12,
            font_family="Trebuchet MS",
        )
        chart.candle_style(
            up_color="#26a69a",
            down_color="#ef5350",
            border_up_color="#26a69a",
            border_down_color="#ef5350",
            wick_up_color="#26a69a",
            wick_down_color="#ef5350",
        )
        chart.volume_config(
            up_color="rgba(38,166,154,0.5)",
            down_color="rgba(239,83,80,0.5)",
        )
        chart.grid(
            vert_enabled=True,
            horz_enabled=True,
            color="rgba(42,46,57,0.6)",
        )
        chart.crosshair(
            mode="normal",
            vert_color="#758696",
            horz_color="#758696",
        )
    else:
        chart.layout(background_color="#ffffff", text_color="#191919")

    chart.legend(visible=True)
    chart.time_scale(right_offset=12, min_bar_spacing=0.5)
    return chart


def main():
    print("=" * 60)
    print("  Real-time TradingView-style Chart (Python)")
    print(f"  Symbol : {SYMBOL}   Timeframe : {TIMEFRAME}")
    print("=" * 60)

    # --------------------------------------------------------
    # 1. Data feed
    # --------------------------------------------------------
    feed = BinanceDataFeed(symbol=SYMBOL, timeframe=TIMEFRAME)

    print("\n[1/4] Fetching historical data …")
    try:
        df = feed.fetch_historical(limit=HISTORY_LIMIT)
        print(f"      Loaded {len(df)} candles  |  Last close: {df['close'].iloc[-1]:.2f}")
    except Exception as e:
        print(f"ERROR fetching history: {e}")
        print("Check your internet connection or try a different symbol.")
        sys.exit(1)

    # --------------------------------------------------------
    # 2. Indicators
    # --------------------------------------------------------
    print("[2/4] Calculating indicators …")
    if SHOW_SMA:
        df = add_sma(df, period=20)
        df = add_sma(df, period=50)
    if SHOW_EMA:
        df = add_ema(df, period=12)
        df = add_ema(df, period=26)
    if SHOW_BOLLINGER:
        df = add_bollinger(df, period=20, std_dev=2.0)
    if SHOW_RSI:
        df = add_rsi(df, period=14)
    df = add_macd(df)   # always compute, you can choose to display later

    # --------------------------------------------------------
    # 3. Create chart & plot historical data
    # --------------------------------------------------------
    print("[3/4] Creating chart window …")
    chart = create_chart()

    # Main candlestick series
    chart.set(df)

    # Volume (built-in)
    if SHOW_VOLUME:
        chart.volume_config(visible=True)

    # Overlay lines
    lines = {}

    if SHOW_SMA:
        for period in (20, 50):
            col = f"SMA_{period}"
            line_df = prepare_indicator_line(df, col)
            line = chart.create_line(name=col, color="#f0b90b" if period == 20 else "#e91e63")
            line.set(line_df)
            lines[col] = line

    if SHOW_EMA:
        for period in (12, 26):
            col = f"EMA_{period}"
            line_df = prepare_indicator_line(df, col)
            line = chart.create_line(name=col, color="#2196f3" if period == 12 else "#9c27b0")
            line.set(line_df)
            lines[col] = line

    if SHOW_BOLLINGER:
        for col, color in [
            ("BB_UPPER_20", "rgba(33,150,243,0.5)"),
            ("BB_MID_20", "rgba(33,150,243,0.8)"),
            ("BB_LOWER_20", "rgba(33,150,243,0.5)"),
        ]:
            line_df = prepare_indicator_line(df, col)
            line = chart.create_line(name=col, color=color, width=1)
            line.set(line_df)
            lines[col] = line

    # Show the window (non-blocking so we can keep updating)
    chart.show(block=False)

    # --------------------------------------------------------
    # 4. Real-time streaming
    # --------------------------------------------------------
    print("[4/4] Starting real-time stream …")
    print("      Chart window should be open. Press Ctrl+C to exit.\n")

    last_bar_time = df["time"].iloc[-1]

    def on_new_bar(bar: dict):
        """Callback called by the WebSocket feed for every kline update."""
        nonlocal last_bar_time

        # Convert to Series so chart.update accepts it
        series = pd.Series(bar)

        # Update the main candlestick
        chart.update(series)

        # Optional: also update indicators in real-time (simple approach)
        # For production you would keep a rolling buffer and recalculate
        # only the latest values. Here we just keep the lines static for clarity.

        # Print a small status line
        ts = bar["time"].strftime("%H:%M:%S") if isinstance(bar["time"], datetime) else bar["time"]
        print(f"\r[{ts}]  O:{bar['open']:.2f}  H:{bar['high']:.2f}  "
              f"L:{bar['low']:.2f}  C:{bar['close']:.2f}  V:{bar['volume']:.4f}", end="")

    feed.start_realtime(callback=on_new_bar)

    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down …")
        feed.stop()
        print("Goodbye!")


if __name__ == "__main__":
    main()