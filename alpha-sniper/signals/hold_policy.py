"""
Dynamic Hold Policy (Hold Brain)

Implements intelligent position management with:
- Promote winners (extend deadline)
- Demote losers (expire early)
- Trailing stops based on R-multiple
- EMA slope analysis
"""

import time
from typing import Dict, Any, Optional, Tuple


def calculate_r_multiple(
    position: Dict[str, Any],
    current_price: float
) -> float:
    """
    Calculate current R-multiple for position.

    Args:
        position: Position dict with entry_price, stop_loss, side
        current_price: Current market price

    Returns:
        R-multiple (positive for winners, negative for losers)
    """
    entry = position.get('entry_price', 0)
    stop = position.get('stop_loss', 0)
    side = position.get('side', 'long')

    risk_per_unit = abs(entry - stop)
    if risk_per_unit <= 0:
        return 0.0

    if side == 'long':
        unrealized_pnl = current_price - entry
    else:
        unrealized_pnl = entry - current_price

    return unrealized_pnl / risk_per_unit


def calculate_ema_slope(close_prices: list, period: int = 9) -> float:
    """
    Calculate EMA slope (simple approximation).

    Args:
        close_prices: List of recent close prices
        period: EMA period

    Returns:
        EMA slope (positive = rising, negative = falling)
    """
    if len(close_prices) < period + 1:
        return 0.0

    # Simple EMA calculation
    multiplier = 2.0 / (period + 1)
    ema_values = []

    # Initialize with SMA
    ema = sum(close_prices[:period]) / period
    ema_values.append(ema)

    # Calculate EMA for remaining values
    for price in close_prices[period:]:
        ema = (price - ema) * multiplier + ema
        ema_values.append(ema)

    # Slope = difference between last two EMA values
    if len(ema_values) >= 2:
        return ema_values[-1] - ema_values[-2]

    return 0.0


def calculate_rvol(volume_data: list, lookback: int = 20) -> float:
    """
    Calculate relative volume (current vs average).

    Args:
        volume_data: List of recent volume values
        lookback: Lookback period for average

    Returns:
        RVOL (e.g., 1.5 = 50% above average)
    """
    if not volume_data or len(volume_data) < 2:
        return 1.0

    current_vol = volume_data[-1]
    avg_vol = sum(volume_data[-lookback:]) / min(len(volume_data), lookback)

    if avg_vol <= 0:
        return 1.0

    return current_vol / avg_vol


def should_promote(
    position: Dict[str, Any],
    current_price: float,
    market_data: Optional[Dict[str, Any]],
    settings
) -> bool:
    """
    Check if position should be promoted (deadline extended).

    Criteria:
    - R >= HOLD_BRAIN_PROMOTE_R_MIN (default 2.5R)
    - RVOL >= HOLD_BRAIN_PROMOTE_RVOL_MIN (default 1.5)
    - EMA slope >= HOLD_BRAIN_PROMOTE_EMA_SLOPE_MIN (default 0.0)

    Args:
        position: Position dict
        current_price: Current market price
        market_data: Market data dict with df, indicators
        settings: Settings object

    Returns:
        True if should promote, False otherwise
    """
    if not getattr(settings, 'HOLD_BRAIN_ENABLE', True):
        return False

    # Calculate R-multiple
    r_mult = calculate_r_multiple(position, current_price)

    # Check R threshold
    r_min = getattr(settings, 'HOLD_BRAIN_PROMOTE_R_MIN', 2.5)
    if r_mult < r_min:
        return False

    # Check RVOL if market data available
    if market_data:
        df = market_data.get('df')
        if df is not None and len(df) >= 20:
            vol_col = 'volume' if 'volume' in df.columns else ('v' if 'v' in df.columns else None)
            if vol_col:
                volume_data = df[vol_col].tolist()
                rvol = calculate_rvol(volume_data)

                rvol_min = getattr(settings, 'HOLD_BRAIN_PROMOTE_RVOL_MIN', 1.5)
                if rvol < rvol_min:
                    return False

        # Check EMA slope
        if df is not None and len(df) >= 10:
            close_col = 'close' if 'close' in df.columns else ('c' if 'c' in df.columns else None)
            if close_col:
                close_prices = df[close_col].tolist()
                ema_slope = calculate_ema_slope(close_prices, period=9)

                ema_min = getattr(settings, 'HOLD_BRAIN_PROMOTE_EMA_SLOPE_MIN', 0.0)
                if ema_slope < ema_min:
                    return False

    # All criteria met
    return True


def should_demote(
    position: Dict[str, Any],
    current_price: float,
    settings
) -> bool:
    """
    Check if position should be demoted (expired early).

    Criteria:
    - Position flat or negative for HOLD_BRAIN_DEMOTE_FLAT_MIN minutes

    Args:
        position: Position dict
        current_price: Current market price
        settings: Settings object

    Returns:
        True if should demote, False otherwise
    """
    if not getattr(settings, 'HOLD_BRAIN_ENABLE', True):
        return False

    # Calculate R-multiple
    r_mult = calculate_r_multiple(position, current_price)

    # If position is winning, don't demote
    if r_mult >= 0.5:  # Small buffer
        return False

    # Check how long position has been flat/negative
    timestamp_open = position.get('timestamp_open', time.time())
    age_minutes = (time.time() - timestamp_open) / 60.0

    flat_min = getattr(settings, 'HOLD_BRAIN_DEMOTE_FLAT_MIN', 2)

    # Demote if been flat/negative for enough time
    if age_minutes >= flat_min and r_mult < 0.5:
        return True

    return False


def calculate_trailing_stop(
    position: Dict[str, Any],
    current_price: float,
    peak_price: Optional[float],
    settings
) -> Optional[float]:
    """
    Calculate trailing stop price if applicable.

    Activates after HOLD_BRAIN_TRAILING_STOP_R_TRIGGER (default 1.5R)
    Trails by HOLD_BRAIN_TRAILING_STOP_PCT (default 2%)

    Args:
        position: Position dict
        current_price: Current market price
        peak_price: Peak price since entry (None if not tracking)
        settings: Settings object

    Returns:
        New stop-loss price, or None if trailing not active
    """
    if not getattr(settings, 'HOLD_BRAIN_ENABLE', True):
        return None

    # Calculate R-multiple
    r_mult = calculate_r_multiple(position, current_price)

    # Check if trailing should activate
    r_trigger = getattr(settings, 'HOLD_BRAIN_TRAILING_STOP_R_TRIGGER', 1.5)
    if r_mult < r_trigger:
        return None

    # Update peak price
    if peak_price is None:
        peak_price = current_price
    else:
        peak_price = max(peak_price, current_price)

    # Calculate trailing stop
    trail_pct = getattr(settings, 'HOLD_BRAIN_TRAILING_STOP_PCT', 0.02)
    side = position.get('side', 'long')

    if side == 'long':
        new_stop = peak_price * (1.0 - trail_pct)
    else:
        new_stop = peak_price * (1.0 + trail_pct)

    # Only move stop in favorable direction
    current_stop = position.get('stop_loss', 0)
    if side == 'long':
        return max(new_stop, current_stop)
    else:
        return min(new_stop, current_stop)


def check_hard_cap_exceeded(
    position: Dict[str, Any],
    settings
) -> bool:
    """
    Check if position has exceeded hard cap hold time.

    Args:
        position: Position dict
        settings: Settings object

    Returns:
        True if hard cap exceeded, False otherwise
    """
    if not getattr(settings, 'HOLD_BRAIN_ENABLE', True):
        return False

    timestamp_open = position.get('timestamp_open', time.time())
    age_hours = (time.time() - timestamp_open) / 3600.0

    max_hold_hours = getattr(settings, 'HOLD_BRAIN_MAX_HOLD_HOURS', 8.0)

    return age_hours >= max_hold_hours


def update_position_with_hold_brain(
    position: Dict[str, Any],
    current_price: float,
    market_data: Optional[Dict[str, Any]],
    settings
) -> Tuple[Dict[str, Any], str]:
    """
    Update position based on hold brain logic.

    Returns updated position dict and action taken.

    Args:
        position: Position dict
        current_price: Current market price
        market_data: Market data dict (optional)
        settings: Settings object

    Returns:
        (updated_position, action) where action is one of:
        - "PROMOTED" - deadline extended
        - "DEMOTED" - should close early
        - "TRAILING_STOP" - trailing stop updated
        - "HARD_CAP" - hard cap exceeded
        - "NONE" - no action
    """
    if not getattr(settings, 'HOLD_BRAIN_ENABLE', True):
        return position, "NONE"

    # Check hard cap first
    if check_hard_cap_exceeded(position, settings):
        return position, "HARD_CAP"

    # Check for demotion
    if should_demote(position, current_price, settings):
        return position, "DEMOTED"

    # Check for promotion
    if should_promote(position, current_price, market_data, settings):
        # Extend deadline
        extend_min = getattr(settings, 'HOLD_BRAIN_PROMOTE_EXTEND_MIN', 10)
        current_deadline = position.get('deadline_ts', int(time.time()))
        new_deadline = int(time.time()) + (extend_min * 60)

        # Only extend if new deadline is later
        if new_deadline > current_deadline:
            position['deadline_ts'] = new_deadline
            promoted_count = position.get('promoted_count', 0)
            position['promoted_count'] = promoted_count + 1
            return position, "PROMOTED"

    # Check trailing stop
    peak_price = position.get('peak_price')
    new_stop = calculate_trailing_stop(position, current_price, peak_price, settings)

    if new_stop is not None:
        # Update peak price
        if peak_price is None:
            position['peak_price'] = current_price
        else:
            position['peak_price'] = max(peak_price, current_price)

        # Update stop if it moved
        if new_stop != position.get('stop_loss'):
            position['stop_loss'] = new_stop
            return position, "TRAILING_STOP"

    return position, "NONE"
