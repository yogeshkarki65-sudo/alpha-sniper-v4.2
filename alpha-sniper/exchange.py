import ccxt
import time
import logging

class ExchangeClient:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.client = None

        if self.config.sim_mode:
            self.logger.info("🌐 ExchangeClient initialized in SIM mode (public endpoints only, no API keys)")
            self.client = ccxt.mexc({
                "enableRateLimit": True,
            })
        else:
            self.client = ccxt.mexc({
                'apiKey': self.config.mexc_api_key,
                'secret': self.config.mexc_secret_key,
                'timeout': 8000,
                'enableRateLimit': True,
            })
            self.logger.info("🌐 ExchangeClient initialized in LIVE mode (private endpoints enabled)")

    def _with_retries(self, func, label: str, max_attempts: int = 3, delay_sec: float = 2.0):
        for attempt in range(max_attempts):
            try:
                return func()
            except Exception as e:
                if self.config.sim_mode and "code": 10072 in str(e):
                    self.logger.warning("Warning: API key info invalid in SIM mode.")
                    return None
                self.logger.error(f"Error on attempt {attempt + 1}: {label} {repr(e)}")
                time.sleep(delay_sec)
        self.logger.error(f"Error {label}: Max retries exceeded")
        return None

    def get_klines(self, symbol: str, timeframe: str, limit: int = 200):
        return self._with_retries(lambda: self.client.fetch_ohlcv(symbol, timeframe, limit=limit), f"fetch_ohlcv {symbol} {timeframe}")

    def get_ticker(self, symbol: str):
        return self._with_retries(lambda: self.client.fetch_ticker(symbol), f"fetch_ticker {symbol}")

    def get_markets(self):
        return self._with_retries(lambda: self.client.load_markets(), "load_markets")

    def create_order(self, symbol, type, side, amount, price=None, params=None):
        if self.config.sim_mode:
            self.logger.info(f"Simulating order creation: {side} {amount} of {symbol}.")
            return {"id": "simulated_order_id"}  # Placeholder for simulated order
        else:
            return self._with_retries(lambda: self.client.create_order(symbol, type, side, amount, price, params), f"create_order {symbol}")

    def get_balance(self):
        if self.config.sim_mode:
            self.logger.info("Simulating fetching balance.")
            return {"free": {}, "used": {}, "total": {}}  # Placeholder for simulated balance
        else:
            return self._with_retries(lambda: self.client.fetch_balance(), "fetch_balance")

    def get_open_positions(self):
        if self.config.sim_mode:
            self.logger.info("Simulating fetching open positions.")
            return []  # Placeholder for simulated open positions
        else:
            return self._with_retries(lambda: self.client.fetch_open_positions(), "fetch_open_positions")

    def close_all_spot_positions(self):
        if self.config.sim_mode:
            self.logger.info("Simulating closing all spot positions.")
            return  # Placeholder for simulated close
        else:
            # Logic to close all spot positions
            pass

    def move_futures_sl_to_breakeven(self):
        if self.config.sim_mode:
            self.logger.info("Simulating moving futures SL to breakeven.")
            return  # Placeholder for simulated action
        else:
            # Logic to move futures stop loss to breakeven
            pass
