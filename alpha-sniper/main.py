import time
import schedule
from config import Config
from exchange import Exchange
from risk_engine import RiskEngine
from signals.scanner import Scanner
from utils.logger import setup_logger

def main():
    config = Config()
    logger = setup_logger()
    exchange = Exchange(config)
    risk_engine = RiskEngine(config, exchange)
    scanner = Scanner(config, exchange, risk_engine)

    # Schedule the scanner
    schedule.every(config.SCAN_INTERVAL_SECONDS).seconds.do(scanner.run)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
