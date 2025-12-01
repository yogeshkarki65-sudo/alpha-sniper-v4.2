"""
Pump Trailer - ATR-based trailing stop for pump positions
"""

import time
from utils import helpers


class PumpTrailer:
    """ATR-based trailing stop manager for pump positions"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def update(self, position, current_price: float, atr_15m: float) -> bool:
        """Update trailing stop for a pump position"""
        if position.get('engine') != 'pump':
            return False

        time_in_position = time.time() - position.get('timestamp_open', time.time())
        time_in_minutes = time_in_position / 60

        if time_in_minutes < self.config.pump_trail_start_minutes:
            return False

        current_stop = position.get('stop_loss', 0)
        trail_distance = atr_15m * self.config.pump_trail_atr_mult
        new_stop = current_price - trail_distance

        if new_stop > current_stop:
            old_stop = current_stop
            position['stop_loss'] = new_stop

            entry_price = position.get('entry_price', current_price)
            profit_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
            stop_buffer_pct = ((new_stop - entry_price) / entry_price) * 100 if entry_price > 0 else 0

            self.logger.info(
                f"[PumpTrailer] Trail updated | "
                f"symbol={position.get('symbol')} | "
                f"old_stop={old_stop:.6f} → new_stop={new_stop:.6f} | "
                f"current_price={current_price:.6f} | "
                f"profit={profit_pct:.1f}% | "
                f"buffer={stop_buffer_pct:.1f}%"
            )
            return True

        return False

    def should_trail(self, position) -> bool:
        """Check if position is eligible for trailing"""
        if position.get('engine') != 'pump':
            return False

        time_in_position = time.time() - position.get('timestamp_open', time.time())
        time_in_minutes = time_in_position / 60

        return time_in_minutes >= self.config.pump_trail_start_minutes
