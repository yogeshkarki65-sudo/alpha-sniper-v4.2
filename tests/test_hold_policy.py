"""
Test Dynamic Hold Brain:
- Promote winners (extend deadline)
- Demote losers (expire early)
- Trailing stops
- Hard cap
"""
import time
from types import SimpleNamespace


def test_promote_extends_deadline():
    """Test that winning positions get deadline extended."""

    import sys
    sys.path.insert(0, '/opt/alpha-sniper/alpha-sniper')
    from signals.hold_policy import should_promote, update_position_with_hold_brain

    # Create mock settings
    mock_settings = SimpleNamespace(
        HOLD_BRAIN_ENABLE=True,
        HOLD_BRAIN_PROMOTE_R_MIN=2.5,
        HOLD_BRAIN_PROMOTE_RVOL_MIN=1.5,
        HOLD_BRAIN_PROMOTE_EMA_SLOPE_MIN=0.0,
        HOLD_BRAIN_PROMOTE_EXTEND_MIN=10,
    )

    # Create winning position at +3R
    now = int(time.time())
    position = {
        'symbol': 'BTC/USDT',
        'entry_price': 100.0,
        'stop_loss': 99.0,
        'side': 'long',
        'timestamp_open': now - 60,  # 1 minute ago to avoid demote
        'deadline_ts': now + 300,  # 5 min deadline
        'promoted_count': 0,
    }

    current_price = 103.0  # +3R (3 points gain / 1 point risk)

    # Should promote (no market data, but R is high enough)
    result = should_promote(position, current_price, None, mock_settings)
    assert result, "Should promote position at +3R"

    # Test full update (make a copy to compare)
    original_deadline = position['deadline_ts']
    updated_pos, action = update_position_with_hold_brain(
        position.copy(), current_price, None, mock_settings
    )

    assert action == "PROMOTED", f"Action should be PROMOTED, got {action}"
    assert updated_pos['promoted_count'] == 1, "Promoted count should increment"
    assert updated_pos['deadline_ts'] > original_deadline, f"Deadline {updated_pos['deadline_ts']} should be > {original_deadline}"

    print("✅ Test passed: Winning positions get promoted")


def test_demote_closes_losers():
    """Test that flat/negative positions get demoted."""

    import sys
    sys.path.insert(0, '/opt/alpha-sniper/alpha-sniper')
    from signals.hold_policy import should_demote, update_position_with_hold_brain

    mock_settings = SimpleNamespace(
        HOLD_BRAIN_ENABLE=True,
        HOLD_BRAIN_DEMOTE_FLAT_MIN=2,  # 2 minutes
    )

    # Create position that's been flat for 3 minutes
    position = {
        'symbol': 'ETH/USDT',
        'entry_price': 100.0,
        'stop_loss': 99.0,
        'side': 'long',
        'timestamp_open': int(time.time()) - 180,  # 3 minutes ago
    }

    current_price = 100.1  # Only +0.1R (basically flat)

    result = should_demote(position, current_price, mock_settings)
    assert result, "Should demote flat position after 2+ minutes"

    # Test full update
    updated_pos, action = update_position_with_hold_brain(
        position, current_price, None, mock_settings
    )

    assert action == "DEMOTED", "Action should be DEMOTED"

    print("✅ Test passed: Flat/negative positions get demoted")


def test_trailing_stop_activates():
    """Test that trailing stop activates at threshold."""

    import sys
    sys.path.insert(0, '/opt/alpha-sniper/alpha-sniper')
    from signals.hold_policy import calculate_trailing_stop, update_position_with_hold_brain

    mock_settings = SimpleNamespace(
        HOLD_BRAIN_ENABLE=True,
        HOLD_BRAIN_TRAILING_STOP_R_TRIGGER=1.5,  # Activate at 1.5R
        HOLD_BRAIN_TRAILING_STOP_PCT=0.02,  # 2% trail
        HOLD_BRAIN_PROMOTE_R_MIN=10.0,  # High to prevent promotion
    )

    now = int(time.time())
    position = {
        'symbol': 'SOL/USDT',
        'entry_price': 100.0,
        'stop_loss': 98.0,  # 2 point risk
        'side': 'long',
        'peak_price': None,
        'timestamp_open': now - 60,  # 1 minute ago
        'deadline_ts': now + 300,  # 5 min deadline
        'promoted_count': 0,
    }

    current_price = 105.0  # +2.5R (5 point gain / 2 point risk)

    # Should activate trailing stop
    new_stop = calculate_trailing_stop(position, current_price, position.get('peak_price'), mock_settings)
    assert new_stop is not None, "Trailing stop should activate at +2.5R"
    assert new_stop > position['stop_loss'], f"New stop {new_stop} should be > original {position['stop_loss']}"

    # Test full update (make a copy)
    original_stop = position['stop_loss']
    updated_pos, action = update_position_with_hold_brain(
        position.copy(), current_price, None, mock_settings
    )

    assert action == "TRAILING_STOP", f"Action should be TRAILING_STOP, got {action}"
    assert updated_pos['peak_price'] == current_price, "Peak price should be set"
    assert updated_pos['stop_loss'] > original_stop, f"Stop {updated_pos['stop_loss']} should be > original {original_stop}"

    print("✅ Test passed: Trailing stop activates correctly")


def test_hard_cap_expires():
    """Test that positions expire after hard cap."""

    import sys
    sys.path.insert(0, '/opt/alpha-sniper/alpha-sniper')
    from signals.hold_policy import check_hard_cap_exceeded, update_position_with_hold_brain

    mock_settings = SimpleNamespace(
        HOLD_BRAIN_ENABLE=True,
        HOLD_BRAIN_MAX_HOLD_HOURS=8.0,
    )

    # Position opened 9 hours ago
    position = {
        'symbol': 'XRP/USDT',
        'entry_price': 100.0,
        'stop_loss': 99.0,
        'side': 'long',
        'timestamp_open': int(time.time()) - (9 * 3600),  # 9 hours ago
    }

    current_price = 102.0

    # Should exceed hard cap
    exceeded = check_hard_cap_exceeded(position, mock_settings)
    assert exceeded, "Should exceed hard cap after 9 hours (max 8h)"

    # Test full update
    updated_pos, action = update_position_with_hold_brain(
        position, current_price, None, mock_settings
    )

    assert action == "HARD_CAP", "Action should be HARD_CAP"

    print("✅ Test passed: Hard cap expires old positions")


def test_r_multiple_calculation():
    """Test R-multiple calculation."""

    import sys
    sys.path.insert(0, '/opt/alpha-sniper/alpha-sniper')
    from signals.hold_policy import calculate_r_multiple

    # Long position at +2R
    position = {
        'entry_price': 100.0,
        'stop_loss': 98.0,  # 2 point risk
        'side': 'long',
    }

    current_price = 104.0  # 4 point gain
    r_mult = calculate_r_multiple(position, current_price)
    assert abs(r_mult - 2.0) < 0.01, f"R-multiple should be 2.0, got {r_mult}"

    # Long position at -1R
    current_price = 97.0  # 3 point loss (1.5R loss)
    r_mult = calculate_r_multiple(position, current_price)
    assert r_mult < 0, "R-multiple should be negative for loss"
    assert abs(r_mult - (-1.5)) < 0.01, f"R-multiple should be -1.5, got {r_mult}"

    print("✅ Test passed: R-multiple calculation correct")


if __name__ == "__main__":
    print("Running Dynamic Hold Brain tests...")
    print()

    test_r_multiple_calculation()
    test_promote_extends_deadline()
    test_demote_closes_losers()
    test_trailing_stop_activates()
    test_hard_cap_expires()

    print()
    print("All Hold Brain tests passed! ✅")
