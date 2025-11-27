"""
Exchange wrapper for Alpha Sniper V4.2
Supports both Real (MEXC) and Simulated modes
"""
import ccxt
import time
import logging
import random
import numpy as np
from datetime import datetime, timedelta


class SimulatedExchange:
    """
    Simulated exchange for SIM_MODE
    No real API calls, generates fake but coherent data
    """
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.logger.info("🌐 SimulatedExchange initialized (no API calls, fake data)")

        # Simulated state
        self.fake_positions = []
        self.base_price_btc = 50000.0
        self.fake_markets = self._generate_fake_markets()

    def _generate_fake_markets(self):
        """Generate fake market data for simulation"""
        markets = {}

        # BTC/USDT (main for regime)
        markets['BTC/USDT'] = {
            'active': True,
            'symbol': 'BTC/USDT',
            'base': 'BTC',
            'quote': 'USDT',
            'spot': True
        }

        # Generate 20 fake altcoins
        alts = ['ETH', 'BNB', 'SOL', 'ADA', 'XRP', 'DOT', 'AVAX', 'MATIC', 'LINK', 'UNI',
                'ATOM', 'LTC', 'BCH', 'ETC', 'FIL', 'AAVE', 'CRV', 'SNX', 'SUSHI', 'COMP']

        for alt in alts:
            symbol = f'{alt}/USDT'
            markets[symbol] = {
                'active': True,
                'symbol': symbol,
                'base': alt,
                'quote': 'USDT',
                'spot': True
            }

        return markets

    def get_markets(self):
        """Return fake markets"""
        return self.fake_markets

    def get_klines(self, symbol: str, timeframe: str, limit: int = 200):
        """
        Generate fake OHLCV data
        Returns: list of [timestamp, open, high, low, close, volume]
        """
        if symbol == 'BTC/USDT':
            return self._generate_btc_klines(timeframe, limit)
        else:
            return self._generate_alt_klines(symbol, timeframe, limit)

    def _generate_btc_klines(self, timeframe: str, limit: int):
        """Generate BTC fake data with gradual uptrend and market cycles"""
        now = int(datetime.now().timestamp() * 1000)

        # Timeframe to milliseconds
        tf_map = {'1d': 86400000, '1h': 3600000, '15m': 900000}
        tf_ms = tf_map.get(timeframe, 3600000)

        ohlcv = []
        current_price = self.base_price_btc

        # Generate older candles first
        for i in range(limit, 0, -1):
            ts = now - (i * tf_ms)

            # Gradual uptrend: +0.05% per candle on average
            trend_move = current_price * 0.0005

            # Add market cycles (trending, consolidation, pullback)
            cycle_position = i % 50  # 50-candle cycles
            if cycle_position < 20:  # Trending phase
                noise = random.uniform(-50, 150)  # Upward bias
            elif cycle_position < 35:  # Consolidation phase
                noise = random.uniform(-100, 100)  # Sideways
            else:  # Pullback phase
                noise = random.uniform(-150, 50)  # Downward bias

            current_price = current_price + trend_move + noise

            o = current_price
            h = current_price * random.uniform(1.002, 1.015)
            l = current_price * random.uniform(0.985, 0.998)
            c = current_price * random.uniform(0.995, 1.005)
            v = random.uniform(2000, 8000)

            ohlcv.append([ts, o, h, l, c, v])

        return ohlcv

    def _generate_alt_klines(self, symbol: str, timeframe: str, limit: int):
        """Generate altcoin fake data with occasional trends and volume spikes"""
        now = int(datetime.now().timestamp() * 1000)

        tf_map = {'1d': 86400000, '1h': 3600000, '15m': 900000}
        tf_ms = tf_map.get(timeframe, 3600000)

        # Base price varies by coin
        base = random.uniform(10, 100)

        # Hash symbol to get consistent behavior per coin
        symbol_hash = hash(symbol) % 100

        # Determine if this coin is in an uptrend, downtrend, or sideways
        if symbol_hash < 30:  # 30% trending up
            trend = 0.008  # +0.8% per candle - STRONG uptrend
            vol_multiplier = 2.5  # Higher base volume
        elif symbol_hash < 50:  # 20% trending down
            trend = -0.006
            vol_multiplier = 1.5
        else:  # 50% sideways
            trend = 0
            vol_multiplier = 1.0

        ohlcv = []
        current_price = base

        for i in range(limit, 0, -1):
            ts = now - (i * tf_ms)

            # Apply accelerating trend (stronger in recent candles)
            trend_strength = 1.0 + (0.5 * (limit - i) / limit)  # 1.0 to 1.5x
            current_price = current_price * (1 + (trend * trend_strength))

            # Less noise for cleaner trends
            noise = random.uniform(0.99, 1.01)
            price = current_price * noise

            o = price
            h = price * random.uniform(1.005, 1.02)
            l = price * random.uniform(0.98, 0.995)
            c = price * random.uniform(0.995, 1.005)

            # Volume increases with trend - recent candles have MUCH higher volume
            recency_factor = 1.0 + (2.0 * (limit - i) / limit)  # 1.0x to 3.0x
            base_vol = random.uniform(300, 600) * vol_multiplier * recency_factor

            # Frequent volume spikes in recent candles
            if i <= 10 or random.random() < 0.25:  # Last 10 candles OR 25% chance
                v = base_vol * random.uniform(1.8, 3.5)  # Big spike
            else:
                v = base_vol

            ohlcv.append([ts, o, h, l, c, v])

        return ohlcv

    def get_ticker(self, symbol: str):
        """Generate fake ticker"""
        # Get recent price from klines
        klines = self.get_klines(symbol, '1h', limit=2)
        if not klines:
            return None

        last_price = klines[-1][4]  # close

        return {
            'symbol': symbol,
            'last': last_price,
            'close': last_price,
            'bid': last_price * 0.999,
            'ask': last_price * 1.001,
            'quoteVolume': random.uniform(100000, 500000),  # Above min threshold
            'timestamp': int(time.time() * 1000)
        }

    def get_orderbook(self, symbol: str):
        """Generate fake orderbook"""
        ticker = self.get_ticker(symbol)
        mid = ticker['last']

        return {
            'bids': [[mid * 0.999, random.uniform(10, 100)]],
            'asks': [[mid * 1.001, random.uniform(10, 100)]]
        }

    def get_funding_rate(self, symbol: str):
        """Return fake funding rate (low, so shorts aren't rejected)"""
        return random.uniform(-0.0001, 0.0002)

    def get_liquidity_metrics(self, symbol: str):
        """
        === UPGRADE D: Liquidity-Aware Position Sizing ===
        Return fake but realistic liquidity metrics
        """
        ticker = self.get_ticker(symbol)
        if not ticker:
            return {'spread_pct': 1.0, 'depth_usd': 5000}

        spread_pct = ((ticker['ask'] - ticker['bid']) / ticker['last']) * 100 if ticker['last'] > 0 else 0.5

        # Simulate varying liquidity: some coins have better depth than others
        symbol_hash = hash(symbol) % 100
        if symbol_hash < 30:
            # Good liquidity
            depth_usd = random.uniform(15000, 30000)
        elif symbol_hash < 70:
            # Medium liquidity
            depth_usd = random.uniform(8000, 18000)
        else:
            # Poor liquidity
            depth_usd = random.uniform(2000, 10000)

        return {
            'spread_pct': spread_pct,
            'depth_usd': depth_usd
        }

    def create_order(self, symbol, type, side, amount, price=None, params=None):
        """Simulate order creation"""
        ticker = self.get_ticker(symbol)
        fill_price = ticker['last']

        order = {
            'id': f'sim_{int(time.time())}_{random.randint(1000, 9999)}',
            'symbol': symbol,
            'type': type,
            'side': side,
            'amount': amount,
            'price': fill_price,
            'filled': amount,
            'status': 'closed',
            'timestamp': int(time.time() * 1000)
        }

        self.logger.info(f"[SIM] Order created: {side} {amount} {symbol} @ {fill_price}")
        return order

    def fetch_open_positions(self):
        """Return simulated open positions"""
        return self.fake_positions

    def cancel_order(self, order_id, symbol=None):
        """Simulate order cancellation"""
        self.logger.info(f"[SIM] Order cancelled: {order_id}")
        return {'id': order_id, 'status': 'canceled'}

    def fetch_balance(self):
        """Return simulated balance"""
        return {
            'USDT': {
                'free': self.config.starting_equity,
                'used': 0,
                'total': self.config.starting_equity
            }
        }


class RealExchange:
    """
    Real exchange wrapper for LIVE mode
    Uses actual MEXC via ccxt
    """
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

        if not config.mexc_api_key or not config.mexc_secret_key:
            raise Exception("LIVE mode requires MEXC_API_KEY and MEXC_SECRET_KEY")

        self.client = ccxt.mexc({
            'apiKey': config.mexc_api_key,
            'secret': config.mexc_secret_key,
            'timeout': 8000,
            'enableRateLimit': True,
        })

        self.logger.info("🌐 RealExchange initialized (LIVE mode with MEXC)")

    def _with_retries(self, func, label: str, max_attempts: int = 3, delay_sec: float = 2.0):
        """Retry wrapper for network calls"""
        for attempt in range(max_attempts):
            try:
                return func()
            except Exception as e:
                self.logger.error(f"Error on attempt {attempt + 1}/{max_attempts}: {label} - {repr(e)}")
                if attempt < max_attempts - 1:
                    time.sleep(delay_sec)

        self.logger.error(f"Max retries exceeded for: {label}")
        return None

    def get_markets(self):
        """Load markets from MEXC"""
        return self._with_retries(lambda: self.client.load_markets(), "load_markets")

    def get_klines(self, symbol: str, timeframe: str, limit: int = 200):
        """Fetch OHLCV from MEXC"""
        return self._with_retries(
            lambda: self.client.fetch_ohlcv(symbol, timeframe, limit=limit),
            f"fetch_ohlcv {symbol} {timeframe}"
        )

    def get_ticker(self, symbol: str):
        """Fetch ticker from MEXC"""
        return self._with_retries(lambda: self.client.fetch_ticker(symbol), f"fetch_ticker {symbol}")

    def get_orderbook(self, symbol: str):
        """Fetch orderbook from MEXC"""
        return self._with_retries(lambda: self.client.fetch_order_book(symbol), f"fetch_orderbook {symbol}")

    def get_funding_rate(self, symbol: str):
        """Fetch funding rate from MEXC"""
        try:
            funding = self._with_retries(
                lambda: self.client.fetch_funding_rate(symbol),
                f"fetch_funding_rate {symbol}"
            )
            if funding:
                return funding.get('fundingRate', 0)
        except:
            pass
        return 0

    def get_liquidity_metrics(self, symbol: str):
        """
        === UPGRADE D: Liquidity-Aware Position Sizing ===
        Calculate liquidity metrics from real orderbook data
        """
        try:
            ticker = self.get_ticker(symbol)
            orderbook = self.get_orderbook(symbol)

            if not ticker or not orderbook:
                return {'spread_pct': 1.0, 'depth_usd': 5000}

            # Calculate spread
            bid = ticker.get('bid', 0)
            ask = ticker.get('ask', 0)
            last = ticker.get('last', 1)

            spread_pct = ((ask - bid) / last) * 100 if last > 0 and bid > 0 and ask > 0 else 0.5

            # Calculate depth (sum of top 10 bid/ask levels)
            depth_usd = 0
            bids = orderbook.get('bids', [])[:10]
            asks = orderbook.get('asks', [])[:10]

            for price, amount in bids:
                depth_usd += price * amount

            for price, amount in asks:
                depth_usd += price * amount

            return {
                'spread_pct': spread_pct,
                'depth_usd': depth_usd
            }

        except Exception as e:
            self.logger.debug(f"Error getting liquidity metrics for {symbol}: {e}")
            return {'spread_pct': 1.0, 'depth_usd': 5000}

    def create_order(self, symbol, type, side, amount, price=None, params=None):
        """Create real order on MEXC"""
        return self._with_retries(
            lambda: self.client.create_order(symbol, type, side, amount, price, params),
            f"create_order {symbol}"
        )

    def fetch_open_positions(self):
        """Fetch open positions from MEXC"""
        return self._with_retries(lambda: self.client.fetch_positions(), "fetch_positions")

    def cancel_order(self, order_id, symbol=None):
        """Cancel order on MEXC"""
        return self._with_retries(
            lambda: self.client.cancel_order(order_id, symbol),
            f"cancel_order {order_id}"
        )

    def fetch_balance(self):
        """Fetch balance from MEXC"""
        return self._with_retries(lambda: self.client.fetch_balance(), "fetch_balance")


# Factory function
def create_exchange(config, logger):
    """
    Factory to create appropriate exchange based on SIM_MODE
    """
    if config.sim_mode:
        return SimulatedExchange(config, logger)
    else:
        return RealExchange(config, logger)
