#!/usr/bin/env python3
"""
Pump Strategy Backtester for Alpha Sniper V4.2

Backtests the pump-only trading strategy using historical OHLCV data.
Reuses the EXACT same signal logic as LIVE mode.

Usage:
    python backtest_pump.py --symbols BTCUSDT,ETHUSDT --start 2025-10-01 --end 2025-12-01

Example with custom config:
    python backtest_pump.py \\
        --symbols SOLUSDT,SUIUSDT,1000PEPEUSDT \\
        --start 2025-10-01 \\
        --end 2025-12-01 \\
        --equity 62.88 \\
        --pump-risk 0.004 \\
        --pump-aggressive

Data Requirements:
    Place CSV files in data/ directory with format:
    - data/BTCUSDT_1m.csv
    - data/BTCUSDT_15m.csv
    - data/BTCUSDT_1h.csv

    CSV format:
    timestamp,open,high,low,close,volume
    1609459200000,0.5,0.51,0.49,0.50,1000000
    ...
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add alpha-sniper to path
sys.path.insert(0, str(Path(__file__).parent / 'alpha-sniper'))

from backtest.engine import BacktestConfig, PumpBacktester


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Backtest PUMP-ONLY strategy for Alpha Sniper V4.2',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # Required
    parser.add_argument(
        '--symbols',
        required=True,
        help='Comma-separated list of symbols (e.g., BTCUSDT,ETHUSDT,SOLUSDT)'
    )
    parser.add_argument(
        '--start',
        required=True,
        help='Start date (YYYY-MM-DD or ISO timestamp)'
    )
    parser.add_argument(
        '--end',
        required=True,
        help='End date (YYYY-MM-DD or ISO timestamp)'
    )

    # Optional strategy parameters
    parser.add_argument(
        '--equity',
        type=float,
        default=62.88,
        help='Starting equity in USDT (default: 62.88)'
    )
    parser.add_argument(
        '--data-dir',
        default='data',
        help='Directory containing CSV files (default: data/)'
    )
    parser.add_argument(
        '--output-dir',
        default='backtest_results',
        help='Output directory for results (default: backtest_results/)'
    )
    parser.add_argument(
        '--scan-interval',
        type=int,
        default=30,
        help='Scan interval in minutes (default: 30)'
    )

    # Pump strategy parameters
    parser.add_argument(
        '--pump-risk',
        type=float,
        default=0.004,
        help='Risk per trade (default: 0.004 = 0.4%%)'
    )
    parser.add_argument(
        '--pump-max-concurrent',
        type=int,
        default=1,
        help='Max concurrent positions (default: 1)'
    )
    parser.add_argument(
        '--pump-min-rvol',
        type=float,
        default=1.5,
        help='Minimum RVOL (default: 1.5)'
    )
    parser.add_argument(
        '--pump-min-24h-return',
        type=float,
        default=0.20,
        help='Minimum 24h return (default: 0.20 = 20%%)'
    )
    parser.add_argument(
        '--pump-max-24h-return',
        type=float,
        default=5.00,
        help='Maximum 24h return (default: 5.00 = 500%%)'
    )
    parser.add_argument(
        '--pump-min-volume',
        type=float,
        default=500000,
        help='Minimum 24h quote volume in USDT (default: 500000)'
    )
    parser.add_argument(
        '--pump-min-score',
        type=int,
        default=72,
        help='Minimum signal score (default: 72)'
    )
    parser.add_argument(
        '--pump-max-hold-hours',
        type=float,
        default=2.0,
        help='Max hold time in hours (default: 2.0)'
    )

    # Aggressive mode
    parser.add_argument(
        '--pump-aggressive',
        action='store_true',
        help='Enable aggressive pump mode (looser filters)'
    )

    # Risk management
    parser.add_argument(
        '--max-portfolio-heat',
        type=float,
        default=0.008,
        help='Max portfolio heat (default: 0.008 = 0.8%%)'
    )
    parser.add_argument(
        '--max-daily-loss',
        type=float,
        default=0.02,
        help='Max daily loss %% (default: 0.02 = 2%%)'
    )
    parser.add_argument(
        '--trailing-stop',
        type=float,
        default=0.35,
        help='Trailing stop %% (default: 0.35 = 35%%)'
    )

    # Output control
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress detailed logs (only show summary)'
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()

    # Parse symbols
    symbols = [s.strip() + '/USDT' if '/' not in s else s.strip() for s in args.symbols.split(',')]

    print("\n🚀 Alpha Sniper V4.2 - Pump Backtest")
    print("=" * 70)
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Period: {args.start} to {args.end}")
    print(f"Starting Equity: ${args.equity:.2f}")
    print("=" * 70)
    print()

    # Create config
    config = BacktestConfig(
        starting_equity=args.equity,
        pump_only_mode=True,
        pump_risk_per_trade=args.pump_risk,
        pump_max_concurrent=args.pump_max_concurrent,
        pump_min_rvol=args.pump_min_rvol,
        pump_min_24h_return=args.pump_min_24h_return,
        pump_max_24h_return=args.pump_max_24h_return,
        pump_min_24h_quote_volume=args.pump_min_volume,
        pump_min_score=args.pump_min_score,
        pump_max_hold_hours=args.pump_max_hold_hours,
        pump_aggressive_mode=args.pump_aggressive,
        max_portfolio_heat=args.max_portfolio_heat,
        max_daily_loss_pct=args.max_daily_loss,
        trailing_stop_pct=args.trailing_stop
    )

    # Create backtester
    backtester = PumpBacktester(
        data_dir=args.data_dir,
        config=config,
        verbose=not args.quiet
    )

    # Load data
    loaded = backtester.load_data(symbols)

    if loaded == 0:
        print("❌ No data loaded. Please check:")
        print(f"   - CSV files exist in {args.data_dir}/")
        print("   - Filenames match pattern: SYMBOLNAME_timeframe.csv")
        print(f"   - Example: {args.data_dir}/BTCUSDT_1m.csv")
        sys.exit(1)

    # Run backtest
    try:
        stats = backtester.run(
            start_time=args.start,
            end_time=args.end,
            scan_interval_minutes=args.scan_interval
        )
    except KeyboardInterrupt:
        print("\n⚠️ Backtest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Save results
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Trade log
    trade_log_path = output_dir / f"trades_{timestamp}.csv"
    backtester.save_trade_log(str(trade_log_path))

    # Equity curve
    equity_curve_path = output_dir / f"equity_{timestamp}.csv"
    backtester.save_equity_curve(str(equity_curve_path))

    # Summary stats
    summary_path = output_dir / f"summary_{timestamp}.txt"
    with open(summary_path, 'w') as f:
        f.write("=" * 70 + "\n")
        f.write("PUMP BACKTEST SUMMARY\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Period: {args.start} to {args.end}\n")
        f.write(f"Symbols: {', '.join(symbols)}\n")
        f.write(f"Starting Equity: ${stats['starting_equity']:.2f}\n")
        f.write("\n")
        f.write(f"Total Trades: {stats['total_trades']}\n")
        f.write(f"Wins / Losses: {stats['wins']}W / {stats['losses']}L\n")
        f.write(f"Win Rate: {stats['win_rate']:.1f}%\n")
        f.write(f"Average R: {stats['avg_r']:.2f}R\n")
        f.write(f"Avg Win: ${stats['avg_win_usd']:.2f}\n")
        f.write(f"Avg Loss: ${stats['avg_loss_usd']:.2f}\n")
        f.write("\n")
        f.write(f"Final Equity: ${stats['final_equity']:.2f}\n")
        f.write(f"Total P&L: ${stats['total_pnl_usd']:+.2f} ({stats['total_pnl_pct']:+.2f}%)\n")
        f.write(f"Total Fees: ${stats['total_fees']:.2f}\n")
        f.write(f"Max Drawdown: {stats['max_drawdown_pct']:.2f}%\n")
        f.write("\n")
        f.write(f"Best Trade: {stats['best_trade_symbol']} ${stats['best_trade_usd']:.2f}\n")
        f.write(f"Worst Trade: {stats['worst_trade_symbol']} ${stats['worst_trade_usd']:.2f}\n")
        f.write("\n")
        f.write("Strategy Parameters:\n")
        f.write(f"  PUMP_RISK_PER_TRADE: {args.pump_risk}\n")
        f.write(f"  PUMP_MIN_RVOL: {args.pump_min_rvol}\n")
        f.write(f"  PUMP_MIN_24H_RETURN: {args.pump_min_24h_return}\n")
        f.write(f"  PUMP_MAX_24H_RETURN: {args.pump_max_24h_return}\n")
        f.write(f"  PUMP_MIN_SCORE: {args.pump_min_score}\n")
        f.write(f"  PUMP_MAX_HOLD_HOURS: {args.pump_max_hold_hours}\n")
        f.write(f"  PUMP_AGGRESSIVE_MODE: {args.pump_aggressive}\n")

    print(f"\n📁 Results saved to: {output_dir}/")
    print(f"   - {trade_log_path.name}")
    print(f"   - {equity_curve_path.name}")
    print(f"   - {summary_path.name}")
    print()

    # Return code based on profitability
    if stats['total_pnl_usd'] > 0:
        print("✅ Backtest PROFITABLE")
        return 0
    else:
        print("⚠️ Backtest UNPROFITABLE")
        return 1


if __name__ == '__main__':
    sys.exit(main())
