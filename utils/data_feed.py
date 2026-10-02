"""
Data feed module – tries multiple exchanges until one works.
Many exchanges block cloud IPs (Render, Railway, etc.).
Order: OKX → KuCoin → Gate → Bybit → Binance
"""

from typing import Callable, Optional, Dict, Any, List
from datetime import datetime, timezone
import pandas as pd
import ccxt


# Exchanges to try (in order). First one that succeeds is used.
EXCHANGE_CANDIDATES = [
    ("okx",     {"enableRateLimit": True}),
    ("kucoin",  {"enableRateLimit": True}),
    ("gate",    {"enableRateLimit": True}),
    ("bybit",   {"enableRateLimit": True, "options": {"defaultType": "spot"}}),
    ("binance", {"enableRateLimit": True}),
]


def _create_exchange(exchange_id: str, config: dict):
    return getattr(ccxt, exchange_id)(config)


class BinanceDataFeed:
    """
    Data feed that automatically picks a working exchange.
    - fetch_historical() returns a DataFrame ready for lightweight-charts
    """

    def __init__(self, symbol: str = "BTC/USDT", timeframe: str = "1m"):
        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange = None
        self.exchange_id = None
        self._working = False

        self._find_working_exchange()

    def _find_working_exchange(self):
        """Try each candidate until one can fetch a candle."""
        for exchange_id, config in EXCHANGE_CANDIDATES:
            try:
                ex = _create_exchange(exchange_id, config)
                # Quick test – fetch just 1 candle
                test = ex.fetch_ohlcv(self.symbol, timeframe=self.timeframe, limit=1)
                if test and len(test) > 0:
                    self.exchange = ex
                    self.exchange_id = exchange_id
                    self._working = True
                    print(f"[DataFeed] Using {exchange_id.upper()} for {self.symbol}")
                    return
            except Exception as e:
                print(f"[DataFeed] {exchange_id} failed: {str(e)[:80]}")
                continue

        print("[DataFeed] WARNING: No exchange worked – charts will be empty")
        # Fallback so the app doesn't crash
        self.exchange = ccxt.okx({"enableRateLimit": True})
        self.exchange_id = "okx"
        self._working = False

    def fetch_historical(self, limit: int = 500) -> pd.DataFrame:
        """
        Fetch historical OHLCV candles.
        Returns DataFrame with columns: time, open, high, low, close, volume
        """
        if not self.exchange:
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

        try:
            ohlcv = self.exchange.fetch_ohlcv(
                self.symbol, timeframe=self.timeframe, limit=limit
            )
            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["time"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            df = df[["time", "open", "high", "low", "close", "volume"]]
            return df
        except Exception as e:
            print(f"[DataFeed] fetch_historical error: {e}")
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

    # --- stubs so desktop version doesn't break ---
    def start_realtime(self, callback: Callable):
        print("[DataFeed] Real-time WebSocket not used in web version (polling instead)")

    def stop(self):
        pass
