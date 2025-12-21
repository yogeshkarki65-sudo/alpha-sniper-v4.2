"""
Symbol quarantine system with time-based cooldowns.
Prevents repeated failures on problematic symbols.
"""

import time
from typing import Dict, Optional
from collections import defaultdict
import logging
from .path_manager import get_path_manager
from .order_executor import OrderFailureReason

logger = logging.getLogger(__name__)


class QuarantineManager:
    """
    Manages symbol quarantine/cooldown logic.

    Policy (configurable):
    - 3 failures in 30min → 2h quarantine
    - 3 quarantines in 24h → 24h quarantine
    """

    def __init__(self, config):
        self.config = config
        self.path_manager = get_path_manager()

        # Config with safe defaults
        self.failure_threshold = getattr(config, 'quarantine_failure_threshold', 3)
        self.failure_window_seconds = getattr(config, 'quarantine_failure_window', 1800)  # 30min
        self.initial_quarantine_seconds = getattr(config, 'quarantine_initial_duration', 7200)  # 2h
        self.extended_quarantine_seconds = getattr(config, 'quarantine_extended_duration', 86400)  # 24h
        self.extended_quarantine_threshold = getattr(config, 'quarantine_extended_threshold', 3)

        # Load state
        self.failures = self._load_failures()
        self.quarantines = self._load_quarantines()

    def _load_failures(self) -> Dict:
        """Load failure history from disk."""
        return self.path_manager.read_json('quarantine', 'symbol_failures.json', default={})

    def _load_quarantines(self) -> Dict:
        """Load quarantine state from disk."""
        return self.path_manager.read_json('quarantine', 'quarantine_state.json', default={})

    def _save_failures(self):
        """Persist failure history."""
        self.path_manager.write_json('quarantine', 'symbol_failures.json', self.failures)

    def _save_quarantines(self):
        """Persist quarantine state."""
        self.path_manager.write_json('quarantine', 'quarantine_state.json', self.quarantines)

    def record_failure(self, symbol: str, reason: OrderFailureReason):
        """Record order failure and check if quarantine needed."""
        now = time.time()

        if symbol not in self.failures:
            self.failures[symbol] = {
                'count': 0,
                'reasons': [],
                'first_seen': now,
                'last_seen': now,
                'recent_timestamps': []
            }

        entry = self.failures[symbol]
        entry['count'] += 1
        entry['last_seen'] = now
        entry['recent_timestamps'].append(now)

        if reason.value not in entry['reasons']:
            entry['reasons'].append(reason.value)

        # Clean old timestamps
        cutoff = now - self.failure_window_seconds
        entry['recent_timestamps'] = [
            ts for ts in entry['recent_timestamps'] if ts > cutoff
        ]

        # Check if quarantine needed
        recent_count = len(entry['recent_timestamps'])
        if recent_count >= self.failure_threshold:
            self._apply_quarantine(symbol)

        self._save_failures()

    def record_success(self, symbol: str):
        """Record successful order - may clear quarantine."""
        if symbol in self.quarantines:
            cooldown_until = self.quarantines[symbol].get('cooldown_until', 0)
            if time.time() > cooldown_until:
                # Quarantine expired and successful - clear it
                del self.quarantines[symbol]
                self._save_quarantines()
                logger.info(f"[QUARANTINE_CLEAR] {symbol} successful order after cooldown")

    def _apply_quarantine(self, symbol: str):
        """Apply quarantine to symbol."""
        now = time.time()

        if symbol not in self.quarantines:
            self.quarantines[symbol] = {
                'quarantine_count': 0,
                'first_quarantine': now,
                'cooldown_until': 0
            }

        entry = self.quarantines[symbol]
        entry['quarantine_count'] += 1

        # Determine quarantine duration
        if entry['quarantine_count'] >= self.extended_quarantine_threshold:
            duration = self.extended_quarantine_seconds
            logger.warning(
                f"[QUARANTINE_EXTENDED] {symbol} | "
                f"count={entry['quarantine_count']} | duration=24h"
            )
        else:
            duration = self.initial_quarantine_seconds
            logger.warning(
                f"[QUARANTINE_ACTIVE] {symbol} | "
                f"count={entry['quarantine_count']} | duration=2h"
            )

        entry['cooldown_until'] = now + duration
        self._save_quarantines()

    def is_quarantined(self, symbol: str) -> bool:
        """Check if symbol is currently quarantined."""
        if symbol not in self.quarantines:
            return False

        cooldown_until = self.quarantines[symbol].get('cooldown_until', 0)
        return time.time() < cooldown_until

    def get_quarantine_status(self, symbol: str) -> Optional[Dict]:
        """Get detailed quarantine status for symbol."""
        if not self.is_quarantined(symbol):
            return None

        entry = self.quarantines[symbol]
        return {
            'quarantine_count': entry['quarantine_count'],
            'cooldown_until': entry['cooldown_until'],
            'remaining_seconds': entry['cooldown_until'] - time.time()
        }
