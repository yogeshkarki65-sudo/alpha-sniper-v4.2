# Rollback Instructions

## Quick Rollback (Git-based)

If you applied patches and need to revert:

### 1. Check current commit
```bash
cd /opt/alpha-sniper/alpha-sniper
git log --oneline -5
```

You should see something like:
```
abc1234 feat(sizing): clamp to free_usdt, auto-bump to min cost, IOC fallback
def5678 fix(app): pass settings into manage loop; precision-safe rounding
2c751d5 fix: Apply LIVE_TEST_MODE cap to EAGER position sizing  ← KNOWN GOOD
bc0bc9e fix: Use absolute path for .env.async to resolve startup crashes
60c9866 fix: Change settings to read .env.async for professional async-specific configuration
```

### 2. Rollback to last known good commit

```bash
# Stop the service
sudo systemctl stop alpha-sniper-async.service

# Rollback to the commit BEFORE patches (2c751d5 in example above)
git reset --hard 2c751d5

# Or rollback by number of commits (e.g., undo last 2 commits)
git reset --hard HEAD~2

# Restart service
sudo systemctl start alpha-sniper-async.service

# Verify
sudo systemctl status alpha-sniper-async.service
sudo journalctl -u alpha-sniper-async.service -n 50
```

### 3. Verify rollback successful

```bash
# Check if bot is trading normally
sudo journalctl -u alpha-sniper-async.service -f | grep -E 'EAGER|OPENED|SCAN'
```

You should see familiar patterns:
```
[LIVE_TEST] WLD/USDT size capped $349.96 → $7.50
[EAGER] OPENED WLD/USDT @ 0.58040000
```

## Manual Rollback (File-by-file)

If git rollback doesn't work, restore from backup:

### 1. Restore specific files

```bash
cd /opt/alpha-sniper/alpha-sniper

# Backup current (broken) state first
cp app_async.py app_async.py.broken
cp alpha-sniper/core/exchange_async.py alpha-sniper/core/exchange_async.py.broken
cp alpha-sniper/config/settings.py alpha-sniper/config/settings.py.broken

# Restore from git history
git checkout 2c751d5 -- app_async.py
git checkout 2c751d5 -- alpha-sniper/core/exchange_async.py
git checkout 2c751d5 -- alpha-sniper/config/settings.py
git checkout 2c751d5 -- scripts/print_settings.py

# Restart
sudo systemctl restart alpha-sniper-async.service
```

### 2. Remove added settings

If you added new overrides, remove them:

```bash
source ../venv/bin/activate
python ../scripts/overrides_cli.py delete --key RESERVE_USDT
python ../scripts/overrides_cli.py delete --key EAGER_EPS_PCT
python ../scripts/overrides_cli.py delete --key IOC_EMULATION_TIMEOUT_MS
python ../scripts/overrides_cli.py delete --key ORDER_RETRY_ON_BALANCE_ERROR
deactivate
```

## Emergency: Service Won't Start

If rollback leaves service broken:

### 1. Check service status
```bash
sudo systemctl status alpha-sniper-async.service --no-pager -l
```

### 2. Check logs for error
```bash
sudo journalctl -u alpha-sniper-async.service -n 100 --no-pager | tail -50
```

### 3. Common issues and fixes

**"ModuleNotFoundError":**
```bash
# Reinstall dependencies
cd /opt/alpha-sniper
source venv/bin/activate
pip install -r requirements.txt
deactivate
sudo systemctl restart alpha-sniper-async.service
```

**"NameError: 'settings' is not defined":**
```bash
# This was fixed in earlier commits - you may need different rollback point
git log --oneline --grep="settings" -10
git reset --hard <commit_before_settings_changes>
```

**"ValueError: LIVE mode requires ALPHA_API_KEY":**
```bash
# Settings file path issue - verify .env.async exists
ls -la /opt/alpha-sniper/alpha-sniper/.env.async

# Check settings.py points to correct path
grep "env_file=" /opt/alpha-sniper/alpha-sniper/alpha-sniper/config/settings.py
# Should show: env_file="/opt/alpha-sniper/alpha-sniper/.env.async"
```

## Nuclear Option: Full Reset to Known Good State

If all else fails, reset to the commit where bot was last known working:

```bash
# This is the commit from our debugging session where bot successfully traded
cd /opt/alpha-sniper/alpha-sniper
git reset --hard 2c751d53

# Force clean any untracked files
git clean -fd

# Restart
sudo systemctl restart alpha-sniper-async.service

# Verify
sudo journalctl -u alpha-sniper-async.service -f | grep "OPENED\|CLOSED\|EAGER"
```

## Verify Rollback Success

After rollback, confirm these still work:

1. **Service starts without errors:**
   ```bash
   sudo systemctl status alpha-sniper-async.service | grep "active (running)"
   ```

2. **Settings load correctly:**
   ```bash
   sudo journalctl -u alpha-sniper-async.service -n 100 | grep "LIVE_TEST_MODE: True"
   ```

3. **EAGER finding candidates:**
   ```bash
   sudo journalctl -u alpha-sniper-async.service --since "5 minutes ago" | grep "\[EARLY_TOP\]"
   ```

4. **Trades executing:**
   Wait for next scan and check for `[EAGER] OPENED` or `[LIVE_TEST]` messages

## Prevention: Always Create Rollback Point

Before applying ANY patches in future:

```bash
# Tag current working state
git tag working-$(date +%Y%m%d-%H%M)
git tag  # List tags

# Can rollback to tag later
git reset --hard working-20260111-1523
```

## Need Help?

If rollback fails and bot is broken:

1. **Stop the service** (prevent bad trades):
   ```bash
   sudo systemctl stop alpha-sniper-async.service
   sudo systemctl disable alpha-sniper-async.service  # Prevent auto-restart
   ```

2. **Capture full diagnostics:**
   ```bash
   sudo journalctl -u alpha-sniper-async.service -n 500 > /tmp/diagnostic.log
   git log --oneline -20 > /tmp/git_history.log
   git status > /tmp/git_status.log
   git diff > /tmp/git_diff.log
   ```

3. **Restore from backup** (if you made one)

4. **Re-apply known good fixes manually** from our debugging session:
   - Settings absolute path fix
   - LIVE_TEST_MODE cap in EAGER
   - None handling for initial_risk_usd

## Last Resort: Fresh Clone

If repository is completely broken:

```bash
# Backup data
sudo cp -r /opt/alpha-sniper/data /tmp/alpha-sniper-data-backup

# Clone fresh
cd /opt
sudo mv alpha-sniper alpha-sniper.broken
sudo git clone <your-repo-url> alpha-sniper
cd alpha-sniper
# ... setup venv, copy .env.async, etc ...

# Restore data
sudo cp -r /tmp/alpha-sniper-data-backup/* /opt/alpha-sniper/data/
```

**Note:** This loses all local commits. Only use if git history is corrupted.
