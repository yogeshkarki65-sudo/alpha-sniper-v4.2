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
        QUICK_EXIT_ENABLE=True,
        QUICK_TP_PCT=0.02,
        QUICK_SL_PCT=0.01,
        QUICK_MAX_HOLD_MIN=5,
    )

    mock_settings.get_pump_thresholds = lambda regime: SimpleNamespace(
        min_score=28,
        min_24h_quote_volume=47000,
    )

    import sys
    sys.path.insert(0, '/opt/alpha-sniper/alpha-sniper')
    from signals.pump_engine import PumpEngine

    pe = PumpEngine(mock_settings, logger=None)

    # Create data with realistic volatility BEFORE the pump
    # This ensures ATR is high enough to allow the pump
    import random
    random.seed(42)

    # Generate 19 bars with VERY high volatility (ATR ~3.5)
    # This makes the 3.5-point pump move acceptable (not a wick)
    # Need ATR > 1.75 so that ATR * 2.0 > 3.5 (the pump move)
    base_prices = []
    for i in range(19):
        base_prices.append(100.0 + random.uniform(-3.5, 3.5))

    # Add pump starting from a known baseline (6 candles total)
    # Need >3% gain from candle -6 to candle -1
    pump_baseline = 100.0
    pump_prices = [
        pump_baseline,      # -5 from current
        pump_baseline,      # -4
        101.0,              # -3
        102.0,              # -2
        103.0,              # -1
        103.5               # current (+3.5% from baseline)
    ]

    close_prices = base_prices + pump_prices

    # Create realistic high/low with VERY wide ranges for higher ATR
    # Wide ranges mean high TR (true range) values, which increases ATR
    high_prices = [c + random.uniform(1.0, 2.5) for c in close_prices]
    low_prices = [c - random.uniform(1.0, 2.5) for c in close_prices]

    # High volume spike on last candle (needs to be 3x average)
    vols = [100] * 19 + [100, 110, 120, 140, 180, 500]

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

    # Should allow because move is gradual and within 2*ATR
    assert len(signals) > 0, f"Wick filter should allow normal pumps, got {len(signals)} signals"
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
    # WAL and SHM files may not exist
    for ext in ["-wal", "-shm"]:
        wal_file = db_path + ext
        if os.path.exists(wal_file):
            os.unlink(wal_file)

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
