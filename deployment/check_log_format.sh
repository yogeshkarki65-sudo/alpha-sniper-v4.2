#!/bin/bash
echo "🔍 Checking actual log format from last 30 minutes..."
echo ""
echo "=== Looking for scan-related messages ==="
sudo journalctl -u alpha-sniper-live.service --since "30 minutes ago" --no-pager 2>/dev/null | grep -iE "(scan|cycle|market data|regime)" | tail -20
echo ""
echo "=== Checking for actual errors vs INFO logs ==="
sudo journalctl -u alpha-sniper-live.service --since "15 minutes ago" --no-pager 2>/dev/null | grep -i "ERROR\|CRITICAL\|Exception" | grep -v "INFO" | tail -10
