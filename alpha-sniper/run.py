#!/usr/bin/env python3
"""
Alpha Sniper V4.2 - Production CLI Entry Point

Usage:
    python run.py --mode sim    # Safe: simulation mode
    python run.py --mode live   # DANGEROUS: real money trading!
    python run.py --mode sim --once  # Single cycle test

Safety:
    - LIVE mode requires BOTH --mode live flag AND SIM_MODE=false in .env
    - Will refuse to start if configuration is inconsistent
    - Validates API keys presence/absence based on mode
"""
import sys
import os
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import Config
from utils import setup_logger_production
from main import AlphaSniperBot


def validate_mode_safety(mode: str, config: Config) -> tuple[bool, str]:
    """
    Validate that CLI mode matches config and credentials

    Returns:
        (is_valid, error_message)
    """
    cli_wants_live = (mode == "live")
    env_says_live = not config.sim_mode

    # Rule 1: CLI and ENV must agree
    if cli_wants_live != env_says_live:
        return False, (
            f"SAFETY ERROR: Mode mismatch!\n"
            f"  CLI flag: --mode {mode} (wants {'LIVE' if cli_wants_live else 'SIM'})\n"
            f"  .env SIM_MODE: {config.sim_mode} (means {'SIM' if config.sim_mode else 'LIVE'})\n"
            f"  These must match. Fix .env or CLI flag."
        )

    # Rule 2: LIVE mode requires API keys
    if mode == "live":
        if not config.mexc_api_key or not config.mexc_secret_key:
            return False, (
                "SAFETY ERROR: LIVE mode requested but MEXC API keys are missing!\n"
                "  Set MEXC_API_KEY and MEXC_SECRET_KEY in .env"
            )

    # Rule 3: SIM mode should NOT have real keys (optional warning, not fatal)
    if mode == "sim":
        if config.mexc_api_key and len(config.mexc_api_key) > 10:
            print("⚠️  WARNING: You have API keys configured but running in SIM mode")
            print("⚠️  These keys will NOT be used. If you meant LIVE, use --mode live")
            print("")

    return True, ""


def main():
    """
    Production entry point with safety checks
    """
    parser = argparse.ArgumentParser(
        description='Alpha Sniper V4.2 - Crypto Trading Bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py --mode sim            # Run in simulation mode
  python run.py --mode sim --once     # Single test cycle (sim)
  python run.py --mode live           # LIVE TRADING (real money!)

Safety:
  - SIM mode is the default and safest option
  - LIVE mode requires explicit --mode live flag
  - LIVE mode also requires SIM_MODE=false in .env
  - Both must match or bot refuses to start
        """
    )

    parser.add_argument(
        '--mode',
        type=str,
        choices=['sim', 'live'],
        required=True,
        help='Trading mode: sim (safe) or live (REAL MONEY!)'
    )

    parser.add_argument(
        '--once',
        action='store_true',
        help='Run single cycle then exit (for testing)'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='.env',
        help='Path to .env config file (default: .env)'
    )

    args = parser.parse_args()

    # Set config file path if specified
    if args.config != '.env':
        os.environ['ALPHA_SNIPER_ENV_FILE'] = args.config

    # Load config
    try:
        config = Config()
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)

    # Validate mode safety
    is_safe, error_msg = validate_mode_safety(args.mode, config)
    if not is_safe:
        print("=" * 70)
        print(error_msg)
        print("=" * 70)
        sys.exit(1)

    # Print big scary warning for LIVE mode
    if args.mode == "live":
        print("")
        print("🚨" * 35)
        print("⚠️  " + " " * 60 + "⚠️")
        print("⚠️  " + "LIVE TRADING MODE - REAL MONEY AT RISK!".center(60) + "⚠️")
        print("⚠️  " + " " * 60 + "⚠️")
        print("🚨" * 35)
        print("")
        print("This bot will place REAL orders with REAL money on MEXC exchange.")
        print("You can lose money. Ensure you have:")
        print("  ✓ Tested thoroughly in SIM mode")
        print("  ✓ Reviewed and understood all risk parameters")
        print("  ✓ Set appropriate position sizes")
        print("  ✓ Configured stop losses correctly")
        print("")

        # Require explicit confirmation in interactive terminals
        if sys.stdin.isatty():
            response = input("Type 'I UNDERSTAND THE RISK' to continue: ")
            if response != "I UNDERSTAND THE RISK":
                print("❌ Confirmation not received. Exiting for safety.")
                sys.exit(1)
        print("")

    # Setup production logging
    logger = setup_logger_production(mode=args.mode)

    # Log startup
    logger.info("=" * 70)
    logger.info("🚀 Alpha Sniper V4.2 Starting (Production Deployment)")
    logger.info(f"🔧 Mode: {args.mode.upper()}")
    logger.info(f"💰 Starting Equity: ${config.starting_equity:.2f}")
    logger.info(f"🔑 API Keys: {'Present' if config.mexc_api_key else 'Missing'}")
    logger.info(f"📁 Config: {args.config}")
    logger.info("=" * 70)

    # Create and run bot (delegates to existing main.py logic)
    bot = None
    exit_code = 0

    try:
        # Import here to ensure logging is setup first
        import signal

        bot = AlphaSniperBot()

        # Handle graceful shutdown
        def signal_handler(sig, frame):
            logger.info("")
            logger.info("👋 Received shutdown signal")
            if bot:
                bot.shutdown()  # Sets bot.running = False and saves state

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Run mode
        if args.once:
            logger.info("🧪 Running in --once test mode (single cycle)")
            bot.trading_cycle()
            logger.info("✅ Test cycle complete, exiting")
            bot.shutdown()
            exit_code = 0
        else:
            # Start health check server in background thread
            from alpha_sniper.health import start_health_server
            start_health_server(bot)

            # Normal scheduled mode - will run until bot.running = False
            bot.run()

            # Clean shutdown after bot.run() completes
            logger.info("📊 Bot run loop completed normally")
            exit_code = 0

    except KeyboardInterrupt:
        logger.info("👋 Keyboard interrupt received")
        if bot:
            bot.shutdown()
        exit_code = 0
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        logger.exception(e)
        if bot:
            try:
                bot.shutdown()
            except Exception as shutdown_error:
                logger.error(f"Error during emergency shutdown: {shutdown_error}")
        exit_code = 1
    finally:
        # Exit cleanly with appropriate code
        # This happens AFTER all cleanup, outside async context
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
