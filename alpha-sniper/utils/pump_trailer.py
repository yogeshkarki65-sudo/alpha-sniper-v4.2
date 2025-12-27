"""
Pump Trailer - ATR-based trailing stop for pump positions

WHY THIS EXISTS:
Pump trades need dynamic trailing stops that lock in profits as the pump continues.
This utility implements an ATR-based trailing stop that:
- Waits 30 minutes before activating (let the pump establish)
- Trails the stop using ATR(14) as the distance metric
- Only raises the stop, never lowers it
- Integrates with Fast Stop Manager's 15s position loop
"""

import time


class PumpTrailer:
    """
    ATR-based trailing stop manager for pump positions

    Usage:
        trailer = PumpTrailer(config, logger)
        trailer.update(position, current_price, atr_15m)
    """

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def update(self, position, current_price: float, atr_15m: float) -> bool:
        """
        Update trailing stop for a pump position

        Args:
            position: Position object with stop_loss, timestamp_open, etc.
            current_price: Current market price
            atr_15m: ATR(14) value from 15m timeframe

        Returns:
            bool: True if stop was updated, False otherwise
        """
        # Only trail pump positions
        if position.get('engine') != 'pump':
            return False

        # Check if trailing should start (after initial wait period)
        time_in_position = time.time() - position.get('timestamp_open', time.time())
        time_in_minutes = time_in_position / 60

        if time_in_minutes < self.config.pump_trail_start_minutes:
            # Too early to trail - let the pump establish first
            return False

        # Get current stop
        current_stop = position.get('stop_loss', 0)

        # Calculate new trailing stop
        trail_distance = atr_15m * self.config.pump_trail_atr_mult
        new_stop = current_price - trail_distance

        # Only raise the stop (never lower)
        if new_stop > current_stop:
            old_stop = current_stop
            position['stop_loss'] = new_stop

            # Calculate profit protection
            entry_price = position.get('entry_price', current_price)
            profit_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
            stop_buffer_pct = ((new_stop - entry_price) / entry_price) * 100 if entry_price > 0 else 0

            self.logger.info(
                f"[PumpTrailer] Trail updated | "
                f"symbol={position.get('symbol')} | "
                f"old_stop={old_stop:.6f} → new_stop={new_stop:.6f} | "
                f"current_price={current_price:.6f} | "
                f"profit={profit_pct:.1f}% | "
                f"buffer={stop_buffer_pct:.1f}% | "
                f"trail_atr={trail_distance:.6f}"
            )

            return True

        return False

    def should_trail(self, position) -> bool:
        """
        Check if a position is eligible for trailing

        Args:
            position: Position object

        Returns:
            bool: True if position should be trailed
        """
        # Only pump positions
        if position.get('engine') != 'pump':
            return False

        # Check time in position
        time_in_position = time.time() - position.get('timestamp_open', time.time())
        time_in_minutes = time_in_position / 60

        return time_in_minutes >= self.config.pump_trail_start_minutes

    def get_initial_stop(self, entry_price: float, atr_15m: float) -> float:
        """
        Calculate initial stop for a new pump position

        Args:
            entry_price: Entry price
            atr_15m: ATR(14) value from 15m timeframe

        Returns:
            float: Initial stop loss price
        """
        initial_stop_distance = atr_15m * self.config.pump_trail_initial_atr_mult
        initial_stop = entry_price - initial_stop_distance

        return initial_stop
