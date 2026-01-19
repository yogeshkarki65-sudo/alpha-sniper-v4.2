#!/usr/bin/env python3
"""
Dynamic Filter Engine (DFE) for Alpha Sniper V4.2

Automatically tunes bot filters based on recent trading performance.
Runs once per day at 00:05 UTC to adjust:
- MIN_SCORE
- MIN_24H_QUOTE_VOLUME
- MAX_SPREAD_PCT
- PUMP_MAX_AGE_HOURS

All adjustments are clamped to safe ranges and logged.
"""

import csv
import os
from datetime import datetime, timedelta
from typing import Dict, Optional


class DynamicFilterEngine:
    """Auto-tunes trading filters based on performance metrics"""

    # Safe ranges for each filter
    FILTER_RANGES = {
        'MIN_SCORE': (68, 82),
        'MIN_24H_QUOTE_VOLUME': (8000, 60000),
        'MAX_SPREAD_PCT': (0.7, 2.4),
        'PUMP_MAX_AGE_HOURS': (24, 168)
    }

    # Minimum trades required to run DFE
    MIN_TRADES_REQUIRED = 10

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        self.trade_log = 'logs/v4_trade_scores.csv'

    def update_filters(self, now_utc: Optional[datetime] = None) -> bool:
        """
        Main entry point: update dynamic filters based on recent performance.

        Returns:
            bool: True if filters were updated, False if skipped
        """
        if now_utc is None:
            now_utc = datetime.utcnow()

        self.logger.info("=" * 70)
        self.logger.info("🔧 Dynamic Filter Engine | Starting daily adjustment")
        self.logger.info("=" * 70)

        # 1. Load trade data
        trades = self._load_trade_data()
        if trades is None:
            self.logger.info("DFE | Trade log not found - skipping")
            return False

        if len(trades) < self.MIN_TRADES_REQUIRED:
            self.logger.info(f"DFE | Not enough trades for adjustment (n_trades={len(trades)}) - skipping")
            return False

        # 2. Calculate performance metrics
        metrics = self._calculate_metrics(trades, now_utc)
        self.logger.info("DFE | Performance metrics:")
        self.logger.info(f"  Trades/day (14d): {metrics['trades_per_day_14d']:.2f}")
        self.logger.info(f"  Win rate (last 30): {metrics['win_rate_30']*100:.1f}%")
        self.logger.info(f"  Avg R (last 30): {metrics['avg_R_30']:.3f}R")

        # 3. Load current filter values
        current_filters = self._load_current_filters()
        self.logger.info("DFE | Current filters:")
        for key, val in current_filters.items():
            self.logger.info(f"  {key} = {val}")

        # 4. Calculate new filter values
        new_filters = self._calculate_new_filters(current_filters, metrics)
        self.logger.info("DFE | New filters:")
        for key, val in new_filters.items():
            delta = val - current_filters[key]
            direction = "↑" if delta > 0 else "↓" if delta < 0 else "→"
            self.logger.info(f"  {key} = {val} {direction} ({delta:+.1f})")

        # 5. Write new filters to .env
        if new_filters != current_filters:
            self._update_env_file(new_filters)
            self.logger.info("DFE | ✅ Filters updated successfully")
            return True
        else:
            self.logger.info("DFE | No changes needed")
            return False

    def _load_trade_data(self) -> Optional[list]:
        """Load closed trades from CSV"""
        if not os.path.exists(self.trade_log):
            return None

        try:
            trades = []
            with open(self.trade_log, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    trades.append(row)
            return trades
        except Exception as e:
            self.logger.warning(f"DFE | Error loading trade log: {e}")
            return None

    def _calculate_metrics(self, trades: list, now_utc: datetime) -> Dict[str, float]:
        """Calculate performance metrics from trade data"""

        # Parse timestamps and sort by time (newest first)
        parsed_trades = []
        for trade in trades:
            try:
                # Handle both timestamp formats
                ts_str = trade.get('timestamp_close', trade.get('timestamp', ''))
                if not ts_str:
                    continue

                # Try parsing different formats
                try:
                    ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                except Exception:
                    try:
                        ts = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        continue

                parsed_trades.append({
                    'timestamp': ts,
                    'R': float(trade.get('r_multiple', trade.get('R', 0))),
                    'pnl': float(trade.get('pnl_usd', 0))
                })
            except Exception:
                continue

        if not parsed_trades:
            return {
                'trades_per_day_14d': 0,
                'win_rate_30': 0,
                'avg_R_30': 0
            }

        parsed_trades.sort(key=lambda x: x['timestamp'], reverse=True)

        # 1. Trades per day (last 14 days)
        cutoff_14d = now_utc - timedelta(days=14)
        trades_14d = [t for t in parsed_trades if t['timestamp'] >= cutoff_14d]
        trades_per_day_14d = len(trades_14d) / 14.0

        # 2. Win rate (last 30 trades)
        last_30 = parsed_trades[:30]
        wins = sum(1 for t in last_30 if t['R'] > 0)
        win_rate_30 = wins / len(last_30) if last_30 else 0

        # 3. Avg R (last 30 trades)
        avg_R_30 = sum(t['R'] for t in last_30) / len(last_30) if last_30 else 0

        return {
            'trades_per_day_14d': trades_per_day_14d,
            'win_rate_30': win_rate_30,
            'avg_R_30': avg_R_30
        }

    def _load_current_filters(self) -> Dict[str, float]:
        """Load current filter values from .env"""
        filters = {}

        if not os.path.exists(self.env_file):
            # Use defaults if .env doesn't exist
            return {
                'MIN_SCORE': 75,
                'MIN_24H_QUOTE_VOLUME': 30000,
                'MAX_SPREAD_PCT': 1.5,
                'PUMP_MAX_AGE_HOURS': 72
            }

        try:
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        key = key.strip()
                        if key in self.FILTER_RANGES:
                            try:
                                filters[key] = float(value.strip())
                            except Exception:
                                pass

            # Fill in any missing filters with defaults
            defaults = {
                'MIN_SCORE': 75,
                'MIN_24H_QUOTE_VOLUME': 30000,
                'MAX_SPREAD_PCT': 1.5,
                'PUMP_MAX_AGE_HOURS': 72
            }
            for key, default_val in defaults.items():
                if key not in filters:
                    filters[key] = default_val

        except Exception as e:
            self.logger.warning(f"DFE | Error reading .env: {e}")
            # Return defaults
            filters = {
                'MIN_SCORE': 75,
                'MIN_24H_QUOTE_VOLUME': 30000,
                'MAX_SPREAD_PCT': 1.5,
                'PUMP_MAX_AGE_HOURS': 72
            }

        return filters

    def _calculate_new_filters(self, current: Dict[str, float], metrics: Dict[str, float]) -> Dict[str, float]:
        """
        Calculate new filter values based on performance metrics.

        Rules:
        1. Trade frequency (14d):
           - < 3 trades/day: loosen filters ~10%
           - > 12 trades/day: tighten filters ~8%

        2. Win rate (last 30):
           - < 56%: tighten quality filters ~5%

        3. Avg R (last 30):
           - < 0.6R: tighten volume/spread ~12%
        """
        new = current.copy()

        trades_per_day = metrics['trades_per_day_14d']
        win_rate = metrics['win_rate_30']
        avg_R = metrics['avg_R_30']

        self.logger.info("DFE | Applying adjustment rules:")

        # Rule 1: Trade frequency adjustment
        if trades_per_day < 3:
            self.logger.info(f"  ↓ Too few trades ({trades_per_day:.1f}/day) - loosening filters ~10%")
            new['MIN_SCORE'] *= 0.90
            new['MIN_24H_QUOTE_VOLUME'] *= 0.90
            new['MAX_SPREAD_PCT'] *= 1.10
            new['PUMP_MAX_AGE_HOURS'] *= 1.10
        elif trades_per_day > 12:
            self.logger.info(f"  ↑ Too many trades ({trades_per_day:.1f}/day) - tightening filters ~8%")
            new['MIN_SCORE'] *= 1.08
            new['MIN_24H_QUOTE_VOLUME'] *= 1.08
            new['MAX_SPREAD_PCT'] *= 0.92
            new['PUMP_MAX_AGE_HOURS'] *= 0.92
        else:
            self.logger.info(f"  → Trade frequency OK ({trades_per_day:.1f}/day) - no frequency adjustment")

        # Rule 2: Win rate adjustment
        if win_rate < 0.56:
            self.logger.info(f"  ↑ Low win rate ({win_rate*100:.1f}%) - tightening quality ~5%")
            new['MIN_SCORE'] *= 1.05
            new['MIN_24H_QUOTE_VOLUME'] *= 1.07
            new['MAX_SPREAD_PCT'] *= 0.95

        # Rule 3: Avg R adjustment
        if avg_R < 0.6:
            self.logger.info(f"  ↑ Low avg R ({avg_R:.3f}R) - tightening volume/spread ~12%")
            new['MIN_24H_QUOTE_VOLUME'] *= 1.12
            new['MAX_SPREAD_PCT'] *= 0.88

        # Clamp all values to safe ranges
        for key in new:
            min_val, max_val = self.FILTER_RANGES[key]
            new[key] = max(min_val, min(max_val, new[key]))

            # Round appropriately
            if key == 'MIN_SCORE':
                new[key] = round(new[key])
            elif key == 'MIN_24H_QUOTE_VOLUME':
                new[key] = round(new[key] / 1000) * 1000  # Round to nearest 1000
            elif key == 'PUMP_MAX_AGE_HOURS':
                new[key] = round(new[key])
            else:  # MAX_SPREAD_PCT
                new[key] = round(new[key], 2)

        return new

    def _update_env_file(self, new_filters: Dict[str, float]) -> None:
        """Update .env file with new filter values, preserving all other lines"""

        if not os.path.exists(self.env_file):
            self.logger.warning("DFE | .env file not found - creating new one")
            # Create basic .env with new values
            with open(self.env_file, 'w') as f:
                for key, val in new_filters.items():
                    f.write(f"{key}={val}\n")
            return

        try:
            # Read all lines
            with open(self.env_file, 'r') as f:
                lines = f.readlines()

            # Update lines for our managed filters
            updated_keys = set()
            for i, line in enumerate(lines):
                stripped = line.strip()
                if '=' in stripped and not stripped.startswith('#'):
                    key = stripped.split('=', 1)[0].strip()
                    if key in new_filters:
                        # Format the value appropriately
                        val = new_filters[key]
                        if isinstance(val, int) or val == int(val):
                            lines[i] = f"{key}={int(val)}\n"
                        else:
                            lines[i] = f"{key}={val}\n"
                        updated_keys.add(key)

            # Add any missing filters at the end
            for key, val in new_filters.items():
                if key not in updated_keys:
                    if isinstance(val, int) or val == int(val):
                        lines.append(f"{key}={int(val)}\n")
                    else:
                        lines.append(f"{key}={val}\n")

            # Write back
            with open(self.env_file, 'w') as f:
                f.writelines(lines)

        except Exception as e:
            self.logger.error(f"DFE | Error updating .env file: {e}")
            raise


def update_dynamic_filters(config, logger, now_utc: Optional[datetime] = None) -> bool:
    """
    Convenience function to run the Dynamic Filter Engine.

    Args:
        config: Bot configuration object
        logger: Logger instance
        now_utc: Current UTC time (defaults to now)

    Returns:
        bool: True if filters were updated, False if skipped
    """
    if not getattr(config, 'dfe_enabled', False):
        logger.debug("DFE | Disabled in config - skipping")
        return False

    dfe = DynamicFilterEngine(config, logger)
    return dfe.update_filters(now_utc)
