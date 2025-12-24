"""
Runtime symbol blacklist to prevent repeated API errors.

Automatically blacklists symbols that cause BadSymbol or similar errors,
preventing them from being retried every scan cycle.
"""
import json
import os
import time
from pathlib import Path
from typing import Set, Dict

class SymbolBlacklist:
    """
    Runtime blacklist for symbols causing API errors.

    Features:
    - Automatic blacklisting on BadSymbol errors
    - Persistence across restarts
    - Expiry (optional, for temporary issues)
    """

    def __init__(self, storage_path: str = "/var/lib/alpha-sniper/symbol_blacklist.json"):
        self.storage_path = Path(storage_path)
        self.blacklist: Dict[str, float] = {}  # {symbol: timestamp_added}
        self.expiry_seconds = 86400 * 7  # 7 days (BadSymbol errors are usually permanent)

        # Load existing blacklist
        self._load()

    def _load(self):
        """Load blacklist from disk."""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self.blacklist = data.get('blacklist', {})
        except Exception as e:
            # Silent fail - start with empty blacklist
            pass

    def _save(self):
        """Save blacklist to disk (atomic write)."""
        try:
            # Ensure directory exists
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            # Atomic write
            data = {
                'blacklist': self.blacklist,
                'updated_at': time.time()
            }

            temp_path = self.storage_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            temp_path.replace(self.storage_path)

        except Exception as e:
            # Silent fail - blacklist still works in memory
            pass

    def add(self, symbol: str, reason: str = "BadSymbol"):
        """
        Add symbol to blacklist.

        Args:
            symbol: Symbol to blacklist (e.g., "PEN/USDT")
            reason: Reason for blacklisting (for logging)
        """
        if symbol not in self.blacklist:
            self.blacklist[symbol] = time.time()
            self._save()

    def is_blacklisted(self, symbol: str) -> bool:
        """
        Check if symbol is blacklisted.

        Returns:
            True if blacklisted and not expired, False otherwise
        """
        if symbol not in self.blacklist:
            return False

        # Check expiry
        added_at = self.blacklist[symbol]
        if time.time() - added_at > self.expiry_seconds:
            # Expired, remove from blacklist
            del self.blacklist[symbol]
            self._save()
            return False

        return True

    def remove(self, symbol: str):
        """Remove symbol from blacklist (for manual unblocking)."""
        if symbol in self.blacklist:
            del self.blacklist[symbol]
            self._save()

    def get_blacklisted_symbols(self) -> Set[str]:
        """Get all currently blacklisted symbols."""
        # Clean expired entries
        now = time.time()
        expired = [
            sym for sym, added_at in self.blacklist.items()
            if now - added_at > self.expiry_seconds
        ]

        for sym in expired:
            del self.blacklist[sym]

        if expired:
            self._save()

        return set(self.blacklist.keys())

    def get_stats(self) -> Dict:
        """Get blacklist statistics."""
        return {
            'total_blacklisted': len(self.blacklist),
            'blacklisted_symbols': list(self.blacklist.keys()),
            'storage_path': str(self.storage_path)
        }
