"""
Data loader for backtesting

Loads historical OHLCV data from CSV files and provides
data in the same format as the live exchange adapter.
"""
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone


class BacktestDataLoader:
    """
    Loads historical market data from CSV files

    Expected CSV format:
    timestamp,open,high,low,close,volume
    1609459200000,0.5,0.51,0.49,0.50,1000000
    """

    def __init__(self, data_dir: str):
        """
        Args:
            data_dir: Directory containing CSV files (e.g., data/)
        """
        self.data_dir = Path(data_dir)
        self.loaded_data = {}  # {symbol: {timeframe: df}}

    def load_symbol(
        self,
        symbol: str,
        timeframes: List[str] = ['1m', '15m', '1h']
    ) -> bool:
        """
        Load all timeframes for a symbol

        Expected filenames:
        - BTCUSDT_1m.csv
        - BTCUSDT_15m.csv
        - BTCUSDT_1h.csv

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframes: List of timeframes to load

        Returns:
            True if at least one timeframe loaded successfully
        """
        # Normalize symbol: BTC/USDT -> BTCUSDT
        symbol_clean = symbol.replace('/', '')

        if symbol not in self.loaded_data:
            self.loaded_data[symbol] = {}

        success = False

        for tf in timeframes:
            filename = f"{symbol_clean}_{tf}.csv"
            filepath = self.data_dir / filename

            if not filepath.exists():
                continue

            try:
                df = pd.read_csv(filepath)

                # Validate columns
                required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                if not all(col in df.columns for col in required_cols):
                    print(f"⚠️ {filename}: Missing required columns")
                    continue

                # Convert timestamp to datetime index
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
                df.set_index('timestamp', inplace=True)

                # Ensure numeric types
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

                # Drop NaN rows
                df.dropna(inplace=True)

                # Sort by timestamp
                df.sort_index(inplace=True)

                self.loaded_data[symbol][tf] = df
                success = True

            except Exception as e:
                print(f"⚠️ Failed to load {filename}: {e}")
                continue

        return success

    def load_symbols(self, symbols: List[str]) -> int:
        """
        Load data for multiple symbols

        Returns:
            Number of symbols successfully loaded
        """
        loaded_count = 0
        for symbol in symbols:
            if self.load_symbol(symbol):
                loaded_count += 1
        return loaded_count

    def get_symbols(self) -> List[str]:
        """Get list of loaded symbols"""
        return list(self.loaded_data.keys())

    def get_data_at_time(
        self,
        symbol: str,
        timestamp: pd.Timestamp,
        timeframe: str,
        lookback: int = 100
    ) -> Optional[pd.DataFrame]:
        """
        Get historical data up to a specific timestamp

        Args:
            symbol: Trading pair
            timestamp: Current timestamp in backtest
            timeframe: Timeframe (1m, 15m, 1h)
            lookback: Number of candles to return

        Returns:
            DataFrame with historical candles up to (but not including) timestamp
        """
        if symbol not in self.loaded_data:
            return None

        if timeframe not in self.loaded_data[symbol]:
            return None

        df = self.loaded_data[symbol][timeframe]

        # Get data up to current timestamp (exclusive)
        historical = df[df.index < timestamp]

        if len(historical) < 1:
            return None

        # Return last N candles
        return historical.tail(lookback).copy()

    def get_latest_price(self, symbol: str, timestamp: pd.Timestamp) -> Optional[float]:
        """
        Get latest close price at a given timestamp

        Uses 1m data for most accurate price
        """
        if symbol not in self.loaded_data or '1m' not in self.loaded_data[symbol]:
            return None

        df = self.loaded_data[symbol]['1m']
        historical = df[df.index < timestamp]

        if len(historical) < 1:
            return None

        return float(historical.iloc[-1]['close'])

    def get_timerange(self, symbol: str, timeframe: str = '1h') -> tuple:
        """
        Get min/max timestamps for a symbol

        Returns:
            (start_time, end_time) as pd.Timestamp
        """
        if symbol not in self.loaded_data or timeframe not in self.loaded_data[symbol]:
            return (None, None)

        df = self.loaded_data[symbol][timeframe]
        return (df.index.min(), df.index.max())

    def calculate_24h_metrics(
        self,
        symbol: str,
        timestamp: pd.Timestamp
    ) -> Dict:
        """
        Calculate 24h volume and price change at a given timestamp

        Returns:
            {
                'quoteVolume': 24h volume in USDT,
                'percentageChange': 24h price change %,
                'last': current price
            }
        """
        if symbol not in self.loaded_data or '1h' not in self.loaded_data[symbol]:
            return {'quoteVolume': 0, 'percentageChange': 0, 'last': 0}

        df_1h = self.loaded_data[symbol]['1h']
        historical = df_1h[df_1h.index < timestamp]

        if len(historical) < 24:
            return {'quoteVolume': 0, 'percentageChange': 0, 'last': 0}

        # Get last 24 hours of data
        last_24h = historical.tail(24)

        # Calculate 24h quote volume (volume * close as approximation)
        quote_volume = (last_24h['volume'] * last_24h['close']).sum()

        # Calculate 24h price change
        price_24h_ago = last_24h.iloc[0]['close']
        current_price = last_24h.iloc[-1]['close']
        pct_change = ((current_price / price_24h_ago) - 1) * 100 if price_24h_ago > 0 else 0

        return {
            'quoteVolume': float(quote_volume),
            'percentageChange': float(pct_change),
            'last': float(current_price),
            'close': float(current_price),
            'bid': float(current_price * 0.9995),  # Approximate bid/ask
            'ask': float(current_price * 1.0005)
        }
