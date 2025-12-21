"""
Scratch exit logic - detect thesis failure early.

Exits positions that show no follow-through within a time budget.
Mode-aware with structure checks to avoid scratching valid consolidations.
"""

import time
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ScratchExitManager:
    """
    Detects early thesis failure and exits before significant loss.

    Uses:
    - Time budget (first 30-120s depending on mode)
    - PnL velocity
    - MFE/MAE thresholds
    - Structure checks (avoid scratching valid consolidation)
    """

    def __init__(self, config):
        self.config = config

        # Mode-specific timeouts (seconds)
        self.timeouts = {
            'HARVEST': getattr(config, 'scratch_timeout_harvest', 30),
            'GRIND': getattr(config, 'scratch_timeout_grind', 60),
            'DEFENSE': getattr(config, 'scratch_timeout_defense', 20),
            'OBSERVE': getattr(config, 'scratch_timeout_observe', 60)
        }

        # Thresholds
        self.min_mfe_required_pct = getattr(config, 'scratch_min_mfe_pct', 0.3)  # 0.3%
        self.max_adverse_allowed_pct = getattr(config, 'scratch_max_mae_pct', -0.5)  # -0.5%

    def should_scratch(
        self,
        position: dict,
        current_price: float,
        current_mode: str,
        elapsed_seconds: float
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if position should be scratched.

        Returns: (should_scratch, reason)
        """

        # Get mode-specific timeout
        timeout = self.timeouts.get(current_mode, 60)

        # Only check within the time budget
        if elapsed_seconds > timeout:
            return False, None  # Outside scratch window

        entry_price = position.get('entry_price', 0)
        if entry_price == 0:
            return False, None

        side = position.get('side', 'long')

        # Calculate current PnL
        if side == 'long':
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:
            pnl_pct = ((entry_price - current_price) / entry_price) * 100

        # Get MFE/MAE from position tracking
        mfe = position.get('max_favorable_pct', 0)
        mae = position.get('max_adverse_pct', 0)

        # Update MFE/MAE
        if pnl_pct > mfe:
            position['max_favorable_pct'] = pnl_pct
            mfe = pnl_pct
        if pnl_pct < mae:
            position['max_adverse_pct'] = pnl_pct
            mae = pnl_pct

        # Scratch conditions

        # 1. Significant adverse move without recovery
        if mae < self.max_adverse_allowed_pct and pnl_pct < 0:
            return True, f"scratch_adverse_mae={mae:.2f}%"

        # 2. No favorable excursion despite time elapsed
        if elapsed_seconds > (timeout * 0.5):  # Halfway through budget
            if mfe < self.min_mfe_required_pct:
                # Check for consolidation (valid structure)
                if self._is_consolidating(position, pnl_pct, mfe, mae):
                    return False, None  # Valid consolidation, don't scratch

                return True, f"scratch_no_follow_through_mfe={mfe:.2f}%_time={elapsed_seconds:.0f}s"

        # 3. Velocity check - price moving against us
        if elapsed_seconds > 10:  # Minimum time for velocity
            velocity = pnl_pct / elapsed_seconds  # %/second

            # Strong negative velocity in first minute
            if elapsed_seconds < 60 and velocity < -0.01:  # -0.01%/s = -0.6%/min
                return True, f"scratch_negative_velocity={velocity:.4f}"

        return False, None

    def _is_consolidating(
        self,
        position: dict,
        current_pnl_pct: float,
        mfe: float,
        mae: float
    ) -> bool:
        """
        Check if position is in valid consolidation (don't scratch).

        Valid consolidation:
        - Small range (MFE - MAE < 1%)
        - Holding near entry (current PnL between -0.2% and +0.2%)
        """
        range_pct = mfe - mae

        if range_pct < 1.0 and -0.2 < current_pnl_pct < 0.2:
            return True  # Tight consolidation near entry

        return False
