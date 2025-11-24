import ccxt
import time
import logging

class ExchangeClient:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.client = None

        if self.config.sim_mode:
            # In SIM mode, use public endpoints only
            self.logger.info("🌐 ExchangeClient initialized in SIM mode (public endpoints only, no API keys)")
            self.client = ccxt.mexc({
                "enableRateLimit": True,
            })
        else:
            # In live mode, initialize the client with API keys
            self.client = ccxt.mexc({
                'apiKey': self.config.mexc_api_key,
                'secret': self.config.mexc_secret_key,
                'timeout': 8000,
                'enableRateLimit': True,
            })
            self.logger.info("🌐 ExchangeClient initialized in LIVE mode (private endpoints enabled)")

    def _retry_request(self, func, *args, **kwargs):
        for attempt in range(3):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Error on attempt {attempt + 1}: {e}")
                time.sleep(2)
        raise Exception("Max retries exceeded")

    def get_klines(self, symbol, timeframe, limit):
        if self.config.sim_mode:
            # Simulate fetching market data
            self.logger.info(f"Simulating fetching OHLCV for {symbol} with timeframe {timeframe}.")
            return [[0, 0, 0, 0, 0, 0]] * limit  # Placeholder for simulated data
        else:
            return self._retry_request(self.client.fetch_ohlcv, symbol, timeframe, limit)

    def get_order_book(self, symbol):
        if self.config.sim_mode:
            self.logger.info(f"Simulating fetching order book for {symbol}.")
            return {}  # Placeholder for simulated order book
        else:
            return self._retry_request(self.client.fetch_order_book, symbol)

    def get_balance(self):
        if self.config.sim_mode:
            self.logger.info("Simulating fetching balance.")
            return {"free": {}, "used": {}, "total": {}}  # Placeholder for simulated balance
        else:
            return self._retry_request(self.client.fetch_balance)

    def create_order(self, symbol, side, amount, order_type, price=None, params={}):
        if self.config.sim_mode:
            self.logger.info(f"Simulating order creation: {side} {amount} of {symbol}.")
            return {"id": "simulated_order_id"}  # Placeholder for simulated order
        else:
            return self._retry_request(self.client.create_order, symbol, side, amount, order_type, price, params)

    def get_open_positions(self):
        if self.config.sim_mode:
            self.logger.info("Simulating fetching open positions.")
            return []  # Placeholder for simulated open positions
        else:
            return self._retry_request(self.client.fetch_open_positions)

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
