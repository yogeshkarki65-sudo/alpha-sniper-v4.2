"""
Helper utilities for Alpha Sniper V4.2
"""
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict
import pandas as pd
import numpy as np


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range
    """
    high = df['high']
    low = df['low']
    close = df['close']

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    return atr


def calculate_ema(df: pd.DataFrame, column: str, period: int) -> pd.Series:
    """
    Calculate Exponential Moving Average
    """
    return df[column].ewm(span=period, adjust=False).mean()


def calculate_rsi(df: pd.DataFrame, column: str = 'close', period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index
    """
    delta = df[column].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_rvol(current_volume: float, avg_volume: float) -> float:
    """
    Calculate Relative Volume
    """
    if avg_volume == 0:
        return 0.0
    return current_volume / avg_volume


def calculate_returns(df: pd.DataFrame, periods: int) -> pd.Series:
    """
    Calculate percentage returns over N periods
    """
    return (df['close'] / df['close'].shift(periods) - 1) * 100


def calculate_momentum(df: pd.DataFrame, periods: int) -> float:
    """
    Calculate momentum as % change over N periods
    """
    if len(df) < periods + 1:
        return 0.0
    return ((df['close'].iloc[-1] / df['close'].iloc[-periods-1]) - 1) * 100


def save_json_atomic(filepath: str, data: Any):
    """
    Atomically save JSON data (write to temp, then rename)
    Creates parent directory if it doesn't exist.
    Raises PermissionError if write fails due to permissions.
    """
    # Ensure parent directory exists
    parent_dir = os.path.dirname(filepath)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    # Write to temp file in same directory, then atomic rename
    temp_path = filepath + '.tmp'
    try:
        with open(temp_path, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(temp_path, filepath)
    except PermissionError as e:
        # Clean up temp file if it exists
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except:
            pass
        # Re-raise PermissionError for caller to handle
        raise PermissionError(f"Permission denied writing to {filepath}: {e}") from e


def load_json(filepath: str, default: Any = None) -> Any:
    """
    Load JSON file with default fallback
    Handles FileNotFoundError, JSONDecodeError, and PermissionError gracefully
    """
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return default if default is not None else []
    except json.JSONDecodeError:
        return default if default is not None else []
    except PermissionError:
        # Log warning but don't crash - return default
        return default if default is not None else []


def utc_now() -> datetime:
    """
    Get current UTC time
    """
    return datetime.now(timezone.utc)


def timestamp_to_str(timestamp: float) -> str:
    """
    Convert timestamp to readable string
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def calculate_position_size_from_risk(
    equity: float,
    risk_pct: float,
    entry_price: float,
    stop_loss_price: float
) -> float:
    """
    Calculate position size in USD based on R-based risk
    equity: current account equity
    risk_pct: risk per trade as decimal (e.g., 0.0025 for 0.25%)
    entry_price: entry price
    stop_loss_price: stop loss price

    Returns: position size in USD
    """
    if entry_price <= 0 or stop_loss_price <= 0:
        return 0.0

    risk_amount = equity * risk_pct
    price_risk_pct = abs((entry_price - stop_loss_price) / entry_price)

    if price_risk_pct == 0:
        return 0.0

    position_size = risk_amount / price_risk_pct

    return position_size


def truncate_message(msg: str, max_length: int = 4000) -> str:
    """
    Truncate message to max length (for Telegram)
    """
    if len(msg) <= max_length:
        return msg
    return msg[:max_length-3] + '...'


def ensure_dir(directory: str):
    """
    Ensure directory exists
    """
    os.makedirs(directory, exist_ok=True)


def ohlcv_to_dataframe(ohlcv: list) -> pd.DataFrame:
    """
    Convert CCXT OHLCV format to pandas DataFrame
    ohlcv: list of [timestamp, open, high, low, close, volume]
    """
    if not ohlcv:
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

    return df


def calculate_spread_pct(bid: float, ask: float) -> float:
    """
    Calculate bid-ask spread as percentage
    """
    if bid <= 0:
        return 999.0
    return ((ask - bid) / bid) * 100


def log_trade_to_csv(trade_data: Dict, filepath: str = 'logs/v4_trade_scores.csv'):
    """
    Log a closed trade to CSV file
    Creates file with headers if it doesn't exist
    """
    import csv

    # Ensure logs directory exists
    ensure_dir('logs')

    # Check if file exists to determine if we need to write headers
    file_exists = os.path.isfile(filepath)

    # Define CSV columns
    fieldnames = [
        'timestamp_open',
        'timestamp_close',
        'symbol',
        'side',
        'regime',
        'engine',
        'entry_price',
        'exit_price',
        'size_usd',
        'qty',
        'initial_risk_usd',
        'pnl_usd',
        'pnl_pct',
        'r_multiple',
        'exit_reason',
        'hold_time_hours',
        'score'
    ]

    # Write to CSV
    with open(filepath, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        # Write header if file is new
        if not file_exists:
            writer.writeheader()

        # Write trade data
        writer.writerow({k: trade_data.get(k, '') for k in fieldnames})
