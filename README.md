# Real-time TradingView-style Chart in Python

A complete, ready-to-run Python project that recreates a professional TradingView-like interface using:

- **lightweight-charts** – official-feeling TradingView Lightweight Charts wrapper
- **Binance public API** – free historical + real-time 1-minute candles
- Technical indicators (SMA, EMA, Bollinger Bands, MACD, RSI)
- Dark theme, volume, drawing toolbox, crosshair, legend

---

## Features

- Candlestick chart with volume histogram
- Real-time WebSocket updates (updates the forming candle every second)
- Overlay indicators: SMA(20/50), EMA(12/26), Bollinger Bands
- Drawing tools (trend lines, horizontal lines, rectangles …)
- Dark TradingView-inspired theme
- Easy configuration at the top of `main.py`

---

## Project Structure

```
tradingview_realtime_python/
├── main.py                 # Desktop version (native window)
├── run_offline_demo.py     # Offline simulation
├── requirements.txt
├── README.md
├── utils/
│   ├── data_feed.py        # Binance historical + WebSocket feed
│   └── indicators.py       # SMA, EMA, RSI, Bollinger, MACD
├── web_app/                # ★ Dash web version
│   ├── app.py
│   ├── requirements_web.txt
│   └── README.md
└── data/                   # (optional) place CSV files here
```

---

## Installation

```bash
# 1. Create & activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate          # Linux / macOS
# venv\Scripts\activate           # Windows

# 2. Install dependencies
pip install -r requirements.txt
```

---

## How to Run

### Desktop version (native window)

```bash
python main.py
```

A chart window will open. Real-time updates from Binance start automatically.  
Press **Ctrl+C** in the terminal to stop.

### Web version (Dash – runs in the browser)

```bash
cd web_app
pip install -r requirements_web.txt
python app.py
```

Then open **http://127.0.0.1:8050** in your browser.  
You get a full web UI with symbol/timeframe selectors and live updates every 2 seconds.

---

## Configuration

Open `main.py` and edit the block at the top:

```python
SYMBOL = "BTC/USDT"      # any Binance spot pair
TIMEFRAME = "1m"         # 1m, 5m, 15m, 1h, 4h, 1d
HISTORY_LIMIT = 500
SHOW_VOLUME = True
SHOW_SMA = True
SHOW_EMA = True
SHOW_BOLLINGER = True
DARK_THEME = True
```

---

## Adding Your Own Indicators

1. Write a function in `utils/indicators.py` that adds columns to the DataFrame.
2. Call it in `main.py` after fetching history.
3. Create a line series with `chart.create_line(...)` and `.set()`.

Example:

```python
df = add_rsi(df, period=14)
rsi_line = chart.create_line(name="RSI_14", color="#ff9800")
rsi_line.set(prepare_indicator_line(df, "RSI_14"))
```

---

## Switching Data Sources

The `BinanceDataFeed` class is self-contained.  
To use another exchange or a paid provider:

1. Keep the same public methods:
   - `fetch_historical(limit) → DataFrame`
   - `start_realtime(callback)`
2. Replace the internals of `utils/data_feed.py`.

Popular alternatives: Polygon.io, Twelve Data, Interactive Brokers, CCXT unified WebSocket, etc.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Chart window does not appear | Make sure you are not running inside a pure headless environment. On remote servers use X11 forwarding or a VNC. |
| WebSocket disconnects | Binance public streams are free but can drop. The feed will print an error; restart the script. |
| “ModuleNotFoundError” | Activate the virtualenv and run `pip install -r requirements.txt` again. |
| Slow updates | 1-minute candles update every few seconds while the candle is forming. Switch to a lower latency tick feed if needed. |

---

## Next Steps / Ideas

- Multi-pane layout (price + RSI + MACD)
- Order book / depth of market
- Alert system when price crosses SMA
- Save / load drawings
- Multi-symbol watchlist
- Deploy as a web app with Dash + `dash-tvlwc`

---

## License

This project is provided as educational sample code.  
TradingView Lightweight Charts is licensed under Apache 2.0.  
Use at your own risk – not financial advice.
