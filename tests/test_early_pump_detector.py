"""
Test early pump detector logic
"""
import pandas as pd
from types import SimpleNamespace


def test_early_detector_5m_ret_and_volume():
    """Test that early detector fires on 5-minute momentum + volume spike."""

    # Create mock settings
    mock_settings = SimpleNamespace(
        EARLY_ENABLE=True,
        EARLY_RET_5M_MIN=0.03,
        EARLY_VOL_SPIKE_MIN=3.0,
        EARLY_ACCEL_REQUIRED=True,
        EARLY_REQUIRE_SCORE=False,
        EARLY_REQUIRE_BULL=False,
        QUICK_EXIT_ENABLE=True,
        QUICK_SL_PCT=0.01,
        QUICK_TP_PCT=0.02,
        QUICK_MAX_HOLD_MIN=5,
        pump_engine_enabled=True,
        pump_debug_logging=False,
    )

    # Mock get_pump_thresholds
    mock_settings.get_pump_thresholds = lambda regime: SimpleNamespace(
        min_score=28,
        min_24h_quote_volume=47000,
    )

    # Import pump engine
    import sys
    sys.path.insert(0, '/opt/alpha-sniper/alpha-sniper')
    from signals.pump_engine import PumpEngine

    pe = PumpEngine(mock_settings, logger=None)

    # Create synthetic data: flat then jump in last 5 bars
    prices = [100.0] * 20 + [101, 102, 103, 104, 105]
    vols = [100] * 20 + [120, 110, 100, 100, 400]  # Last candle 4x volume spike

    df = pd.DataFrame({"close": prices, "volume": vols})

    # Market data
    market_data = {
        "TEST/USDT": {
            "df": df,
            "indicators": {"score": 30}
        }
    }

    # Generate signals
    signals = pe.generate_signals(market_data, regime='BULL')

    # Assertions
    assert len(signals) > 0, "Should generate at least one signal"
    assert signals[0]['symbol'] == 'TEST/USDT', "Should match test symbol"
    assert signals[0]['engine'] == 'pump_early', "Should be marked as pump_early"
    assert signals[0]['max_hold_hours'] < 1.0, "Should have quick exit (< 1 hour)"

    print("✅ Test passed: Early detector fires on 5-min momentum + volume spike")


if __name__ == "__main__":
    test_early_detector_5m_ret_and_volume()
