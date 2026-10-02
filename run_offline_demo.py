#!/usr/bin/env python3
"""
Offline demo – simulates real-time updates using historical data.
Useful when you have no internet or want to test without Binance.
"""

import time
import pandas as pd
from lightweight_charts import Chart
from utils.indicators import add_sma, add_bollinger, prepare_indicator_line


def generate_sample_data(n: int = 300) -> pd.DataFrame:
    """Create synthetic OHLCV data that looks realistic."""
    import numpy as np
    np.random.seed(42)

    dates = pd.date_range(end=pd.Timestamp.utcnow(), periods=n, freq="1min", tz="UTC")
    price = 65000.0
    rows = []

    for t in dates:
        change = np.random.normal(0, 30)
        open_p = price
        close_p = price + change
        high_p = max(open_p, close_p) + abs(np.random.normal(0, 15))
        low_p = min(open_p, close_p) - abs(np.random.normal(0, 15))
        volume = abs(np.random.normal(50, 20))
        rows.append({
            "time": t,
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(close_p, 2),
            "volume": round(volume, 4),
        })
        price = close_p

    return pd.DataFrame(rows)


def main():
    print("Generating sample data …")
    df = generate_sample_data(400)
    df = add_sma(df, 20)
    df = add_bollinger(df, 20)

    # Split into history + “live” part
    hist = df.iloc[:300].copy()
    live = df.iloc[300:].copy()

    chart = Chart(toolbox=True)
    chart.layout(background_color="#131722", text_color="#d1d4dc")
    chart.candle_style(
        up_color="#26a69a", down_color="#ef5350",
        border_up_color="#26a69a", border_down_color="#ef5350",
        wick_up_color="#26a69a", wick_down_color="#ef5350",
    )
    chart.set(hist)

    # SMA line
    sma_line = chart.create_line(name="SMA_20", color="#f0b90b")
    sma_line.set(prepare_indicator_line(hist, "SMA_20"))

    chart.show(block=False)
    print("Simulating real-time updates (press Ctrl+C to stop) …")

    try:
        for _, bar in live.iterrows():
            chart.update(bar)
            # also update the SMA line with the new point
            sma_line.update(pd.Series({"time": bar["time"], "SMA_20": bar["SMA_20"]}))
            time.sleep(0.15)
            print(f"\rClose: {bar['close']:.2f}", end="")
    except KeyboardInterrupt:
        print("\nDemo finished.")


if __name__ == "__main__":
    main()