"""
Runtime Settings Overlay for Alpha Sniper v4.2

Provides mutable overlay on top of immutable Pydantic Settings with JSON persistence.
Allows runtime threshold adjustments without restart.
"""

import json
import os
import threading
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class RuntimeSettings:
    """
    Overlay for Settings with persistence to JSON.

    - Updates underlying settings object so existing code sees new values
    - Persists to disk at specified path
    - Thread-safe for concurrent access
    """

    def __init__(self, settings, path: str = "./data/overrides.json", log: Optional[logging.Logger] = None):
        """
        Initialize runtime settings overlay.

        Args:
            settings: Pydantic Settings object to overlay
            path: JSON file path for persistence
            log: Optional logger instance
        """
        self._s = settings
        self._path = path
        self._lock = threading.Lock()
        self._ovr: Dict[str, Any] = {}
        self._logger = log or logger

        # Ensure data directory exists
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)

    def load(self):
        """Load overrides from JSON file and apply to settings object."""
        with self._lock:
            if not os.path.exists(self._path):
                return

            try:
                with open(self._path, "r") as f:
                    self._ovr = json.load(f) or {}

                # Apply each override to the underlying settings object
                for k, v in self._ovr.items():
                    if hasattr(self._s, k):
                        setattr(self._s, k, v)

                if self._logger:
                    self._logger.info(f"[RUNTIME_CFG] Loaded {len(self._ovr)} overrides from {self._path}")

            except Exception as e:
                if self._logger:
                    self._logger.error(f"[RUNTIME_CFG] Load failed: {e}")

    def _save_nolock(self):
        """Save overrides to JSON file (internal, no lock)."""
        with open(self._path, "w") as f:
            json.dump(self._ovr, f, indent=2, sort_keys=True)

    def set(self, key: str, val: Any):
        """
        Set a runtime override.

        Args:
            key: Setting key to override
            val: New value

        Raises:
            AttributeError: If key doesn't exist in settings
        """
        with self._lock:
            if not hasattr(self._s, key):
                raise AttributeError(f"Unknown setting: {key}")

            # Update both the settings object and our override dict
            setattr(self._s, key, val)
            self._ovr[key] = val
            self._save_nolock()

            if self._logger:
                self._logger.info(f"[RUNTIME_CFG] Set {key}={val}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value (override or original).

        Args:
            key: Setting key
            default: Default value if key not found

        Returns:
            Setting value
        """
        with self._lock:
            if key in self._ovr:
                return self._ovr[key]
            return getattr(self._s, key, default)

    def reset(self, *keys: str) -> int:
        """
        Reset overrides to original values.

        Args:
            *keys: Keys to reset (if empty, reset all)

        Returns:
            Number of keys reset
        """
        with self._lock:
            changed = 0

            if not keys:
                # Reset all
                self._ovr = {}
                self._save_nolock()
                if self._logger:
                    self._logger.info("[RUNTIME_CFG] Reset all overrides")
                return 0

            # Reset specific keys
            for k in keys:
                if k in self._ovr:
                    self._ovr.pop(k)
                    changed += 1

            self._save_nolock()

            if self._logger and changed > 0:
                self._logger.info(f"[RUNTIME_CFG] Reset {changed} override(s)")

            return changed

    def dump(self) -> Dict[str, Any]:
        """
        Get all current overrides.

        Returns:
            Dict of current overrides
        """
        with self._lock:
            return dict(self._ovr)
