"""
Technical indicators for the TradingView-style chart.
Uses the 'ta' library + pure pandas implementations.
"""

import pandas as pd
import numpy as np


def add_sma(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.DataFrame:
    """Simple Moving Average."""
    df = df.copy()
    df[f"SMA_{period}"] = df[column].rolling(window=period, min_periods=1).mean()
    return df


def add_ema(df: pd.DataFrame, period: int = 20, column: str = "close") -> pd.DataFrame:
    """Exponential Moving Average."""
    df = df.copy()
    df[f"EMA_{period}"] = df[column].ewm(span=period, adjust=False).mean()
    return df


def add_rsi(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.DataFrame:
    """Relative Strength Index."""
    df = df.copy()
    delta = df[column].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df[f"RSI_{period}"] = 100 - (100 / (1 + rs))
    return df


def add_bollinger(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0, column: str = "close") -> pd.DataFrame:
    """Bollinger Bands."""
    df = df.copy()
    sma = df[column].rolling(window=period, min_periods=1).mean()
    std = df[column].rolling(window=period, min_periods=1).std()
    df[f"BB_MID_{period}"] = sma
    df[f"BB_UPPER_{period}"] = sma + (std * std_dev)
    df[f"BB_LOWER_{period}"] = sma - (std * std_dev)
    return df


def add_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, column: str = "close") -> pd.DataFrame:
    """MACD (Moving Average Convergence Divergence)."""
    df = df.copy()
    ema_fast = df[column].ewm(span=fast, adjust=False).mean()
    ema_slow = df[column].ewm(span=slow, adjust=False).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=signal, adjust=False).mean()
    df["MACD_HIST"] = df["MACD"] - df["MACD_SIGNAL"]
    return df


def prepare_indicator_line(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """
    Prepare a DataFrame suitable for lightweight-charts line series.
    Expected columns: time + value column.
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame")
    result = df[["time", column]].dropna().copy()
    result.columns = ["time", column]
    return result