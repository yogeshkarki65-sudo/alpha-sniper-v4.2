#!/usr/bin/env python3
"""
End-to-end health check for alpha-sniper (no trades).
Usage: python scripts/diagnostics.py | tee /tmp/alpha_diag.json
       SEND_TEST_TELEGRAM=1 python scripts/diagnostics.py
"""

import asyncio
import json
import sys
import os
import time
from typing import Dict, Any
from pathlib import Path

# Add alpha-sniper to path (same as app_async.py)
sys.path.insert(0, str(Path(__file__).parent.parent / "alpha-sniper"))

from config.settings import get_settings, Settings
from core.exchange_async import AsyncExchange
from risk.async_risk_engine import AsyncRiskEngine
from signals.pump_engine import PumpEngine

async def check_exchange(settings: Settings) -> Dict[str, Any]:
    """Test exchange connection and fetch capabilities."""
    result = {
        "status": "unknown",
        "error": None,
        "details": {}
    }

    try:
        exchange = AsyncExchange(settings)
        await exchange.initialize()

        # Check balance
        balance = await exchange.fetch_balance()
        quote_balance = balance.get('free', {}).get(settings.UNIVERSE_BASE_QUOTE, 0.0)

        # Check markets
        markets = await exchange.fetch_markets()
        usdt_pairs = [m for m in markets if m.endswith('/USDT')]

        # Check rate limits
        rate_limits = exchange.exchange.rateLimit if hasattr(exchange.exchange, 'rateLimit') else None

        result["status"] = "ok"
        result["details"] = {
            "quote_currency": settings.UNIVERSE_BASE_QUOTE,
            "quote_balance": quote_balance,
            "total_markets": len(markets),
            "usdt_pairs": len(usdt_pairs),
            "rate_limit_ms": rate_limits,
            "exchange_id": exchange.exchange.id if hasattr(exchange.exchange, 'id') else 'unknown'
        }

        await exchange.close()

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["error_type"] = type(e).__name__

    return result

async def check_database(settings: Settings) -> Dict[str, Any]:
    """Test database connection and initialization."""
    result = {
        "status": "unknown",
        "error": None,
        "details": {}
    }

    try:
        risk = AsyncRiskEngine(settings)
        await risk.initialize()

        # Check tables exist
        cursor = await risk.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]

        # Check positions
        cursor = await risk.conn.execute("SELECT COUNT(*) FROM positions")
        pos_count = (await cursor.fetchone())[0]

        # Check symbol_meta
        cursor = await risk.conn.execute("SELECT COUNT(*) FROM symbol_meta")
        meta_count = (await cursor.fetchone())[0]

        # Check daily_counters
        cursor = await risk.conn.execute("SELECT COUNT(*) FROM daily_counters")
        counter_count = (await cursor.fetchone())[0]

        result["status"] = "ok"
        result["details"] = {
            "db_path": settings.DB_PATH,
            "tables": tables,
            "positions_count": pos_count,
            "symbol_meta_count": meta_count,
            "daily_counters_count": counter_count
        }

        await risk.close()

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["error_type"] = type(e).__name__

    return result

async def check_telegram(settings: Settings, send_test: bool = False) -> Dict[str, Any]:
    """Test Telegram connection (optional ping)."""
    result = {
        "status": "unknown",
        "error": None,
        "details": {}
    }

    try:
        if not settings.TELEGRAM_ENABLED:
            result["status"] = "disabled"
            result["details"]["message"] = "Telegram notifications disabled in settings"
            return result

        # Import aiogram
        try:
            from aiogram import Bot
        except ImportError:
            result["status"] = "error"
            result["error"] = "aiogram not installed"
            return result

        bot = Bot(token=settings.TELEGRAM_TOKEN)

        # Get bot info
        bot_info = await bot.get_me()

        result["details"] = {
            "bot_username": bot_info.username,
            "bot_id": bot_info.id,
            "chat_id": settings.TELEGRAM_CHAT_ID
        }

        # Send test message if requested
        if send_test:
            msg = f"🔍 Diagnostics Test\n\nBot: @{bot_info.username}\nTime: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}"
            await bot.send_message(chat_id=settings.TELEGRAM_CHAT_ID, text=msg)
            result["details"]["test_message_sent"] = True

        result["status"] = "ok"
        await bot.session.close()

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["error_type"] = type(e).__name__

    return result

async def check_pump_detector(settings: Settings) -> Dict[str, Any]:
    """Run pump detector in dry-run mode."""
    result = {
        "status": "unknown",
        "error": None,
        "details": {}
    }

    try:
        exchange = AsyncExchange(settings)
        await exchange.initialize()

        pump_engine = PumpEngine(settings)

        # Fetch some markets
        markets = await exchange.fetch_markets()
        usdt_pairs = [m for m in markets if m.endswith('/USDT')][:10]  # Sample 10

        # Fetch OHLCV for sample
        market_data = {}
        for symbol in usdt_pairs:
            try:
                ohlcv = await exchange.fetch_ohlcv(symbol, timeframe='1m', limit=25)
                if len(ohlcv) >= 25:
                    import pandas as pd
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    market_data[symbol] = {
                        'df': df,
                        'indicators': {'score': 50}  # Neutral score
                    }
            except:
                continue

        # Generate signals (dry run)
        signals = pump_engine.generate_signals(market_data, regime='BULL')

        result["status"] = "ok"
        result["details"] = {
            "symbols_scanned": len(market_data),
            "signals_generated": len(signals),
            "wick_filter_enabled": settings.WICK_FILTER_ENABLE,
            "early_ret_5m_min": settings.EARLY_RET_5M_MIN,
            "early_vol_spike_min": settings.EARLY_VOL_SPIKE_MIN
        }

        if len(signals) > 0:
            result["details"]["sample_signal"] = {
                "symbol": signals[0].get('symbol'),
                "ret_5m": signals[0].get('ret_5m'),
                "vol_spike": signals[0].get('vol_spike')
            }

        await exchange.close()

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["error_type"] = type(e).__name__

    return result

def check_rate_budget(settings: Settings, exchange_result: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate rate limit budget safety."""
    result = {
        "status": "unknown",
        "error": None,
        "details": {}
    }

    try:
        # Get exchange rate limit
        rate_limit_ms = exchange_result.get("details", {}).get("rate_limit_ms", 1000)

        # Calculate requests per minute
        requests_per_min = 60000 / rate_limit_ms if rate_limit_ms > 0 else 60

        # Estimate bot usage
        # Assume: 1 scan/10s * (fetch_markets + N * fetch_ohlcv + N/10 * liquidity checks)
        scans_per_min = 6  # 60s / 10s
        symbols_per_scan = settings.MAX_CONCURRENT_POSITIONS * 3  # Scan 3x position limit
        requests_per_scan = 1 + symbols_per_scan + (symbols_per_scan / 10)  # markets + ohlcv + liq
        estimated_usage = scans_per_min * requests_per_scan

        # Calculate safety margin
        usage_pct = (estimated_usage / requests_per_min) * 100 if requests_per_min > 0 else 999

        result["status"] = "ok" if usage_pct < 80 else "warning"
        result["details"] = {
            "rate_limit_ms": rate_limit_ms,
            "requests_per_min_limit": requests_per_min,
            "estimated_requests_per_min": estimated_usage,
            "usage_percentage": round(usage_pct, 1),
            "safety_status": "SAFE" if usage_pct < 50 else "MODERATE" if usage_pct < 80 else "RISKY"
        }

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["error_type"] = type(e).__name__

    return result

async def main():
    """Run all diagnostics."""
    print("🔍 Running alpha-sniper diagnostics...\n", file=sys.stderr)

    # Check if test Telegram is requested
    send_test_telegram = os.getenv('SEND_TEST_TELEGRAM', '0') == '1'

    try:
        # Load settings
        settings = get_settings()

        # Run checks
        print("📡 Checking exchange connection...", file=sys.stderr)
        exchange_result = await check_exchange(settings)

        print("💾 Checking database...", file=sys.stderr)
        db_result = await check_database(settings)

        print("📱 Checking Telegram...", file=sys.stderr)
        telegram_result = await check_telegram(settings, send_test=send_test_telegram)

        print("📊 Checking pump detector...", file=sys.stderr)
        pump_result = await check_pump_detector(settings)

        print("⏱️  Checking rate limit budget...", file=sys.stderr)
        rate_result = check_rate_budget(settings, exchange_result)

        # Compile report
        report = {
            "status": "success",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "checks": {
                "exchange": exchange_result,
                "database": db_result,
                "telegram": telegram_result,
                "pump_detector": pump_result,
                "rate_limit_budget": rate_result
            },
            "summary": {
                "total_checks": 5,
                "passed": sum(1 for r in [exchange_result, db_result, telegram_result, pump_result, rate_result] if r["status"] in ["ok", "disabled"]),
                "warnings": sum(1 for r in [exchange_result, db_result, telegram_result, pump_result, rate_result] if r["status"] == "warning"),
                "failed": sum(1 for r in [exchange_result, db_result, telegram_result, pump_result, rate_result] if r["status"] == "error")
            }
        }

        print(json.dumps(report, indent=2, default=str))

    except Exception as e:
        report = {
            "status": "error",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "error": str(e),
            "error_type": type(e).__name__
        }
        print(json.dumps(report, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
