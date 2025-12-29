#!/usr/bin/env python3
"""
Alpha Sniper V4.2 - Production CLI Entry Point

Usage:
    python run.py           # Run bot in LIVE mode
    python run.py --once    # Single cycle test

Safety:
    - Always runs in LIVE mode with real money
    - Validates API keys are present
    - Use systemd service for production deployment
"""
import argparse
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import Config  # noqa: E402
from main import AlphaSniperBot  # noqa: E402
from utils import setup_logger_production  # noqa: E402


def main():
    """
    Production entry point - LIVE mode only
    """
    parser = argparse.ArgumentParser(
        description='Alpha Sniper V4.2 - Crypto Trading Bot (LIVE MODE ONLY)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py           # Run bot in LIVE mode
  python run.py --once    # Single test cycle then exit

Safety:
  - This always runs in LIVE mode with REAL MONEY
  - Ensure you have tested thoroughly before running
  - Use systemd service (alpha-sniper-live.service) for production
        """
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

    # Validate API keys are present
    if not config.mexc_api_key or not config.mexc_secret_key:
        print("=" * 70)
        print("SAFETY ERROR: MEXC API keys are missing!")
        print("  Set MEXC_API_KEY and MEXC_SECRET_KEY in .env")
        print("=" * 70)
        sys.exit(1)

    # Print big scary warning for LIVE mode
    print("")
    print("🚨" * 35)
    print("⚠️  " + " " * 60 + "⚠️")
    print("⚠️  " + "LIVE TRADING MODE - REAL MONEY AT RISK!".center(60) + "⚠️")
    print("⚠️  " + " " * 60 + "⚠️")
    print("🚨" * 35)
    print("")
    print("This bot will place REAL orders with REAL money on MEXC exchange.")
    print("You can lose money. Ensure you have:")
    print("  ✓ Tested thoroughly before running")
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
    logger = setup_logger_production(mode="live")

    # Log startup
    logger.info("=" * 70)
    logger.info("🚀 Alpha Sniper V4.2 Starting (Production Deployment)")
    logger.info("🔧 Mode: LIVE")
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
