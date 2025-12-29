"""
Indicator Precompute Module for Alpha Sniper v4.2

Computes technical indicators ONCE per (symbol, timeframe) and caches results.
Engines read from this shared cache to avoid duplicate computation.

Pure functions - no side effects, no I/O.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def compute_indicators(df: pd.DataFrame, symbol: str = "UNKNOWN") -> Dict[str, Any]:
    """
    Compute all technical indicators for a given OHLCV dataframe.

    This is the single source of truth for indicator computation.
    Called once per (symbol, timeframe) after OHLCV fetch.

    Args:
        df: OHLCV dataframe with columns: timestamp, open, high, low, close, volume
        symbol: Symbol name (for logging)

    Returns:
        Dict with all computed indicators and derived metrics
    """
    try:
        if df is None or len(df) == 0:
            logger.warning(f"[{symbol}] Empty dataframe, returning empty indicators")
            return {}

        indicators = {}

        # Basic price metrics
        indicators["current_price"] = float(df["close"].iloc[-1])
        indicators["price_24h_ago"] = float(df["close"].iloc[-24] if len(df) >= 24 else df["close"].iloc[0])
        indicators["high_24h"] = float(df["high"].tail(24).max() if len(df) >= 24 else df["high"].max())
        indicators["low_24h"] = float(df["low"].tail(24).min() if len(df) >= 24 else df["low"].min())

        # Returns
        if len(df) >= 2:
            indicators["return_1h"] = float((df["close"].iloc[-1] / df["close"].iloc[-2] - 1) * 100)
        if len(df) >= 24:
            indicators["return_24h"] = float((df["close"].iloc[-1] / df["close"].iloc[-24] - 1) * 100)

        # Volume metrics
        indicators["volume_current"] = float(df["volume"].iloc[-1])
        indicators["volume_24h"] = float(df["volume"].tail(24).sum() if len(df) >= 24 else df["volume"].sum())
        indicators["volume_mean_24h"] = float(df["volume"].tail(24).mean() if len(df) >= 24 else df["volume"].mean())

        # Relative volume (rvol)
        if indicators["volume_mean_24h"] > 0:
            indicators["rvol"] = indicators["volume_current"] / indicators["volume_mean_24h"]
        else:
            indicators["rvol"] = 0.0

        # Moving averages
        if len(df) >= 20:
            indicators["ema_20"] = float(df["close"].ewm(span=20, adjust=False).mean().iloc[-1])
            indicators["ema_50"] = float(df["close"].ewm(span=50, adjust=False).mean().iloc[-1]) if len(df) >= 50 else indicators["ema_20"]
            indicators["ema_200"] = float(df["close"].ewm(span=200, adjust=False).mean().iloc[-1]) if len(df) >= 200 else indicators["ema_50"]
        else:
            indicators["ema_20"] = indicators["current_price"]
            indicators["ema_50"] = indicators["current_price"]
            indicators["ema_200"] = indicators["current_price"]

        # RSI (14-period)
        indicators["rsi_14"] = compute_rsi(df["close"], period=14)

        # ATR (14-period)
        indicators["atr_14"] = compute_atr(df, period=14)

        # Momentum
        if len(df) >= 15:
            close_15_ago = df["close"].iloc[-15]
            indicators["momentum_1h"] = float((indicators["current_price"] / close_15_ago - 1) * 100) if close_15_ago > 0 else 0.0
        else:
            indicators["momentum_1h"] = 0.0

        # Bollinger Bands
        if len(df) >= 20:
            bb = compute_bollinger_bands(df["close"], period=20, std_dev=2.0)
            indicators["bb_upper"] = bb["upper"]
            indicators["bb_middle"] = bb["middle"]
            indicators["bb_lower"] = bb["lower"]
            indicators["bb_width"] = bb["width"]
        else:
            indicators["bb_upper"] = indicators["current_price"]
            indicators["bb_middle"] = indicators["current_price"]
            indicators["bb_lower"] = indicators["current_price"]
            indicators["bb_width"] = 0.0

        # MACD
        if len(df) >= 26:
            macd = compute_macd(df["close"])
            indicators["macd"] = macd["macd"]
            indicators["macd_signal"] = macd["signal"]
            indicators["macd_hist"] = macd["histogram"]
        else:
            indicators["macd"] = 0.0
            indicators["macd_signal"] = 0.0
            indicators["macd_hist"] = 0.0

        # Stochastic
        if len(df) >= 14:
            stoch = compute_stochastic(df, k_period=14, d_period=3)
            indicators["stoch_k"] = stoch["k"]
            indicators["stoch_d"] = stoch["d"]
        else:
            indicators["stoch_k"] = 50.0
            indicators["stoch_d"] = 50.0

        logger.debug(f"[{symbol}] Indicators computed: {len(indicators)} metrics")
        return indicators

    except Exception as e:
        logger.error(f"[{symbol}] Error computing indicators: {e}")
        return {}


def compute_rsi(close: pd.Series, period: int = 14) -> float:
    """
    Compute RSI (Relative Strength Index).

    Args:
        close: Close price series
        period: RSI period

    Returns:
        RSI value (0-100)
    """
    if len(close) < period + 1:
        return 50.0  # Neutral default

    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0


def compute_atr(df: pd.DataFrame, period: int = 14) -> float:
    """
    Compute ATR (Average True Range).

    Args:
        df: OHLCV dataframe
        period: ATR period

    Returns:
        ATR value
    """
    if len(df) < period + 1:
        return 0.0

    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    return float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0


def compute_bollinger_bands(
    close: pd.Series, period: int = 20, std_dev: float = 2.0
) -> Dict[str, float]:
    """
    Compute Bollinger Bands.

    Args:
        close: Close price series
        period: Moving average period
        std_dev: Standard deviation multiplier

    Returns:
        Dict with upper, middle, lower, width
    """
    if len(close) < period:
        current = float(close.iloc[-1])
        return {
            "upper": current,
            "middle": current,
            "lower": current,
            "width": 0.0,
        }

    middle = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)

    return {
        "upper": float(upper.iloc[-1]) if not pd.isna(upper.iloc[-1]) else float(close.iloc[-1]),
        "middle": float(middle.iloc[-1]) if not pd.isna(middle.iloc[-1]) else float(close.iloc[-1]),
        "lower": float(lower.iloc[-1]) if not pd.isna(lower.iloc[-1]) else float(close.iloc[-1]),
        "width": float((upper.iloc[-1] - lower.iloc[-1]) / middle.iloc[-1] * 100) if middle.iloc[-1] > 0 else 0.0,
    }


def compute_macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> Dict[str, float]:
    """
    Compute MACD (Moving Average Convergence Divergence).

    Args:
        close: Close price series
        fast: Fast EMA period
        slow: Slow EMA period
        signal: Signal line period

    Returns:
        Dict with macd, signal, histogram
    """
    if len(close) < slow:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}

    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    return {
        "macd": float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else 0.0,
        "signal": float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else 0.0,
        "histogram": float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else 0.0,
    }


def compute_stochastic(
    df: pd.DataFrame, k_period: int = 14, d_period: int = 3
) -> Dict[str, float]:
    """
    Compute Stochastic Oscillator.

    Args:
        df: OHLCV dataframe
        k_period: %K period
        d_period: %D period (moving average of %K)

    Returns:
        Dict with k and d values (0-100)
    """
    if len(df) < k_period:
        return {"k": 50.0, "d": 50.0}

    low_min = df["low"].rolling(window=k_period).min()
    high_max = df["high"].rolling(window=k_period).max()

    k = 100 * (df["close"] - low_min) / (high_max - low_min)
    d = k.rolling(window=d_period).mean()

    return {
        "k": float(k.iloc[-1]) if not pd.isna(k.iloc[-1]) else 50.0,
        "d": float(d.iloc[-1]) if not pd.isna(d.iloc[-1]) else 50.0,
    }
