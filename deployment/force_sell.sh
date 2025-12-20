#!/bin/bash
# ============================================================================
# Force Sell METIS/USDT and CKB/USDT Positions
# Uses Python script with MEXC API to close positions
# ============================================================================

set -e

VENV_PATH="/opt/alpha-sniper/venv"
SCRIPT_PATH="/opt/alpha-sniper/deployment/force_sell_positions.py"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "        FORCE SELL PROBLEMATIC POSITIONS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This will attempt to sell METIS/USDT and CKB/USDT using MEXC API"
echo ""

# Check if virtual environment exists
if [[ ! -d "$VENV_PATH" ]]; then
    echo "❌ Virtual environment not found at: $VENV_PATH"
    echo "Using system Python instead..."
    PYTHON_CMD="python3"
else
    PYTHON_CMD="$VENV_PATH/bin/python"
fi

# Check if script exists
if [[ ! -f "$SCRIPT_PATH" ]]; then
    echo "❌ Script not found at: $SCRIPT_PATH"
    echo "Make sure you've pulled the latest code from git"
    exit 1
fi

# Run the Python script
echo "🚀 Executing force sell script..."
echo ""

sudo -E "$PYTHON_CMD" "$SCRIPT_PATH"

EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    echo ""
    echo "✅ Script completed successfully"
else
    echo ""
    echo "❌ Script exited with code $EXIT_CODE"
    echo ""
    echo "If the script failed, you may need to:"
    echo "  1. Sell manually on MEXC website"
    echo "  2. Check if symbols are suspended"
    echo "  3. Verify API permissions"
fi

exit $EXIT_CODE
