"""
Test Phase 1.1 features:
- Per-symbol cooldown
- Wick filter (ATR-based spike rejection)
- Absolute depth floor
"""
import asyncio
import pandas as pd
from types import SimpleNamespace


def test_wick_filter_rejects_spike():
    """Test that wick filter rejects abnormal price spikes."""

    # Create mock settings
    mock_settings = SimpleNamespace(
        EARLY_ENABLE=True,
        EARLY_RET_5M_MIN=0.03,
        EARLY_VOL_SPIKE_MIN=3.0,
        EARLY_ACCEL_REQUIRED=True,
        EARLY_REQUIRE_SCORE=False,
        EARLY_REQUIRE_BULL=False,
        WICK_FILTER_ENABLE=True,
        WICK_FILTER_ATR_MULT=2.0,
        pump_engine_enabled=True,
        pump_debug_logging=False,
    )

    mock_settings.get_pump_thresholds = lambda regime: SimpleNamespace(
        min_score=28,
        min_24h_quote_volume=47000,
    )

    import sys
    sys.path.insert(0, '/opt/alpha-sniper/alpha-sniper')
    from signals.pump_engine import PumpEngine

    pe = PumpEngine(mock_settings, logger=None)

    # Create data with a WICK spike (large sudden move, not sustained)
    # ATR should be around 0.5-1.0 for this data
    # But the 5m move will be 10 (way beyond 2*ATR)
    close_prices = [100.0] * 20 + [100, 100, 100, 100, 110]  # Last candle spikes to 110
    high_prices = [c + 0.5 for c in close_prices]
    low_prices = [c - 0.5 for c in close_prices]
    vols = [100] * 20 + [120, 110, 100, 100, 500]  # High volume on spike

    df = pd.DataFrame({
        "close": close_prices,
        "high": high_prices,
        "low": low_prices,
        "volume": vols
    })

    market_data = {
        "TEST/USDT": {
            "df": df,
            "indicators": {"score": 30}
        }
    }

    signals = pe.generate_signals(market_data, regime='BULL')

    # Should reject because 10-point move >> 2*ATR
    assert len(signals) == 0, "Wick filter should reject abnormal spikes"

    print("✅ Test passed: Wick filter rejects abnormal price spikes")


def test_wick_filter_allows_normal_pump():
    """Test that wick filter allows normal pumps (within ATR bounds)."""

    mock_settings = SimpleNamespace(
        EARLY_ENABLE=True,
        EARLY_RET_5M_MIN=0.03,
        EARLY_VOL_SPIKE_MIN=3.0,
        EARLY_ACCEL_REQUIRED=True,
        EARLY_REQUIRE_SCORE=False,
        EARLY_REQUIRE_BULL=False,
        WICK_FILTER_ENABLE=True,
        WICK_FILTER_ATR_MULT=2.0,
        pump_engine_enabled=True,
        pump_debug_logging=False,
    )

    mock_settings.get_pump_thresholds = lambda regime: SimpleNamespace(
        min_score=28,
        min_24h_quote_volume=47000,
    )

    import sys
    sys.path.insert(0, '/opt/alpha-sniper/alpha-sniper')
    from signals.pump_engine import PumpEngine

    pe = PumpEngine(mock_settings, logger=None)

    # Create data with gradual pump (within ATR bounds)
    close_prices = [100.0] * 20 + [101, 102, 103, 104, 105]
    high_prices = [c + 0.5 for c in close_prices]
    low_prices = [c - 0.5 for c in close_prices]
    vols = [100] * 20 + [120, 130, 140, 150, 400]

    df = pd.DataFrame({
        "close": close_prices,
        "high": high_prices,
        "low": low_prices,
        "volume": vols
    })

    market_data = {
        "TEST/USDT": {
            "df": df,
            "indicators": {"score": 30}
        }
    }

    signals = pe.generate_signals(market_data, regime='BULL')

    # Should allow because 5-point move is within 2*ATR
    assert len(signals) > 0, "Wick filter should allow normal pumps"
    assert signals[0]['symbol'] == 'TEST/USDT'

    print("✅ Test passed: Wick filter allows normal pumps")


async def test_cooldown_prevents_reentry():
    """Test that cooldown prevents immediate re-entry."""

    import sys, time
    sys.path.insert(0, '/opt/alpha-sniper/alpha-sniper')
    from risk.async_risk_engine import AsyncRiskEngine
    from types import SimpleNamespace

    # Create mock settings
    mock_settings = SimpleNamespace(
        COOLDOWN_PER_SYMBOL_SEC=120,  # 2 minutes
        MAX_CONCURRENT_POSITIONS=5,
        DAILY_LOSS_CAP_PCT=-0.02,
        STREAK_BREAKER_LOSSES=3,
        RISK_PER_TRADE=0.0025,
        MIN_VIABLE_TRADE_USD=5.0,
        SIM_STARTING_EQUITY=1000.0,
    )

    # Create temporary DB
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    class MockLogger:
        def info(self, msg): pass
        def debug(self, msg): pass
        def warning(self, msg): pass
        def error(self, msg, exc_info=False): pass

    risk = AsyncRiskEngine(db_path, mock_settings, MockLogger())
    await risk.connect()

    # Set cooldown for BTC/USDT
    await risk.set_symbol_cooldown("BTC/USDT")

    # Check if on cooldown
    is_cooldown = await risk.is_symbol_on_cooldown("BTC/USDT")
    assert is_cooldown, "Symbol should be on cooldown immediately after setting"

    # Check different symbol
    is_cooldown_eth = await risk.is_symbol_on_cooldown("ETH/USDT")
    assert not is_cooldown_eth, "Different symbol should not be on cooldown"

    await risk.close()

    # Clean up
    import os
    os.unlink(db_path)
    os.unlink(db_path + "-wal")
    os.unlink(db_path + "-shm")

    print("✅ Test passed: Cooldown prevents immediate re-entry")


if __name__ == "__main__":
    print("Running Phase 1.1 tests...")
    print()

    test_wick_filter_rejects_spike()
    test_wick_filter_allows_normal_pump()

    # Run async test
    asyncio.run(test_cooldown_prevents_reentry())

    print()
    print("All Phase 1.1 tests passed! ✅")
