#!/bin/bash
# Performance & Win Rate Checker for Alpha Sniper
# Usage: bash check_performance.sh

echo "=========================================="
echo "  Alpha Sniper Performance Report"
echo "=========================================="
echo ""

DB_PATH="/opt/alpha-sniper/data/alpha_async.db"

if [ ! -f "$DB_PATH" ]; then
    echo "❌ Database not found at: $DB_PATH"
    exit 1
fi

# Check if sqlite3 is available
if ! command -v sqlite3 &> /dev/null; then
    echo "❌ sqlite3 not installed. Install with: sudo apt-get install sqlite3"
    exit 1
fi

echo "📊 OVERALL STATISTICS"
echo "----------------------------------------"

# Total closed trades
TOTAL_TRADES=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM closed_positions;" 2>/dev/null || echo "0")
echo "Total Trades: $TOTAL_TRADES"

if [ "$TOTAL_TRADES" -eq 0 ]; then
    echo ""
    echo "No closed trades yet. Bot is still warming up!"
    echo ""
    echo "Check open positions:"
    OPEN_POS=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM positions WHERE status='open';" 2>/dev/null || echo "0")
    echo "  Currently open: $OPEN_POS positions"
    echo ""
    echo "Recent log activity (last 30 minutes):"
    sudo journalctl -u alpha-sniper-async.service --since "30 minutes ago" --no-pager | grep -E 'OPENED|CLOSED' | tail -5
    exit 0
fi

# Winning trades
WINS=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM closed_positions WHERE pnl_usd > 0;" 2>/dev/null || echo "0")
LOSSES=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM closed_positions WHERE pnl_usd <= 0;" 2>/dev/null || echo "0")

WIN_RATE=$(echo "scale=2; $WINS * 100 / $TOTAL_TRADES" | bc)
echo "Winning Trades: $WINS"
echo "Losing Trades: $LOSSES"
echo "Win Rate: ${WIN_RATE}%"

# Total P&L
TOTAL_PNL=$(sqlite3 "$DB_PATH" "SELECT ROUND(SUM(pnl_usd), 2) FROM closed_positions;" 2>/dev/null || echo "0.00")
echo "Total P&L: \$$TOTAL_PNL"

# Average R-multiple
AVG_R=$(sqlite3 "$DB_PATH" "SELECT ROUND(AVG(r_multiple), 2) FROM closed_positions WHERE r_multiple IS NOT NULL;" 2>/dev/null || echo "0.00")
echo "Average R: ${AVG_R}R"

# Best and worst trades
BEST_TRADE=$(sqlite3 "$DB_PATH" "SELECT symbol, ROUND(pnl_usd, 2), ROUND(pnl_pct, 2) FROM closed_positions ORDER BY pnl_usd DESC LIMIT 1;" 2>/dev/null)
WORST_TRADE=$(sqlite3 "$DB_PATH" "SELECT symbol, ROUND(pnl_usd, 2), ROUND(pnl_pct, 2) FROM closed_positions ORDER BY pnl_usd ASC LIMIT 1;" 2>/dev/null)

if [ -n "$BEST_TRADE" ]; then
    echo ""
    echo "Best Trade: $BEST_TRADE"
    echo "Worst Trade: $WORST_TRADE"
fi

echo ""
echo "📈 RECENT TRADES (Last 10)"
echo "----------------------------------------"

sqlite3 -header -column "$DB_PATH" "
SELECT
    symbol,
    ROUND(entry_price, 6) as entry,
    ROUND(exit_price, 6) as exit,
    ROUND(pnl_usd, 2) as pnl_usd,
    ROUND(pnl_pct, 2) as pnl_pct,
    ROUND(r_multiple, 2) as r_mult,
    exit_reason
FROM closed_positions
ORDER BY exit_time DESC
LIMIT 10;
" 2>/dev/null

echo ""
echo "📊 PERFORMANCE BY REASON"
echo "----------------------------------------"

sqlite3 -header -column "$DB_PATH" "
SELECT
    exit_reason,
    COUNT(*) as count,
    ROUND(AVG(pnl_pct), 2) as avg_pnl_pct,
    ROUND(AVG(r_multiple), 2) as avg_r
FROM closed_positions
GROUP BY exit_reason
ORDER BY count DESC;
" 2>/dev/null

echo ""
echo "🎯 LIVE TEST MODE STATUS"
echo "----------------------------------------"

# Check current day's orders
TODAY=$(date +%Y-%m-%d)
ORDERS_TODAY=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM closed_positions WHERE date(exit_time) = '$TODAY';" 2>/dev/null || echo "0")
echo "Trades Today: $ORDERS_TODAY / 50 (LIVE_TEST limit)"

# Check equity
LATEST_EQUITY=$(sqlite3 "$DB_PATH" "SELECT ROUND(total_equity, 2) FROM equity_snapshots ORDER BY timestamp DESC LIMIT 1;" 2>/dev/null || echo "N/A")
echo "Latest Equity: \$$LATEST_EQUITY"

echo ""
echo "🔍 AUTO-FLIP CRITERIA CHECK"
echo "----------------------------------------"

if [ "$TOTAL_TRADES" -ge 20 ]; then
    echo "✅ Minimum trades: $TOTAL_TRADES / 20"

    # Check win rate
    if (( $(echo "$WIN_RATE >= 55" | bc -l) )); then
        echo "✅ Win rate: ${WIN_RATE}% / 55%"
    else
        echo "❌ Win rate: ${WIN_RATE}% / 55% (need higher)"
    fi

    # Check avg R
    if (( $(echo "$AVG_R >= 0.60" | bc -l) )); then
        echo "✅ Avg R-multiple: ${AVG_R}R / 0.60R"
    else
        echo "❌ Avg R-multiple: ${AVG_R}R / 0.60R (need higher)"
    fi

    echo ""
    if (( $(echo "$WIN_RATE >= 55 && $AVG_R >= 0.60" | bc -l) )); then
        echo "🚀 CRITERIA MET! Bot may auto-flip out of test mode soon."
    else
        echo "⏳ Keep trading in test mode to improve metrics."
    fi
else
    echo "⏳ Need more trades: $TOTAL_TRADES / 20"
    echo "   (collect more data before evaluation)"
fi

echo ""
echo "=========================================="
echo "  Report generated: $(date)"
echo "=========================================="
echo ""

# Offer to show open positions
read -p "Show currently open positions? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "📍 OPEN POSITIONS"
    echo "----------------------------------------"
    sqlite3 -header -column "$DB_PATH" "
    SELECT
        symbol,
        ROUND(entry_price, 6) as entry,
        ROUND(size_usd, 2) as size_usd,
        ROUND(take_profit, 6) as tp,
        ROUND(stop_loss, 6) as sl,
        datetime(entry_time, 'unixepoch') as opened_at
    FROM positions
    WHERE status = 'open'
    ORDER BY entry_time DESC;
    " 2>/dev/null || echo "No open positions"
fi

echo ""
