"""
Data feed module – historical + real-time OHLCV via ccxt.
Uses Bybit by default (works from Render / restricted locations).
Binance is blocked from many cloud providers (error 451).
"""

import time
import json
import threading
from typing import Callable, Optional, List, Dict, Any
from datetime import datetime, timezone

import pandas as pd
import ccxt
from websocket import WebSocketApp


class BinanceDataFeed:
    """
    Data feed for major spot markets (Bybit by default).
    - fetch_historical(): returns pandas DataFrame ready for lightweight-charts
    - start_realtime(): optional WebSocket (mainly for desktop version)
    """

    def __init__(self, symbol: str = "BTC/USDT", timeframe: str = "1m", exchange_id: str = "bybit"):
        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange_id = exchange_id

        # Bybit works from Render. Binance is geo-blocked on most cloud IPs.
        if exchange_id == "bybit":
            self.exchange = ccxt.bybit({
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
            })
        elif exchange_id == "okx":
            self.exchange = ccxt.okx({"enableRateLimit": True})
        else:
            self.exchange = ccxt.binance({"enableRateLimit": True})

        self._ws: Optional[WebSocketApp] = None
        self._running = False
        self._callback: Optional[Callable] = None

        # Stream symbol (used only for Binance-style websocket)
        self.stream_symbol = symbol.replace("/", "").lower()  # btcusdt

    def fetch_historical(self, limit: int = 500) -> pd.DataFrame:
        """
        Fetch historical OHLCV candles.
        Returns DataFrame with columns: time, open, high, low, close, volume
        """
        ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe=self.timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["time"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df[["time", "open", "high", "low", "close", "volume"]]
        return df

    def _on_message(self, ws, message: str):
        """Parse kline WebSocket message (Binance format – used by desktop only)."""
        try:
            data = json.loads(message)
            k = data.get("k")
            if not k:
                return

            bar = {
                "time": datetime.fromtimestamp(k["t"] / 1000, tz=timezone.utc),
                "open": float(k["o"]),
                "high": float(k["h"]),
                "low": float(k["l"]),
                "close": float(k["c"]),
                "volume": float(k["v"]),
            }

            if self._callback:
                self._callback(bar)

        except Exception as e:
            print(f"[DataFeed] Error parsing message: {e}")

    def _on_error(self, ws, error):
        print(f"[DataFeed] WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        print("[DataFeed] WebSocket closed")
        self._running = False

    def _on_open(self, ws):
        print(f"[DataFeed] WebSocket connected – streaming {self.stream_symbol}@{self.timeframe}")

    def start_realtime(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Start a background WebSocket (mainly for the desktop version).
        The web version uses polling via dcc.Interval instead.
        """
        if self._running:
            print("[DataFeed] Already running")
            return

        self._callback = callback
        self._running = True

        # Only Binance has this simple public kline stream used by the desktop demo.
        # For Bybit the web app relies on REST polling (more reliable on Render).
        interval = self.timeframe
        url = f"wss://stream.binance.com:9443/ws/{self.stream_symbol}@kline_{interval}"

        self._ws = WebSocketApp(
            url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open,
        )

        t = threading.Thread(target=self._ws.run_forever, daemon=True)
        t.start()
        print("[DataFeed] Real-time stream started in background thread")

    def stop(self):
        """Gracefully stop the WebSocket."""
        self._running = False
        if self._ws:
            self._ws.close()
            print("[DataFeed] Stream stopped")
