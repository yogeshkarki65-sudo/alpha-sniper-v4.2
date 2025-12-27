"""
Exchange wrapper for Alpha Sniper V4.2
Supports both Real (MEXC) and Simulated modes

IMPROVEMENTS:
- Enhanced _with_retries with funding-rate spam suppression
- Clean BaseExchange interface
- Robust error handling with exponential backoff
"""
import random
import time
from datetime import datetime

import ccxt


class BaseExchange:
    """
    Base exchange interface - defines the contract all exchanges must implement
    """
    def get_markets(self):
        raise NotImplementedError

    def get_klines(self, symbol: str, timeframe: str, limit: int = 200):
        raise NotImplementedError

    def get_ticker(self, symbol: str):
        raise NotImplementedError

    def get_last_price(self, symbol: str):
        raise NotImplementedError

    def get_orderbook(self, symbol: str):
        raise NotImplementedError

    def get_funding_rate(self, symbol: str):
        raise NotImplementedError

    def get_liquidity_metrics(self, symbol: str):
        raise NotImplementedError

    def create_order(self, symbol, type, side, amount, price=None, params=None):
        raise NotImplementedError

    def fetch_open_positions(self):
        raise NotImplementedError

    def cancel_order(self, order_id, symbol=None):
        raise NotImplementedError

    def fetch_balance(self):
        raise NotImplementedError


class SimulatedExchange(BaseExchange):
    """
    Simulated exchange for SIM_MODE
    No real API calls, generates fake but coherent data
    FIX: Maintains consistent prices across calls with gradual updates
    """
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.logger.info("🌐 SimulatedExchange initialized (no API calls, fake data)")

        # Simulated state
        self.fake_positions = []
        self.base_price_btc = 50000.0
        self.fake_markets = self._generate_fake_markets()

        # === PRICE CACHE FIX ===
        # Cache klines data to ensure price continuity
        self.klines_cache = {}  # {symbol: {timeframe: [(ts, o, h, l, c, v), ...]}}
        self.cache_timestamps = {}  # {symbol: {timeframe: last_update_ts}}
        self.cache_lifetime = 60  # seconds - update prices every 60s to simulate market movement

        # Initialize current prices (seeded from symbol hash for consistency)
        self.current_prices = {}  # {symbol: price}
        self._initialize_prices()

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

    def _initialize_prices(self):
        """Initialize consistent starting prices for all symbols"""
        # BTC starts at base_price_btc
        self.current_prices['BTC/USDT'] = self.base_price_btc

        # Altcoins get consistent prices based on symbol hash
        alts = ['ETH', 'BNB', 'SOL', 'ADA', 'XRP', 'DOT', 'AVAX', 'MATIC', 'LINK', 'UNI',
                'ATOM', 'LTC', 'BCH', 'ETC', 'FIL', 'AAVE', 'CRV', 'SNX', 'SUSHI', 'COMP']

        for alt in alts:
            symbol = f'{alt}/USDT'
            # Use symbol hash for consistent but varied prices
            symbol_hash = abs(hash(symbol))
            base_price = 10 + (symbol_hash % 500) / 10  # Range: $10 - $60
            self.current_prices[symbol] = base_price

    def _should_update_cache(self, symbol: str, timeframe: str) -> bool:
        """Check if cache should be updated"""
        if symbol not in self.cache_timestamps:
            return True
        if timeframe not in self.cache_timestamps[symbol]:
            return True

        last_update = self.cache_timestamps[symbol][timeframe]
        return (time.time() - last_update) > self.cache_lifetime

    def _update_price(self, symbol: str):
        """Gradually update current price to simulate market movement"""
        if symbol not in self.current_prices:
            self._initialize_prices()

        current = self.current_prices[symbol]

        # Small random walk: ±0.1% to ±0.5% per update (every 60s)
        change_pct = random.uniform(-0.005, 0.005)  # -0.5% to +0.5%

        # Add slight upward bias for trending markets
        if symbol != 'BTC/USDT':
            symbol_hash = abs(hash(symbol)) % 100
            if symbol_hash < 30:  # 30% get upward bias
                change_pct += random.uniform(0.001, 0.003)  # +0.1% to +0.3% bias

        new_price = current * (1 + change_pct)
        self.current_prices[symbol] = new_price

    def get_markets(self):
        """Return fake markets"""
        return self.fake_markets

    def get_klines(self, symbol: str, timeframe: str, limit: int = 200):
        """
        Generate fake OHLCV data with CACHING for price continuity
        Returns: list of [timestamp, open, high, low, close, volume]
        """
        # Check if we should update cache
        should_update = self._should_update_cache(symbol, timeframe)

        # Initialize cache structure if needed
        if symbol not in self.klines_cache:
            self.klines_cache[symbol] = {}
            self.cache_timestamps[symbol] = {}

        # Return cached data if still valid
        if not should_update and timeframe in self.klines_cache[symbol]:
            cached = self.klines_cache[symbol][timeframe]
            # Return last 'limit' candles
            return cached[-limit:] if len(cached) >= limit else cached

        # Generate or update klines
        if symbol == 'BTC/USDT':
            klines = self._generate_btc_klines(timeframe, limit)
        else:
            klines = self._generate_alt_klines(symbol, timeframe, limit)

        # Cache the data
        self.klines_cache[symbol][timeframe] = klines
        self.cache_timestamps[symbol][timeframe] = time.time()

        # Update current price gradually
        if should_update:
            self._update_price(symbol)

        return klines[-limit:]

    def _generate_btc_klines(self, timeframe: str, limit: int):
        """Generate BTC fake data with gradual uptrend and market cycles"""
        now = int(datetime.now().timestamp() * 1000)

        # Timeframe to milliseconds
        tf_map = {'1d': 86400000, '1h': 3600000, '15m': 900000}
        tf_ms = tf_map.get(timeframe, 3600000)

        # Use current price as the latest price for continuity
        latest_price = self.current_prices.get('BTC/USDT', self.base_price_btc)

        ohlcv = []
        # Work backwards from current price
        current_price = latest_price

        # Generate candles from oldest to newest
        prices = [current_price]
        for i in range(limit - 1):
            # Work backwards: reverse the trend to build history
            change_pct = random.uniform(-0.005, 0.002)  # Slight downward bias when going back in time
            current_price = current_price / (1 + change_pct)
            prices.append(current_price)

        # Reverse so oldest is first
        prices.reverse()

        # Build OHLCV candles
        for i in range(limit):
            ts = now - ((limit - i) * tf_ms)
            price = prices[i]

            o = price
            h = price * random.uniform(1.001, 1.008)  # Smaller intrabar moves
            low = price * random.uniform(0.992, 0.999)
            c = price * random.uniform(0.998, 1.002)  # Close near open
            v = random.uniform(2000, 8000)

            ohlcv.append([ts, o, h, low, c, v])

        # Ensure the last candle close matches current price
        if ohlcv:
            ohlcv[-1][4] = latest_price  # Set last close to current price

        return ohlcv

    def _generate_alt_klines(self, symbol: str, timeframe: str, limit: int):
        """Generate altcoin fake data with price continuity"""
        now = int(datetime.now().timestamp() * 1000)

        tf_map = {'1d': 86400000, '1h': 3600000, '15m': 900000}
        tf_ms = tf_map.get(timeframe, 3600000)

        # Use current price for this symbol, ensuring continuity
        latest_price = self.current_prices.get(symbol)
        if latest_price is None:
            # First time - initialize
            self._initialize_prices()
            latest_price = self.current_prices.get(symbol, 20.0)

        # Hash symbol to get consistent behavior per coin
        symbol_hash = abs(hash(symbol)) % 100

        # Determine trend characteristics
        if symbol_hash < 30:  # 30% trending up
            vol_multiplier = 2.5
        elif symbol_hash < 50:  # 20% trending down
            vol_multiplier = 1.5
        else:  # 50% sideways
            vol_multiplier = 1.0

        # Build price history working backwards from current price
        current_price = latest_price
        prices = [current_price]

        for i in range(limit - 1):
            # Work backwards with small random moves
            change_pct = random.uniform(-0.008, 0.005)  # Slight downward bias going back
            current_price = current_price / (1 + change_pct)
            prices.append(current_price)

        # Reverse so oldest is first
        prices.reverse()

        # Build OHLCV candles
        ohlcv = []
        for i in range(limit):
            ts = now - ((limit - i) * tf_ms)
            price = prices[i]

            o = price
            h = price * random.uniform(1.002, 1.015)
            low = price * random.uniform(0.985, 0.998)
            c = price * random.uniform(0.995, 1.005)

            # Volume increases with recency
            recency_factor = 1.0 + (2.0 * i / limit)  # 1.0x to 3.0x
            base_vol = random.uniform(300, 600) * vol_multiplier * recency_factor

            # Occasional volume spikes
            if i >= limit - 10 or random.random() < 0.15:
                v = base_vol * random.uniform(1.5, 3.0)
            else:
                v = base_vol

            ohlcv.append([ts, o, h, low, c, v])

        # Ensure the last candle close matches current price
        if ohlcv:
            ohlcv[-1][4] = latest_price

        return ohlcv

    def get_ticker(self, symbol: str):
        """Generate fake ticker using current price (with caching for continuity)"""
        # Use current price directly (updated every 60s by cache system)
        if symbol not in self.current_prices:
            self._initialize_prices()

        last_price = self.current_prices[symbol]

        return {
            'symbol': symbol,
            'last': last_price,
            'close': last_price,
            'bid': last_price * 0.999,
            'ask': last_price * 1.001,
            'quoteVolume': random.uniform(100000, 500000),  # Above min threshold
            'timestamp': int(time.time() * 1000)
        }

    def get_last_price(self, symbol: str):
        """Get latest price for Fast Stop Manager"""
        ticker = self.get_ticker(symbol)
        return ticker['last'] if ticker else None

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


class RealExchange(BaseExchange):
    """
    Real exchange wrapper for LIVE mode
    Uses actual MEXC via ccxt

    IMPROVEMENTS:
    - Enhanced _with_retries with funding-rate spam suppression
    - Exponential backoff retry strategy
    - Clean error handling without log flooding
    """
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

        if not config.mexc_api_key or not config.mexc_secret_key:
            raise Exception("LIVE mode requires MEXC_API_KEY and MEXC_SECRET_KEY")

        self.client = ccxt.mexc({
            'apiKey': config.mexc_api_key,
            'secret': config.mexc_secret_key,
            'timeout': 5000,  # 5s timeout to prevent scan loop stalling
            'enableRateLimit': True,
        })

        self.logger.info("🌐 RealExchange initialized (LIVE mode with MEXC)")

    def _with_retries(self, func, label: str, max_attempts: int = 2, delay_sec: float = 1.0):
        """
        Retry wrapper for network calls with exponential backoff

        SPAM SUPPRESSION FOR FUNDING RATE ERRORS:
        - If label contains "fetch_funding_rate" or "fetch_funding_rate_history"
          AND the exception contains both "Contract does not exist" AND code 1001:
            - Log exactly one debug line
            - Return None immediately (no retries, no ERROR logs)
        - For all other errors: normal retry behavior with ERROR logging

        Args:
            func: Function to call
            label: Description for logging
            max_attempts: Max retry attempts (default: 2, reduced from 3 to fail-fast)
            delay_sec: Initial delay between retries (default: 1.0s, reduced from 2.0s)

        Returns:
            Result from func(), or None on failure (fail-safe: scan continues)
        """
        for attempt in range(max_attempts):
            try:
                return func()
            except Exception as e:
                error_str = str(e)
                error_repr = repr(e)

                # === FUNDING RATE SPAM SUPPRESSION ===
                # Check if this is a funding rate call with "contract does not exist" error
                is_funding_call = 'fetch_funding_rate' in label.lower()
                # Check for both "Contract does not exist" message and code 1001 (with various JSON formatting)
                has_contract_error_msg = 'Contract does not exist' in error_str or 'Contract does not exist' in error_repr
                has_code_1001 = ('code":1001' in error_repr or 'code": 1001' in error_repr or 'code:1001' in error_repr)
                is_contract_error = has_contract_error_msg and has_code_1001

                if is_funding_call and is_contract_error:
                    # Extract symbol from label if available
                    symbol_part = label.replace('fetch_funding_rate', '').replace('fetch_funding_rate_history', '').strip()
                    self.logger.debug(f"Skipping funding rate for {symbol_part}: contract does not exist on exchange (code 1001)")
                    return None  # Return immediately, no retries, no ERROR logs

                # === NORMAL ERROR HANDLING ===
                # Log error for non-funding-rate calls or different errors
                self.logger.error(f"Error on attempt {attempt + 1}/{max_attempts}: {label} - {error_repr}")

                if attempt < max_attempts - 1:
                    # Exponential backoff: 1s (fail-fast to prevent scan loop stalling)
                    backoff = delay_sec * (2 ** attempt)
                    self.logger.debug(f"Retrying after {backoff:.1f}s...")
                    time.sleep(backoff)

        # Max retries exceeded
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

    def get_last_price(self, symbol: str):
        """Get latest price for Fast Stop Manager"""
        ticker = self.get_ticker(symbol)
        return ticker['last'] if ticker else None

    def get_orderbook(self, symbol: str):
        """Fetch orderbook from MEXC"""
        return self._with_retries(lambda: self.client.fetch_order_book(symbol), f"fetch_orderbook {symbol}")

    def get_funding_rate(self, symbol: str):
        """
        Fetch funding rate from MEXC

        Note: This uses _with_retries which has spam suppression for
        "Contract does not exist" errors (MEXC code 1001).
        Returns 0 if symbol has no futures contract.
        """
        try:
            funding = self._with_retries(
                lambda: self.client.fetch_funding_rate(symbol),
                f"fetch_funding_rate {symbol}"
            )
            if funding:
                return funding.get('fundingRate', 0)
        except Exception as e:
            # This catch is for any errors NOT caught by _with_retries
            self.logger.debug(f"Unexpected error fetching funding rate for {symbol}: {e}")
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
        # Fix: ccxt expects params to be a dict, not None
        if params is None:
            params = {}
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

    def get_total_usdt_balance(self):
        """
        Get total portfolio value in USDT (all assets converted to USDT)
        Returns: float (total portfolio value in USDT)
        """
        try:
            balance = self.fetch_balance()
            if not balance:
                self.logger.error("Failed to fetch balance from MEXC")
                return None

            # Start with USDT balance
            usdt_free = balance.get('USDT', {}).get('free', 0) or 0
            usdt_used = balance.get('USDT', {}).get('used', 0) or 0
            total_value_usdt = usdt_free + usdt_used

            # Convert all other assets to USDT
            asset_values = []
            for asset, asset_balance in balance.items():
                # Skip USDT (already counted), info dict, and assets with zero balance
                if asset == 'USDT' or asset in ['info', 'free', 'used', 'total']:
                    continue

                try:
                    total_amount = asset_balance.get('total', 0) or 0
                    if total_amount <= 0:
                        continue  # Skip zero balances

                    # Get current price of asset in USDT
                    symbol = f"{asset}/USDT"
                    ticker = self.get_ticker(symbol)
                    if ticker:
                        price = ticker.get('last', ticker.get('close', 0)) or 0
                        if price > 0:
                            asset_value_usdt = total_amount * price
                            total_value_usdt += asset_value_usdt
                            asset_values.append(f"{asset}={total_amount:.4f}@${price:.6f}=${asset_value_usdt:.2f}")
                except Exception as e:
                    self.logger.debug(f"Could not convert {asset} to USDT: {e}")
                    continue

            # Log breakdown
            if asset_values:
                breakdown_msg = (
                    f"Portfolio breakdown: USDT=${usdt_free + usdt_used:.2f} | "
                    f"{' | '.join(asset_values)} | Total=${total_value_usdt:.2f}"
                )
                self.logger.info(breakdown_msg)
            else:
                portfolio_msg = (
                    f"MEXC Portfolio: USDT=${usdt_free + usdt_used:.2f} (100%) | "
                    f"Total=${total_value_usdt:.2f}"
                )
                self.logger.debug(portfolio_msg)

            return total_value_usdt

        except Exception as e:
            self.logger.error(f"Error fetching total portfolio value: {e}")
            return None


class DataOnlyMexcExchange(BaseExchange):
    """
    Data-only exchange for SIM mode with LIVE_DATA
    Uses real MEXC market data via public API (no authentication)
    Does NOT place real orders - for paper trading only

    IMPROVEMENTS:
    - Enhanced _with_retries with funding-rate spam suppression
    - Exponential backoff retry strategy
    - Clean error handling without log flooding
    """
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

        # Initialize MEXC client in public mode (no API keys required)
        self.client = ccxt.mexc({
            'timeout': 5000,  # 5s timeout to prevent scan loop stalling
            'enableRateLimit': True,
        })

        self.logger.info("🌐 DataOnlyMexcExchange initialized (REAL MEXC data, PAPER trading only)")

    def _with_retries(self, func, label: str, max_attempts: int = 2, delay_sec: float = 1.0):
        """
        Retry wrapper for network calls with exponential backoff

        SPAM SUPPRESSION FOR FUNDING RATE ERRORS:
        - If label contains "fetch_funding_rate" or "fetch_funding_rate_history"
          AND the exception contains both "Contract does not exist" AND code 1001:
            - Log exactly one debug line
            - Return None immediately (no retries, no ERROR logs)
        - For all other errors: normal retry behavior with ERROR logging

        Args:
            func: Function to call
            label: Description for logging
            max_attempts: Max retry attempts (default: 2, reduced from 3 to fail-fast)
            delay_sec: Initial delay between retries (default: 1.0s, reduced from 2.0s)

        Returns:
            Result from func(), or None on failure (fail-safe: scan continues)
        """
        for attempt in range(max_attempts):
            try:
                return func()
            except Exception as e:
                error_str = str(e)
                error_repr = repr(e)

                # === FUNDING RATE SPAM SUPPRESSION ===
                # Check if this is a funding rate call with "contract does not exist" error
                is_funding_call = 'fetch_funding_rate' in label.lower()
                # Check for both "Contract does not exist" message and code 1001 (with various JSON formatting)
                has_contract_error_msg = 'Contract does not exist' in error_str or 'Contract does not exist' in error_repr
                has_code_1001 = ('code":1001' in error_repr or 'code": 1001' in error_repr or 'code:1001' in error_repr)
                is_contract_error = has_contract_error_msg and has_code_1001

                if is_funding_call and is_contract_error:
                    # Extract symbol from label if available
                    symbol_part = label.replace('fetch_funding_rate', '').replace('fetch_funding_rate_history', '').strip()
                    self.logger.debug(f"Skipping funding rate for {symbol_part}: contract does not exist on exchange (code 1001)")
                    return None  # Return immediately, no retries, no ERROR logs

                # === NORMAL ERROR HANDLING ===
                # Log error for non-funding-rate calls or different errors
                self.logger.error(f"Error on attempt {attempt + 1}/{max_attempts}: {label} - {error_repr}")

                if attempt < max_attempts - 1:
                    # Exponential backoff: 1s (fail-fast to prevent scan loop stalling)
                    backoff = delay_sec * (2 ** attempt)
                    self.logger.debug(f"Retrying after {backoff:.1f}s...")
                    time.sleep(backoff)

        # Max retries exceeded
        self.logger.error(f"Max retries exceeded for: {label}")
        return None

    def get_markets(self):
        """Load markets from MEXC (public endpoint)"""
        return self._with_retries(lambda: self.client.load_markets(), "load_markets")

    def get_klines(self, symbol: str, timeframe: str, limit: int = 200):
        """Fetch OHLCV from MEXC (public endpoint)"""
        return self._with_retries(
            lambda: self.client.fetch_ohlcv(symbol, timeframe, limit=limit),
            f"fetch_ohlcv {symbol} {timeframe}"
        )

    def get_ticker(self, symbol: str):
        """Fetch ticker from MEXC (public endpoint)"""
        return self._with_retries(lambda: self.client.fetch_ticker(symbol), f"fetch_ticker {symbol}")

    def get_last_price(self, symbol: str):
        """Get latest price for Fast Stop Manager"""
        ticker = self.get_ticker(symbol)
        return ticker['last'] if ticker else None

    def get_orderbook(self, symbol: str):
        """Fetch orderbook from MEXC (public endpoint)"""
        return self._with_retries(lambda: self.client.fetch_order_book(symbol), f"fetch_orderbook {symbol}")

    def get_funding_rate(self, symbol: str) -> float:
        """
        Fetch real MEXC futures funding rate (8h) for a given symbol.

        Uses MEXC Contract API: https://contract.mexc.com/api/v1/contract/funding_rate/{symbol}
        API Documentation: https://mxcdevelop.github.io/apidocs/contract_v1_en/#get-contract-funding-rate

        Args:
            symbol: Spot symbol like "BTC/USDT"

        Returns:
            float: 8h funding rate (e.g., 0.0001 = 0.01%), or 0.0 on failure

        Example:
            >>> ex.get_funding_rate("BTC/USDT")
            0.000100  # 0.01% funding rate

        Note: Uses _with_retries which has spam suppression for
        "Contract does not exist" errors (MEXC code 1001).
        """
        try:
            # Convert spot symbol to MEXC contract format
            # "BTC/USDT" -> "BTC_USDT" for MEXC contract API
            contract_symbol = symbol.replace('/', '_')

            # Use MEXC contract API directly (more reliable than CCXT for funding)
            import requests

            url = "https://contract.mexc.com/api/v1/contract/funding_rate/" + contract_symbol

            # Wrap in _with_retries for consistency and spam suppression
            def fetch_funding():
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data and 'data' in data and data['data']:
                        rate = float(data['data'].get('fundingRate', 0))
                        return rate
                    else:
                        return 0.0
                else:
                    # Raise exception to trigger retry logic
                    raise Exception(f"API returned {response.status_code}")

            rate = self._with_retries(fetch_funding, f"fetch_funding_rate {symbol}")
            if rate is not None:
                self.logger.debug(f"[Funding] {symbol} | funding_8h={rate:.6f}")
                return rate
            else:
                return 0.0

        except Exception as e:
            self.logger.debug(f"[Funding] Failed to fetch funding for {symbol}, defaulting to 0.0: {e}")
            return 0.0

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

    # === PAPER TRADING METHODS (No real orders) ===

    def create_order(self, symbol, type, side, amount, price=None, params=None):
        """
        PAPER TRADING: Simulate order (no real execution)
        """
        self.logger.info(f"[PAPER] Order simulated: {side} {amount} {symbol} @ market")
        ticker = self.get_ticker(symbol)
        fill_price = ticker['last'] if ticker else 0

        return {
            'id': f'paper_{int(time.time())}_{random.randint(1000, 9999)}',
            'symbol': symbol,
            'type': type,
            'side': side,
            'amount': amount,
            'price': fill_price,
            'filled': amount,
            'status': 'closed',
            'timestamp': int(time.time() * 1000)
        }

    def fetch_open_positions(self):
        """PAPER TRADING: No real positions"""
        return []

    def cancel_order(self, order_id, symbol=None):
        """PAPER TRADING: Simulate cancel"""
        self.logger.info(f"[PAPER] Order cancel simulated: {order_id}")
        return {'id': order_id, 'status': 'canceled'}

    def fetch_balance(self):
        """PAPER TRADING: Return starting equity as balance"""
        return {
            'USDT': {
                'free': self.config.starting_equity,
                'used': 0,
                'total': self.config.starting_equity
            }
        }


def create_exchange(config, logger):
    """
    Factory to create appropriate exchange based on SIM_MODE and SIM_DATA_SOURCE
    """
    if config.sim_mode:
        if config.sim_data_source == "LIVE_DATA":
            logger.info("📡 SIM_MODE=True | SIM_DATA_SOURCE=LIVE_DATA | Using DataOnlyMexcExchange (REAL MEXC market data, PAPER ONLY)")
            return DataOnlyMexcExchange(config, logger)
        else:
            logger.info("📡 SIM_MODE=True | SIM_DATA_SOURCE=FAKE | Using SimulatedExchange (synthetic data)")
            return SimulatedExchange(config, logger)
    else:
        logger.info("📡 SIM_MODE=False | Using RealExchange (LIVE trading)")
        return RealExchange(config, logger)
