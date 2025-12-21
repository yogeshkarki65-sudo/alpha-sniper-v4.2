"""
Decision Layer (DDL) - Adaptive session-based mode selection.

Decides:
1. Can we trade right now? (allowed_to_trade)
2. What mode should we use? (HARVEST/GRIND/DEFENSE/OBSERVE)
3. What parameter overrides? (risk %, thresholds, etc.)
"""

import time
from typing import Dict, Any, Optional, Tuple
from enum import Enum
from collections import deque
import logging
from .path_manager import get_path_manager

logger = logging.getLogger(__name__)


class DDLMode(Enum):
    """Trading modes with distinct behavior."""
    HARVEST = "HARVEST"      # Aggressive momentum extraction
    GRIND = "GRIND"          # Tight risk, choppy markets
    DEFENSE = "DEFENSE"      # Capital preservation
    OBSERVE = "OBSERVE"      # Paper trading only


class OpportunityDensity:
    """
    Measures current market opportunity quality.

    Inputs:
    - Signal count and quality
    - Entry acceptance rate
    - Early follow-through (MFE in first minutes)
    - Win rate and profit factor
    """

    def __init__(self, window_seconds: int = 7200):  # 2 hours
        self.window_seconds = window_seconds

        # Rolling metrics
        self.signals = deque(maxlen=100)
        self.entries = deque(maxlen=50)
        self.closes = deque(maxlen=50)

    def record_signal(self, timestamp: float, score: float, accepted: bool):
        """Record signal generation."""
        self.signals.append({
            'timestamp': timestamp,
            'score': score,
            'accepted': accepted
        })

    def record_entry(self, timestamp: float, symbol: str, score: float):
        """Record position entry."""
        self.entries.append({
            'timestamp': timestamp,
            'symbol': symbol,
            'score': score,
            'entry_time': timestamp
        })

    def record_close(
        self,
        timestamp: float,
        symbol: str,
        entry_time: float,
        pnl_pct: float,
        exit_reason: str,
        max_favorable: float,
        max_adverse: float
    ):
        """Record position close."""
        self.closes.append({
            'timestamp': timestamp,
            'symbol': symbol,
            'entry_time': entry_time,
            'hold_seconds': timestamp - entry_time,
            'pnl_pct': pnl_pct,
            'exit_reason': exit_reason,
            'mfe': max_favorable,
            'mae': max_adverse,
            'green_within_60s': max_favorable > 0.5 and (timestamp - entry_time) < 60
        })

    def calculate_density(self) -> float:
        """
        Calculate opportunity density score [0.0 - 1.0].

        High density = good market conditions
        Low density = poor conditions
        """
        now = time.time()
        cutoff = now - self.window_seconds

        # Filter to window
        recent_signals = [s for s in self.signals if s['timestamp'] > cutoff]
        recent_closes = [c for c in self.closes if c['timestamp'] > cutoff]

        if not recent_signals or not recent_closes:
            return 0.5  # Neutral on insufficient data

        # Component 1: Signal quality and acceptance rate
        avg_score = sum(s['score'] for s in recent_signals) / len(recent_signals)
        acceptance_rate = sum(1 for s in recent_signals if s['accepted']) / len(recent_signals)
        signal_component = (avg_score * acceptance_rate) * 0.3

        # Component 2: Early follow-through (green within 60s)
        quick_wins = sum(1 for c in recent_closes if c.get('green_within_60s', False))
        quick_win_rate = quick_wins / len(recent_closes)
        follow_through_component = quick_win_rate * 0.3

        # Component 3: Win rate
        winners = sum(1 for c in recent_closes if c['pnl_pct'] > 0)
        win_rate = winners / len(recent_closes)
        win_component = win_rate * 0.2

        # Component 4: Profit factor proxy
        total_wins = sum(c['pnl_pct'] for c in recent_closes if c['pnl_pct'] > 0)
        total_losses = abs(sum(c['pnl_pct'] for c in recent_closes if c['pnl_pct'] < 0))
        profit_factor = total_wins / total_losses if total_losses > 0 else 1.0
        pf_component = min(profit_factor / 2.0, 1.0) * 0.2

        density = signal_component + follow_through_component + win_component + pf_component
        return max(0.0, min(1.0, density))


class DDL:
    """
    Decision Layer for adaptive mode selection.

    Uses opportunity density + hysteresis to switch modes safely.
    """

    def __init__(self, config):
        self.config = config
        self.path_manager = get_path_manager()

        # Config with safe defaults
        self.update_interval = getattr(config, 'ddl_update_interval_seconds', 300)  # 5min
        self.min_time_in_mode = getattr(config, 'ddl_min_time_in_mode_seconds', 900)  # 15min

        # Mode thresholds (density required to enter mode)
        self.thresholds = {
            'harvest_entry': getattr(config, 'ddl_harvest_threshold', 0.70),
            'harvest_exit': getattr(config, 'ddl_harvest_exit_threshold', 0.55),  # Hysteresis
            'grind_entry': getattr(config, 'ddl_grind_threshold', 0.40),
            'grind_exit': getattr(config, 'ddl_grind_exit_threshold', 0.30),
            'defense_threshold': getattr(config, 'ddl_defense_threshold', 0.25),
        }

        # State
        self.current_mode = DDLMode.GRIND  # Conservative start
        self.mode_entered_at = time.time()
        self.last_update = time.time()
        self.confidence = 0.5

        # Metrics
        self.opportunity_density = OpportunityDensity(
            window_seconds=getattr(config, 'ddl_density_window_seconds', 7200)
        )

        # Load persisted state
        self._load_state()

    def _load_state(self):
        """Load DDL state from disk."""
        state = self.path_manager.read_json('metrics', 'ddl_state.json', default={})
        if state:
            try:
                self.current_mode = DDLMode(state.get('mode', 'GRIND'))
                self.mode_entered_at = state.get('mode_entered_at', time.time())
                self.confidence = state.get('confidence', 0.5)
            except (ValueError, KeyError):
                pass

    def _save_state(self):
        """Persist DDL state."""
        state = {
            'mode': self.current_mode.value,
            'mode_entered_at': self.mode_entered_at,
            'confidence': self.confidence,
            'last_update': time.time()
        }
        self.path_manager.write_json('metrics', 'ddl_state.json', state)

    def update(self) -> bool:
        """
        Periodic update check - reevaluate mode.
        Returns True if mode changed.
        """
        now = time.time()

        if now - self.last_update < self.update_interval:
            return False  # Too soon

        self.last_update = now

        # Calculate current density
        density = self.opportunity_density.calculate_density()

        # Check if we can switch modes (respect min time in mode)
        time_in_mode = now - self.mode_entered_at
        can_switch = time_in_mode >= self.min_time_in_mode

        if not can_switch:
            return False

        # Mode selection logic with hysteresis
        new_mode = self._select_mode(density)

        if new_mode != self.current_mode:
            logger.info(
                f"[DDL_MODE_CHANGE] {self.current_mode.value} → {new_mode.value} | "
                f"density={density:.2f} | time_in_mode={time_in_mode/60:.1f}min"
            )
            self.current_mode = new_mode
            self.mode_entered_at = now
            self._save_state()
            return True

        return False

    def _select_mode(self, density: float) -> DDLMode:
        """Select mode based on density and hysteresis."""

        # Defense mode (very low density)
        if density < self.thresholds['defense_threshold']:
            return DDLMode.DEFENSE

        # Current mode influences threshold (hysteresis)
        if self.current_mode == DDLMode.HARVEST:
            # Harder to exit HARVEST (avoid thrashing)
            if density >= self.thresholds['harvest_exit']:
                return DDLMode.HARVEST
            elif density >= self.thresholds['grind_entry']:
                return DDLMode.GRIND
            else:
                return DDLMode.DEFENSE

        elif self.current_mode == DDLMode.GRIND:
            if density >= self.thresholds['harvest_entry']:
                return DDLMode.HARVEST
            elif density >= self.thresholds['grind_exit']:
                return DDLMode.GRIND
            else:
                return DDLMode.DEFENSE

        else:  # DEFENSE or OBSERVE
            # Require clear signal to exit defensive mode
            if density >= self.thresholds['harvest_entry']:
                return DDLMode.HARVEST
            elif density >= self.thresholds['grind_entry']:
                return DDLMode.GRIND
            else:
                return DDLMode.DEFENSE

    def get_decision(self) -> Dict[str, Any]:
        """
        Get current trading decision.

        Returns:
        {
            'mode': DDLMode,
            'allowed_to_trade': bool,
            'confidence': float,
            'param_overrides': dict
        }
        """
        mode = self.current_mode
        density = self.opportunity_density.calculate_density()

        # OBSERVE mode = paper trading only
        allowed_to_trade = mode != DDLMode.OBSERVE

        # Mode-specific parameter overrides
        param_overrides = self._get_mode_params(mode)

        return {
            'mode': mode,
            'allowed_to_trade': allowed_to_trade,
            'confidence': density,
            'density': density,
            'param_overrides': param_overrides
        }

    def _get_mode_params(self, mode: DDLMode) -> Dict[str, Any]:
        """Get parameter overrides for mode."""

        if mode == DDLMode.HARVEST:
            return {
                'position_size_multiplier': 1.2,
                'min_score_multiplier': 0.9,  # Lower threshold
                'max_concurrent_positions': 3,
                'max_hold_hours': 12,
                'scratch_timeout_seconds': 30,
                'trailing_activation_pct': 0.03  # Activate earlier
            }

        elif mode == DDLMode.GRIND:
            return {
                'position_size_multiplier': 1.0,
                'min_score_multiplier': 1.0,
                'max_concurrent_positions': 2,
                'max_hold_hours': 24,
                'scratch_timeout_seconds': 60,
                'trailing_activation_pct': 0.05
            }

        elif mode == DDLMode.DEFENSE:
            return {
                'position_size_multiplier': 0.5,  # Half size
                'min_score_multiplier': 1.2,  # Higher threshold
                'max_concurrent_positions': 1,
                'max_hold_hours': 6,
                'scratch_timeout_seconds': 20,  # Quick scratch
                'trailing_activation_pct': 0.02
            }

        else:  # OBSERVE
            return {
                'position_size_multiplier': 0.0,  # No real trades
                'simulate': True
            }

    def record_signal(self, timestamp: float, score: float, accepted: bool):
        """Record signal for density calculation."""
        self.opportunity_density.record_signal(timestamp, score, accepted)

    def record_entry(self, timestamp: float, symbol: str, score: float):
        """Record entry for density calculation."""
        self.opportunity_density.record_entry(timestamp, symbol, score)

    def record_close(
        self,
        timestamp: float,
        symbol: str,
        entry_time: float,
        pnl_pct: float,
        exit_reason: str,
        max_favorable: float,
        max_adverse: float
    ):
        """Record close for density calculation."""
        self.opportunity_density.record_close(
            timestamp, symbol, entry_time, pnl_pct, exit_reason,
            max_favorable, max_adverse
        )
