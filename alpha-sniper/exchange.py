import ccxt
import time
import logging

class MexcExchange:
    def __init__(self, config, logger):
        self.config = config
        self.client = ccxt.mexc({
            'apiKey': self.config.MEXC_API_KEY,
            'secret': self.config.MEXC_SECRET_KEY,
            'timeout': 8000,
            'enableRateLimit': True,
        })
        self.logger = logger

    def _retry_request(self, func, *args, **kwargs):
        for attempt in range(3):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Error on attempt {attempt + 1}: {e}")
                time.sleep(2)
        raise Exception("Max retries exceeded")

    def get_klines(self, symbol, timeframe, limit):
        return self._retry_request(self.client.fetch_ohlcv, symbol, timeframe, limit)

    def get_order_book(self, symbol):
        return self._retry_request(self.client.fetch_order_book, symbol)

    def get_balance(self):
        return self._retry_request(self.client.fetch_balance)

    def create_order(self, symbol, side, amount, order_type, price=None, params={}):
        return self._retry_request(self.client.create_order, symbol, side, amount, order_type, price, params)

    def get_open_positions(self):
        return self._retry_request(self.client.fetch_open_positions)

    def close_all_spot_positions(self):
        # Logic to close all spot positions
        pass

    def move_futures_sl_to_breakeven(self):
        # Logic to move futures stop loss to breakeven
        pass
