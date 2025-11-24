import time
from config import load_config
from exchange import MexcExchange
from risk_engine import RiskEngine
from signals.scanner import Scanner
from utils.logger import setup_logger
from utils.telegram import send_telegram


def main():
    logger = setup_logger()
    config = load_config()

    scan_interval = int(config.get("SCAN_INTERVAL_SECONDS", 300))
    sim_mode = config.get("SIM_MODE", True)
    starting_equity = float(config.get("STARTING_EQUITY", 1000))

    send_telegram(f"🚀 Bot started (SIM_MODE={sim_mode})")
    logger.info("🚀 Starting Alpha Sniper V4.2 bot...")
    logger.info(f"SIM_MODE={sim_mode} | STARTING_EQUITY={starting_equity} | SCAN_INTERVAL={scan_interval}s")

    # Core components
    exchange = MexcExchange(config, logger)
    risk_engine = RiskEngine(exchange, config, logger)
    scanner = Scanner(exchange, risk_engine, config, logger)

    while True:
        logger.info("=" * 80)
        logger.info("🔄 New bot cycle starting...")
        send_telegram("🔄 New cycle started")

        # 1) Regime detection
        try:
            regime = risk_engine.get_current_regime()
            logger.info(f"📊 Current regime: {regime}")
            send_telegram(f"📊 Regime changed → {regime}")
        except Exception:
            logger.exception("❌ Failed to update/get market regime")
            regime = "UNKNOWN"

        # 2) Run scanner
        try:
            logger.info("🔍 Running scanner...")
            signals = scanner.scan()
            logger.info("✅ Scanner cycle finished")
            if signals['long'] > 0 or signals['short'] > 0 or signals['pump'] > 0:
                send_telegram(f"📡 Signals detected | L={signals['long']} S={signals['short']} P={signals['pump']}")
        except Exception as e:
            logger.exception("❌ Error during scanner cycle")
            send_telegram(f"❌ Error during scanner cycle: {str(e)}")

        # 3) Sleep until next cycle
        logger.info(f"😴 Sleeping {scan_interval} seconds before next cycle...")
        time.sleep(scan_interval)


if __name__ == "__main__":
    main()
