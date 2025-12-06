"""
Backtest engine

Orchestrates the backtesting process by:
1. Loading historical data
2. Reusing PumpEngine for signal generation
3. Simulating position management
4. Calculating performance metrics
"""
import sys
from pathlib import Path
from typing import Dict, List
import pandas as pd
from datetime import datetime, timezone, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.data_loader import BacktestDataLoader
from backtest.portfolio import BacktestPortfolio
from signals.pump_engine import PumpEngine
from utils import helpers


class SimpleLogger:
    """Simple logger for backtest"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def info(self, msg: str):
        if self.verbose:
            print(f"[INFO] {msg}")

    def debug(self, msg: str):
        pass  # Suppress debug in backtest

    def warning(self, msg: str):
        print(f"[WARN] {msg}")

    def error(self, msg: str):
        print(f"[ERROR] {msg}")


class BacktestConfig:
    """
    Config object for backtesting

    Mirrors the structure of the live Config class but with
    backtesting-specific values
    """

    def __init__(self, **kwargs):
        # Core settings
        self.sim_mode = False  # Treat as LIVE mode for strategy logic
        self.pump_only_mode = kwargs.get('pump_only_mode', True)
        self.starting_equity = kwargs.get('starting_equity', 100.0)

        # Pump engine settings
        self.pump_engine_enabled = True
        self.pump_risk_per_trade = kwargs.get('pump_risk_per_trade', 0.004)
        self.pump_max_concurrent = kwargs.get('pump_max_concurrent', 1)
        self.pump_min_24h_return = kwargs.get('pump_min_24h_return', 0.20)
        self.pump_max_24h_return = kwargs.get('pump_max_24h_return', 5.00)
        self.pump_min_rvol = kwargs.get('pump_min_rvol', 1.5)
        self.pump_min_24h_quote_volume = kwargs.get('pump_min_24h_quote_volume', 500000)
        self.pump_min_momentum_1h = kwargs.get('pump_min_momentum_1h', 20)
        self.pump_min_score = kwargs.get('pump_min_score', 72)
        self.pump_max_hold_hours = kwargs.get('pump_max_hold_hours', 2)

        # Aggressive pump mode
        self.pump_aggressive_mode = kwargs.get('pump_aggressive_mode', False)
        self.pump_aggressive_min_rvol = kwargs.get('pump_aggressive_min_rvol', 1.8)
        self.pump_aggressive_min_24h_return = kwargs.get('pump_aggressive_min_24h_return', 0.30)
        self.pump_aggressive_max_24h_return = kwargs.get('pump_aggressive_max_24h_return', 5.00)
        self.pump_aggressive_min_24h_quote_volume = kwargs.get('pump_aggressive_min_24h_quote_volume', 500000)
        self.pump_aggressive_momentum_rsi_5m = kwargs.get('pump_aggressive_momentum_rsi_5m', 55)
        self.pump_aggressive_price_above_ema1m = kwargs.get('pump_aggressive_price_above_ema1m', True)
        self.pump_aggressive_max_hold_minutes = kwargs.get('pump_aggressive_max_hold_minutes', 90)

        # Risk management
        self.max_portfolio_heat = kwargs.get('max_portfolio_heat', 0.008)
        self.max_concurrent_positions = kwargs.get('max_concurrent_positions', 2)
        self.max_spread_pct = kwargs.get('max_spread_pct', 0.5)
        self.enable_daily_loss_limit = kwargs.get('enable_daily_loss_limit', True)
        self.max_daily_loss_pct = kwargs.get('max_daily_loss_pct', 0.02)

        # Stop management
        self.min_stop_pct_pump = kwargs.get('min_stop_pct_pump', 0.02)
        self.enable_trailing_stop = kwargs.get('enable_trailing_stop', True)
        self.trailing_stop_pct = kwargs.get('trailing_stop_pct', 0.35)

        # Global filters
        self.min_24h_quote_volume = kwargs.get('min_24h_quote_volume', 100000)

        # Liquidity (not used in backtest, but needed for compatibility)
        self.liquidity_sizing_enabled = False
        self.correlation_limit_enabled = False


class PumpBacktester:
    """
    Main backtesting engine for PUMP-ONLY strategy

    Reuses exact PumpEngine logic from live trading
    """

    def __init__(
        self,
        data_dir: str,
        config: BacktestConfig,
        verbose: bool = True
    ):
        """
        Args:
            data_dir: Directory containing CSV files
            config: BacktestConfig with strategy parameters
            verbose: Print detailed logs
        """
        self.data_loader = BacktestDataLoader(data_dir)
        self.config = config
        self.logger = SimpleLogger(verbose)

        # Initialize strategy components
        self.pump_engine = PumpEngine(self.config, self.logger)
        self.portfolio = BacktestPortfolio(self.config, self.logger)

    def load_data(self, symbols: List[str]) -> int:
        """
        Load historical data for symbols

        Returns:
            Number of symbols successfully loaded
        """
        self.logger.info(f"Loading data for {len(symbols)} symbols...")
        loaded = self.data_loader.load_symbols(symbols)
        self.logger.info(f"✅ Loaded data for {loaded}/{len(symbols)} symbols")
        return loaded

    def build_market_data(
        self,
        timestamp: pd.Timestamp
    ) -> Dict:
        """
        Build market_data dict in same format as live Scanner

        Returns:
            {symbol: {ticker, df_15m, df_1h, spread_pct, volume_24h}}
        """
        market_data = {}

        for symbol in self.data_loader.get_symbols():
            # Get historical candles up to current timestamp
            df_15m = self.data_loader.get_data_at_time(symbol, timestamp, '15m', lookback=100)
            df_1h = self.data_loader.get_data_at_time(symbol, timestamp, '1h', lookback=100)

            if df_15m is None or df_1h is None:
                continue

            if len(df_15m) < 20 or len(df_1h) < 20:
                continue

            # Get 24h metrics
            ticker = self.data_loader.calculate_24h_metrics(symbol, timestamp)

            if ticker['quoteVolume'] < self.config.min_24h_quote_volume:
                continue

            # Calculate spread (approximate)
            current_price = df_15m.iloc[-1]['close']
            spread_pct = helpers.calculate_spread_pct(
                current_price * 0.9995,
                current_price * 1.0005
            )

            market_data[symbol] = {
                'ticker': ticker,
                'df_15m': df_15m,
                'df_1h': df_1h,
                'spread_pct': spread_pct,
                'volume_24h': ticker['quoteVolume']
            }

        return market_data

    def run(
        self,
        start_time: str,
        end_time: str,
        scan_interval_minutes: int = 30
    ) -> Dict:
        """
        Run backtest

        Args:
            start_time: Start timestamp (ISO format or 'YYYY-MM-DD')
            end_time: End timestamp (ISO format or 'YYYY-MM-DD')
            scan_interval_minutes: How often to scan for signals (default: 30 min)

        Returns:
            Statistics dictionary
        """
        # Parse timestamps
        start_ts = pd.to_datetime(start_time, utc=True)
        end_ts = pd.to_datetime(end_time, utc=True)

        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("🔬 PUMP BACKTEST START")
        self.logger.info("=" * 70)
        self.logger.info(f"Start: {start_ts}")
        self.logger.info(f"End: {end_ts}")
        self.logger.info(f"Starting Equity: ${self.config.starting_equity:.2f}")
        self.logger.info(f"Scan Interval: {scan_interval_minutes} minutes")
        self.logger.info(f"Symbols: {len(self.data_loader.get_symbols())}")
        self.logger.info("=" * 70)
        self.logger.info("")

        # Main backtest loop
        current_time = start_ts
        scan_delta = timedelta(minutes=scan_interval_minutes)
        scan_count = 0

        while current_time <= end_ts:
            # Check daily reset
            self.portfolio.check_daily_reset(current_time)

            # Update open positions (check every scan)
            prices = {}
            for symbol in self.data_loader.get_symbols():
                price = self.data_loader.get_latest_price(symbol, current_time)
                if price:
                    prices[symbol] = price

            self.portfolio.update_positions(current_time, prices)

            # Scan for new signals (at scan_interval)
            market_data = self.build_market_data(current_time)

            if market_data:
                # Generate pump signals using EXACT same logic as LIVE
                signals = self.pump_engine.generate_signals(market_data, regime='BULL')

                if signals:
                    # Sort by score
                    signals.sort(key=lambda s: s.get('score', 0), reverse=True)

                    # Try to open positions for top signals
                    for signal in signals:
                        # Get current price for entry
                        entry_price = signal['entry_price']

                        # Attempt to open position
                        position = self.portfolio.open_position(
                            signal,
                            current_time,
                            entry_price
                        )

                        if position:
                            # Only take one signal per scan (aggressive mode)
                            break

            # Advance time
            current_time += scan_delta
            scan_count += 1

            # Progress logging
            if scan_count % 100 == 0:
                progress = (current_time - start_ts) / (end_ts - start_ts) * 100
                self.logger.info(
                    f"📊 Progress: {progress:.1f}% | "
                    f"Equity: ${self.portfolio.current_equity:.2f} | "
                    f"Open: {len(self.portfolio.open_positions)} | "
                    f"Closed: {len(self.portfolio.closed_positions)}"
                )

        # Close any remaining positions at end time
        self.logger.info("")
        self.logger.info("Closing remaining positions...")
        for pos in self.portfolio.open_positions[:]:
            exit_price = self.data_loader.get_latest_price(pos.symbol, end_ts)
            if exit_price:
                self.portfolio.close_position(pos, end_ts, exit_price, 'Backtest end')

        # Calculate final stats
        stats = self.portfolio.get_stats()

        self.logger.info("")
        self.logger.info("=" * 70)
        self.logger.info("🎯 BACKTEST RESULTS")
        self.logger.info("=" * 70)
        self.logger.info(f"Total Trades: {stats['total_trades']}")
        self.logger.info(f"Wins / Losses: {stats['wins']}W / {stats['losses']}L")
        self.logger.info(f"Win Rate: {stats['win_rate']:.1f}%")
        self.logger.info(f"Average R: {stats['avg_r']:.2f}R")
        self.logger.info(f"Avg Win: ${stats['avg_win_usd']:.2f}")
        self.logger.info(f"Avg Loss: ${stats['avg_loss_usd']:.2f}")
        self.logger.info(f"Best Trade: {stats['best_trade_symbol']} ${stats['best_trade_usd']:.2f}")
        self.logger.info(f"Worst Trade: {stats['worst_trade_symbol']} ${stats['worst_trade_usd']:.2f}")
        self.logger.info(f"")
        self.logger.info(f"Starting Equity: ${stats['starting_equity']:.2f}")
        self.logger.info(f"Final Equity: ${stats['final_equity']:.2f}")
        self.logger.info(f"Total P&L: ${stats['total_pnl_usd']:+.2f} ({stats['total_pnl_pct']:+.2f}%)")
        self.logger.info(f"Total Fees: ${stats['total_fees']:.2f}")
        self.logger.info(f"Max Drawdown: {stats['max_drawdown_pct']:.2f}%")
        self.logger.info("=" * 70)
        self.logger.info("")

        # Calculate trades per month
        duration_days = (end_ts - start_ts).days
        trades_per_month = (stats['total_trades'] / duration_days * 30) if duration_days > 0 else 0
        self.logger.info(f"📈 Trades per Month: {trades_per_month:.1f}")

        return stats

    def save_trade_log(self, filepath: str):
        """
        Save detailed trade log to CSV

        Args:
            filepath: Output CSV path (e.g., 'backtest_trades.csv')
        """
        if not self.portfolio.closed_positions:
            self.logger.warning("No trades to save")
            return

        trades = [pos.to_dict() for pos in self.portfolio.closed_positions]
        df = pd.DataFrame(trades)

        # Reorder columns
        columns = [
            'timestamp_open', 'timestamp_close', 'symbol', 'side',
            'entry_price', 'exit_price', 'stop_loss', 'size_usd',
            'pnl_usd', 'pnl_pct', 'r_multiple', 'hold_minutes',
            'exit_reason', 'score', 'rvol', 'return_24h', 'volume_24h'
        ]

        df = df[columns]
        df.to_csv(filepath, index=False)

        self.logger.info(f"💾 Trade log saved to: {filepath}")

    def save_equity_curve(self, filepath: str):
        """
        Save equity curve to CSV

        Args:
            filepath: Output CSV path (e.g., 'equity_curve.csv')
        """
        if not self.portfolio.closed_positions:
            self.logger.warning("No trades for equity curve")
            return

        equity_points = []
        running_equity = self.config.starting_equity

        for pos in self.portfolio.closed_positions:
            equity_points.append({
                'timestamp': pos.exit_time.isoformat(),
                'equity': running_equity + pos.pnl_usd,
                'pnl': pos.pnl_usd,
                'symbol': pos.symbol
            })
            running_equity += pos.pnl_usd

        df = pd.DataFrame(equity_points)
        df.to_csv(filepath, index=False)

        self.logger.info(f"📊 Equity curve saved to: {filepath}")
