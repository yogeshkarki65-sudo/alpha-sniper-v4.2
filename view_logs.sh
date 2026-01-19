#!/bin/bash
# View alpha-sniper logs in readable format

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "Installing jq for better log formatting..."
    sudo apt-get update -qq && sudo apt-get install -y jq
fi

# View logs with color and formatting
sudo journalctl -u alpha-sniper-async -f --no-hostname -o cat | while read line; do
    # Try to parse as JSON, otherwise print as-is
    if echo "$line" | jq -e . >/dev/null 2>&1; then
        echo "$line" | jq -r '"\(.time) [\(.level)] \(.message)"'
    else
        echo "$line"
    fi
done
