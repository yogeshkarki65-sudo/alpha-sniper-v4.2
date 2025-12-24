"""
Scanner for Alpha Sniper V4.2
- Fetches and filters market universe
- Orchestrates all signal engines
- Returns prioritized signals
"""
from utils import helpers
from signals.long_engine import LongEngine
from signals.short_engine import ShortEngine
from signals.pump_engine import PumpEngine
from signals.bear_micro_long import BearMicroLongEngine


class Scanner:
    """
    Master Scanner
    - Builds tradeable universe
    - Applies global filters
    - Runs all engines
    - Returns ranked signals
    """
    def __init__(self, exchange, risk_engine, config, logger):
        self.exchange = exchange
        self.risk_engine = risk_engine
        self.config = config
        self.logger = logger

        # Initialize engines
        self.long_engine = LongEngine(config, logger)
        self.short_engine = ShortEngine(config, logger)
        self.pump_engine = PumpEngine(config, logger)
        self.bear_micro_engine = BearMicroLongEngine(config, logger)

    def scan(self) -> list:
        """
        Main scan method
        Returns: list of signals
        """
        regime = self.risk_engine.current_regime or "SIDEWAYS"

        self.logger.info("")
        self.logger.info("=" * 50)
        self.logger.info(f"🔍 SCANNER CYCLE START | Regime: {regime}")
        self.logger.info("=" * 50)

        # 1. Get universe of tradeable symbols
        universe = self._build_universe()

        if not universe:
            self.logger.warning("⚠️ No symbols in universe after filtering")
            return []

        self.logger.info(f"📊 Universe: {len(universe)} symbols passed filters")

        # 2. Fetch market data for universe
        market_data = self._fetch_market_data(universe)

        if not market_data:
            self.logger.warning("⚠️ No market data available")
            return []

        self.logger.debug(f"📊 Market data fetched for {len(market_data)} symbols")

        # 3. Run engines (PUMP-ONLY MODE or multi-engine)
        # Wrap engine calls in try/except to prevent crashes from breaking scan loop
        if self.config.pump_only_mode:
            # PUMP-ONLY MODE: Use ONLY the pump engine
            self.logger.info("🎯 PUMP-ONLY MODE: Using pump engine exclusively")
            try:
                pump_signals = self.pump_engine.generate_signals(market_data, regime)
            except Exception as e:
                self.logger.error(f"🔴 Pump engine crashed (non-fatal): {e}")
                self.logger.exception(e)
                pump_signals = []

            all_signals = pump_signals
            long_signals = []
            short_signals = []
            bear_micro_signals = []
        else:
            # NORMAL MODE: Run all engines (each wrapped to prevent cascading failures)
            try:
                long_signals = self.long_engine.generate_signals(market_data, regime)
            except Exception as e:
                self.logger.error(f"🔴 Long engine crashed (non-fatal): {e}")
                self.logger.exception(e)
                long_signals = []

            try:
                short_signals = self.short_engine.generate_signals(market_data, regime)
            except Exception as e:
                self.logger.error(f"🔴 Short engine crashed (non-fatal): {e}")
                self.logger.exception(e)
                short_signals = []

            try:
                pump_signals = self.pump_engine.generate_signals(market_data, regime)
            except Exception as e:
                self.logger.error(f"🔴 Pump engine crashed (non-fatal): {e}")
                self.logger.exception(e)
                pump_signals = []

            try:
                bear_micro_signals = self.bear_micro_engine.generate_signals(market_data, regime)
            except Exception as e:
                self.logger.error(f"🔴 Bear micro engine crashed (non-fatal): {e}")
                self.logger.exception(e)
                bear_micro_signals = []

            # 4. Combine and sort signals by score
            all_signals = long_signals + short_signals + pump_signals + bear_micro_signals

        all_signals.sort(key=lambda x: x.get('score', 0), reverse=True)

        # 5. Log results
        self.logger.info("")
        if self.config.pump_only_mode and self.config.pump_aggressive_mode:
            self.logger.info(
                f"📡 Signals Generated [PUMP-AGGRESSIVE] | "
                f"Pump: {len(pump_signals)} | "
                f"TOTAL: {len(all_signals)}"
            )
        elif self.config.pump_only_mode:
            self.logger.info(
                f"📡 Signals Generated [PUMP-ONLY] | "
                f"Pump: {len(pump_signals)} | "
                f"TOTAL: {len(all_signals)}"
            )
        else:
            self.logger.info(
                f"📡 Signals Generated | "
                f"Long: {len(long_signals)} | Short: {len(short_signals)} | "
                f"Pump: {len(pump_signals)} | BearMicro: {len(bear_micro_signals)} | "
                f"TOTAL: {len(all_signals)}"
            )

        if all_signals:
            top_signal = all_signals[0]
            self.logger.info(
                f"   🎯 Top signal: {top_signal['symbol']} | "
                f"Engine: {top_signal['engine']} | "
                f"Score: {top_signal['score']} | "
                f"Side: {top_signal.get('side', 'N/A')}"
            )
        else:
            self.logger.info("   No signals met criteria")

        self.logger.info("=" * 50)
        self.logger.info("")

        return all_signals

    def _build_universe(self) -> list:
        """
        Build tradeable universe with global filters
        Returns: list of symbol strings
        """
        try:
            # Load markets from exchange
            markets = self.exchange.get_markets()
            if not markets:
                self.logger.error("🔴 Failed to load markets from exchange")
                return []

            universe = []
            rejected_counts = {
                'quote_currency': 0,
                'volume': 0,
                'inactive': 0,
                'blacklisted': 0,
                'total_checked': 0
            }

            for symbol, market in markets.items():
                rejected_counts['total_checked'] += 1

                # Filter: Only USDT pairs
                if not symbol.endswith('/USDT'):
                    rejected_counts['quote_currency'] += 1
                    continue

                # Filter: Active markets only
                if not market.get('active', False):
                    rejected_counts['inactive'] += 1
                    continue

                # Skip if it's a test market or delisted
                if 'BULL' in symbol or 'BEAR' in symbol or '3L' in symbol or '3S' in symbol:
                    rejected_counts['inactive'] += 1
                    continue

                # Skip futures symbols (PERP contracts) - we want spot only
                if '_PERP' in symbol or symbol.endswith('PERP') or ':' in symbol:
                    rejected_counts['inactive'] += 1
                    continue

                # Skip if market type is explicitly 'swap' or 'future' (for SPOT-only mode)
                if self.config.mexc_spot_enabled and not self.config.mexc_futures_enabled:
                    market_type = market.get('type', '').lower()
                    if market_type in ['swap', 'future', 'futures']:
                        rejected_counts['inactive'] += 1
                        continue

                # === BLACKLIST FILTER (symbols causing API errors) ===
                # Check config blacklist
                if symbol in self.config.symbol_blacklist:
                    rejected_counts['blacklisted'] += 1
                    self.logger.debug(f"[BLACKLIST] Skipping {symbol} (in config SYMBOL_BLACKLIST)")
                    continue

                # Check runtime blacklist (BadSymbol errors)
                if hasattr(self.exchange, 'symbol_blacklist') and self.exchange.symbol_blacklist.is_blacklisted(symbol):
                    rejected_counts['blacklisted'] += 1
                    self.logger.debug(f"[BLACKLIST] Skipping {symbol} (in runtime blacklist)")
                    continue

                universe.append(symbol)

            self.logger.debug(
                f"Universe filter stats | "
                f"checked={rejected_counts['total_checked']} "
                f"rejected_quote={rejected_counts['quote_currency']} "
                f"rejected_inactive={rejected_counts['inactive']} "
                f"rejected_blacklisted={rejected_counts['blacklisted']} "
                f"passed={len(universe)}"
            )

            # Limit universe size for SIM mode to avoid rate limits
            if self.config.sim_mode and len(universe) > 50:
                self.logger.debug(f"SIM mode: limiting universe to top 50 by volume")
                # In real implementation, you'd sort by volume here
                # For now, just take first 50
                universe = universe[:50]

            return universe

        except Exception as e:
            self.logger.error(f"🔴 Error building universe: {e}")
            return []

    def _fetch_market_data(self, universe: list) -> dict:
        """
        Fetch market data for all symbols in universe
        Returns: dict {symbol -> {ticker, df_15m, df_1h, ...}}
        """
        market_data = {}
        fetch_errors = 0
        rejected_volume = 0
        rejected_spread = 0

        for symbol in universe:
            try:
                # Fetch ticker
                ticker = self.exchange.get_ticker(symbol)
                if not ticker:
                    fetch_errors += 1
                    continue

                # Volume filter
                volume_24h = ticker.get('quoteVolume', 0)
                if volume_24h < self.config.min_24h_quote_volume:
                    rejected_volume += 1
                    continue

                # Spread filter
                bid = ticker.get('bid', 0)
                ask = ticker.get('ask', 0)
                spread_pct = helpers.calculate_spread_pct(bid, ask)

                if spread_pct > self.config.max_spread_pct:
                    rejected_spread += 1
                    continue

                # Fetch OHLCV data
                ohlcv_15m = self.exchange.get_klines(symbol, '15m', limit=100)
                ohlcv_1h = self.exchange.get_klines(symbol, '1h', limit=100)

                if not ohlcv_15m or not ohlcv_1h:
                    fetch_errors += 1
                    continue

                # Convert to dataframes
                df_15m = helpers.ohlcv_to_dataframe(ohlcv_15m)
                df_1h = helpers.ohlcv_to_dataframe(ohlcv_1h)

                # Fetch real funding rate ONLY for futures symbols (for short engine)
                # Skip for spot symbols to prevent "contract does not exist" spam
                funding_rate = 0
                if '_PERP' in symbol or symbol.endswith('PERP') or ':' in symbol:
                    # This is a futures contract, fetch funding rate
                    funding_rate = self.exchange.get_funding_rate(symbol)

                # Store data
                market_data[symbol] = {
                    'ticker': ticker,
                    'df_15m': df_15m,
                    'df_1h': df_1h,
                    'spread_pct': spread_pct,
                    'volume_24h': volume_24h,
                    'funding_rate': funding_rate,
                    'btc_performance': 0  # TODO: Calculate relative to BTC
                }

            except Exception as e:
                self.logger.debug(f"Error fetching data for {symbol}: {e}")
                fetch_errors += 1
                continue

        self.logger.info(
            f"📊 Market data: {len(market_data)} symbols fetched | "
            f"rejected: volume={rejected_volume} spread={rejected_spread} errors={fetch_errors}"
        )

        return market_data
