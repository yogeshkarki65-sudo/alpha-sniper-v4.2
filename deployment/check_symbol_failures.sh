#!/bin/bash
# ============================================================================
# Check Symbol Failures - Review Auto-Tracked API Failures
# ============================================================================

FAILURE_LOG="/var/lib/alpha-sniper/symbol_failures.json"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "        SYMBOL FAILURE REPORT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [[ ! -f "$FAILURE_LOG" ]]; then
    echo "✅ No symbol failures detected yet"
    echo ""
    echo "The bot will automatically track symbols that fail to create orders."
    echo "After 3+ failures, it will recommend blacklisting."
    exit 0
fi

echo "Symbols with repeated order creation failures:"
echo ""

# Parse and display failures
cat "$FAILURE_LOG" | jq -r '
to_entries[] |
select(.value.count >= 1) |
"\(.key): \(.value.count) failures | Reasons: \(.value.reasons | join(", "))"
' | while read -r line; do
    count=$(echo "$line" | grep -oP '\d+(?= failures)')

    if [[ $count -ge 3 ]]; then
        echo "❌ $line [RECOMMEND BLACKLIST]"
    else
        echo "⚠️  $line"
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "RECOMMENDATIONS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Get symbols with 3+ failures
PROBLEM_SYMBOLS=$(cat "$FAILURE_LOG" | jq -r 'to_entries[] | select(.value.count >= 3) | .key' | tr '\n' ',' | sed 's/,$//')

if [[ -n "$PROBLEM_SYMBOLS" ]]; then
    echo "The following symbols should be blacklisted:"
    echo "$PROBLEM_SYMBOLS"
    echo ""
    echo "To blacklist automatically:"
    echo "  1. Edit /etc/alpha-sniper/alpha-sniper-live.env"
    echo "  2. Update SYMBOL_BLACKLIST line:"
    echo "     SYMBOL_BLACKLIST=$PROBLEM_SYMBOLS"
    echo "  3. Restart: sudo systemctl restart alpha-sniper-live.service"
    echo ""
    echo "Or use the automated script:"
    echo "  sudo ./deployment/fix_symbol_errors.sh"
else
    echo "✅ No symbols currently need blacklisting"
    echo ""
    echo "All failures are below the 3-failure threshold."
    echo "The bot will continue monitoring automatically."
fi

echo ""
echo "To clear failure history:"
echo "  sudo rm $FAILURE_LOG"
echo ""
