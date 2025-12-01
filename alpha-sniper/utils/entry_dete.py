"""
Entry-DETE (Dynamic Entry Timing Engine) v1

WHY THIS EXISTS:
Instead of entering positions immediately when a signal is generated,
Entry-DETE queues the signal and waits for micro-confirmation:
- Slight dip for better entry (0.5-2%)
- Volume re-engagement
- Liquidity/spread sanity
- Momentum still intact

This is NOT "perfect entry" wizardry. It's a simple, robust filter that:
- Improves average entry prices slightly
- Discards signals that don't confirm quickly
- Works cleanly with existing DFE, FSM, and Exit-DETE

Design Philosophy:
- Simple, cheap micro-triggers (no deep order book modeling)
- Uses existing exchange APIs (ticker, klines, liquidity)
- Runs in POSITION LOOP (15s) alongside FSM
- Clear timeout mechanism (120-180s)
- No complex state machines
"""

import time
from datetime import datetime, timezone


class EntryDETEngine:
    """
    Smart entry timing engine that queues signals and confirms them
    using lightweight micro-triggers before opening positions.
    """

    def __init__(self, config, logger, exchange, risk_engine):
        self.config = config
        self.logger = logger
        self.exchange = exchange
        self.risk_engine = risk_engine

        # In-memory queue of pending signals
        self.pending_signals = []

        self.logger.info("🎯 Entry-DETE v1 initialized")
        self.logger.info(f"   Enabled: {config.entry_dete_enabled}")
        if config.entry_dete_enabled:
            self.logger.info(f"   Max wait: {config.entry_dete_max_wait_seconds}s")
            self.logger.info(f"   Min triggers: {config.entry_dete_min_triggers}")
            self.logger.info(f"   Dip range: {config.entry_dete_min_dip_pct*100:.1f}% - {config.entry_dete_max_dip_pct*100:.1f}%")
            self.logger.info(f"   Volume multiplier: {config.entry_dete_volume_multiplier}x")

    def queue_signal(self, signal):
        """
        Queue a signal for micro-confirmation instead of opening immediately.

        Args:
            signal: Signal dict from scanner with keys:
                - symbol, side, engine, score, entry_price, regime, etc.
        """
        if not self.config.entry_dete_enabled:
            # Entry-DETE disabled, this shouldn't be called
            self.logger.warning("[Entry-DETE] Called but disabled - this is a bug!")
            return

        # Create pending entry object
        pending = {
            'symbol': signal['symbol'],
            'side': signal['side'],
            'engine': signal.get('engine', 'unknown'),
            'score': signal.get('score', 0),
            'regime': signal.get('regime', 'UNKNOWN'),
            'baseline_price': signal.get('entry_price', 0),
            'created_at': time.time(),
            'max_wait_seconds': self.config.entry_dete_max_wait_seconds,
            'raw_signal': signal  # Keep full signal for later
        }

        self.pending_signals.append(pending)

        self.logger.info(
            f"[Entry-DETE] QUEUED | symbol={signal['symbol']} | "
            f"side={signal['side']} | engine={signal.get('engine')} | "
            f"score={signal.get('score')} | baseline={pending['baseline_price']:.6f}"
        )

    def process_pending(self):
        """
        Process all pending signals using micro-triggers.
        Called from POSITION LOOP every 15s.

        For each pending signal:
        1. Check if expired (timeout)
        2. Evaluate micro-triggers
        3. If confirmed -> open position
        4. If expired -> drop
        """
        if not self.config.entry_dete_enabled:
            return

        if not self.pending_signals:
            return  # Nothing to process

        now = time.time()
        confirmed = []
        expired = []
        still_waiting = []

        for pending in self.pending_signals:
            symbol = pending['symbol']
            side = pending['side']
            baseline_price = pending['baseline_price']
            waited_seconds = now - pending['created_at']

            # Check timeout
            if waited_seconds >= pending['max_wait_seconds']:
                expired.append(pending)
                self.logger.info(
                    f"[Entry-DETE] DROP | symbol={symbol} | reason=timeout | "
                    f"waited={waited_seconds:.0f}s | baseline={baseline_price:.6f}"
                )
                continue

            # Evaluate micro-triggers
            try:
                triggers = self._evaluate_micro_triggers(pending, now)
                trigger_count = sum(triggers.values())

                if trigger_count >= self.config.entry_dete_min_triggers:
                    # Confirmed! Open position now
                    confirmed.append(pending)

                    # Get current price for entry
                    current_price = self.exchange.get_last_price(symbol)
                    if not current_price:
                        self.logger.warning(f"[Entry-DETE] No price for {symbol}, keeping in queue")
                        still_waiting.append(pending)
                        continue

                    # Calculate dip percentage (for logging)
                    if side == 'long':
                        dip_pct = ((baseline_price - current_price) / baseline_price) * 100
                    else:
                        dip_pct = ((current_price - baseline_price) / baseline_price) * 100

                    # Log confirmation with trigger details
                    trigger_names = [name for name, value in triggers.items() if value]
                    self.logger.info(
                        f"[Entry-DETE] CONFIRM | symbol={symbol} | side={side} | "
                        f"triggers={'+'.join(trigger_names)} ({trigger_count}) | "
                        f"dip={dip_pct:+.2f}% | waited={waited_seconds:.0f}s | "
                        f"entry={current_price:.6f} vs baseline={baseline_price:.6f}"
                    )

                    # Open position via risk engine
                    self._open_position_from_pending(pending, current_price)

                else:
                    # Not enough triggers yet, keep waiting
                    still_waiting.append(pending)

            except Exception as e:
                self.logger.error(f"[Entry-DETE] Error evaluating {symbol}: {e}")
                still_waiting.append(pending)  # Keep in queue, try again next cycle

        # Update pending list (remove confirmed and expired)
        self.pending_signals = still_waiting

    def _evaluate_micro_triggers(self, pending, now):
        """
        Evaluate micro-triggers for a pending signal.

        Returns:
            dict of boolean triggers: {
                'dip_ok': bool,
                'volume_ok': bool,
                'liquidity_ok': bool,
                'momentum_ok': bool
            }
        """
        symbol = pending['symbol']
        side = pending['side']
        baseline_price = pending['baseline_price']

        triggers = {
            'dip_ok': False,
            'volume_ok': False,
            'liquidity_ok': False,
            'momentum_ok': False
        }

        # Get current price
        current_price = self.exchange.get_last_price(symbol)
        if not current_price or current_price == 0:
            return triggers

        # 1. DIP CONFIRMATION
        if side == 'long':
            # For longs, want a small pullback (dip) from baseline
            dip_pct = (baseline_price - current_price) / baseline_price
            if self.config.entry_dete_min_dip_pct <= dip_pct <= self.config.entry_dete_max_dip_pct:
                triggers['dip_ok'] = True
        else:
            # For shorts, want a small bounce above baseline
            dip_pct = (current_price - baseline_price) / baseline_price
            if self.config.entry_dete_min_dip_pct <= dip_pct <= self.config.entry_dete_max_dip_pct:
                triggers['dip_ok'] = True

        # 2. VOLUME RE-ENGAGEMENT
        try:
            # Get recent 1m candles (last 5-10 for volume check)
            klines = self.exchange.get_klines(symbol, '1m', limit=10)
            if klines and len(klines) >= 5:
                # Extract volumes
                volumes = [candle[5] for candle in klines[-5:]]  # Last 5 candles
                avg_volume = sum(volumes) / len(volumes)
                current_volume = volumes[-1]

                # Check if current volume is above threshold
                if current_volume >= avg_volume * self.config.entry_dete_volume_multiplier:
                    triggers['volume_ok'] = True
        except Exception as e:
            self.logger.debug(f"[Entry-DETE] Volume check failed for {symbol}: {e}")
            # Don't fail the whole evaluation, just skip this trigger

        # 3. LIQUIDITY & SPREAD SANITY
        try:
            # Reuse existing liquidity metrics
            liquidity = self.exchange.get_liquidity_metrics(symbol)
            if liquidity:
                spread_pct = liquidity.get('spread_pct', 999)
                depth_usd = liquidity.get('depth_usd', 0)

                # Check spread
                spread_ok = spread_pct <= self.config.max_spread_pct

                # Check depth (use a fraction of the "good level")
                depth_ok = depth_usd >= self.config.liquidity_depth_good_level * 0.5

                if spread_ok and depth_ok:
                    triggers['liquidity_ok'] = True
        except Exception as e:
            self.logger.debug(f"[Entry-DETE] Liquidity check failed for {symbol}: {e}")

        # 4. MOMENTUM NOT DEAD
        try:
            # Simple check: current price should be near recent candle range
            klines = self.exchange.get_klines(symbol, '1m', limit=5)
            if klines and len(klines) >= 3:
                recent_closes = [candle[4] for candle in klines[-3:]]
                min_close = min(recent_closes)

                if side == 'long':
                    # For longs, price should not be making lower lows
                    if current_price >= min_close * 0.998:  # Within 0.2% of recent low
                        triggers['momentum_ok'] = True
                else:
                    # For shorts, price should not be making higher highs
                    max_close = max(recent_closes)
                    if current_price <= max_close * 1.002:
                        triggers['momentum_ok'] = True
        except Exception as e:
            self.logger.debug(f"[Entry-DETE] Momentum check failed for {symbol}: {e}")

        return triggers

    def _open_position_from_pending(self, pending, entry_price):
        """
        Open a position from a confirmed pending signal.

        Args:
            pending: Pending signal dict
            entry_price: Confirmed entry price
        """
        # Reconstruct signal with confirmed entry price
        signal = pending['raw_signal'].copy()
        signal['entry_price'] = entry_price

        # Call risk engine to open position
        # This follows the same path as regular signals
        try:
            position = self.risk_engine.open_position(signal)
            if position:
                self.logger.info(
                    f"[Entry-DETE] Position opened | symbol={signal['symbol']} | "
                    f"side={signal['side']} | entry={entry_price:.6f}"
                )
            else:
                self.logger.warning(
                    f"[Entry-DETE] Failed to open position for {signal['symbol']} "
                    f"(risk engine rejected)"
                )
        except Exception as e:
            self.logger.error(f"[Entry-DETE] Error opening position: {e}")

    def get_pending_count(self):
        """Return count of pending signals (for monitoring)"""
        return len(self.pending_signals)

    def clear_pending(self):
        """Clear all pending signals (for emergency use)"""
        count = len(self.pending_signals)
        self.pending_signals = []
        self.logger.warning(f"[Entry-DETE] Cleared {count} pending signals")
        return count
