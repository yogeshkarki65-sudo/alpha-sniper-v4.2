# Auto ENV Optimizer - One-Click Deployment

## 🚀 **COPY-PASTE DEPLOYMENT** (Production Server)

Copy and paste this **entire block** into your production server terminal:

```bash
# Download and run deployment script
cd /opt/alpha-sniper
curl -sS https://raw.githubusercontent.com/yogeshkarki65-sudo/alpha-sniper-v4.2/claude/fix-issues-018PzVLhR8jpyJBusPvozqDS/deploy_optimizer.sh | bash
```

**OR** if you've already pulled the code:

```bash
cd /opt/alpha-sniper
bash deploy_optimizer.sh
```

---

## 📋 What This Script Does

1. ✅ **Stops** the bot safely
2. ✅ **Creates backup** of .env and database
3. ✅ **Pulls latest code** from GitHub
4. ✅ **Runs optimizer in DRY-RUN** mode (shows what it would do)
5. ✅ **Asks for confirmation** before applying changes
6. ✅ **Applies changes** and restarts bot
7. ✅ **Sets up crontab** to run optimizer every 6 hours automatically
8. ✅ **Shows status** and monitoring commands

---

## ⚠️ What to Expect

### **First Run (Dry-Run):**

```
🤖 Alpha Sniper V4.2 - Automatic ENV Optimizer
================================================================================
📊 Mode: DRY RUN (no changes)

📊 METRICS
--------------------------------------------------------------------------------
Regime: SIDEWAYS
EMA Signals: 0.8 (target: 2-8)
Top Bottleneck: VOLUME (score: 62.3)

🚫 REJECTION BREAKDOWN
--------------------------------------------------------------------------------
   VOLUME_TOO_LOW: 342
   SCORE_TOO_LOW: 123

🔧 PROPOSED CHANGES
--------------------------------------------------------------------------------
Parameter                      Current         New             Reason
--------------------------------------------------------------------------------
MIN_PUMP_VOLUME_24H_USD       135000          115000          Loosen VOLUME: EMA signals 0.8 < target 2
MIN_SCORE                     30              28              Loosen SCORE: EMA signals 0.8 < target 2

⚠️  Review the proposed changes above.
   Do you want to APPLY these changes and restart the bot?

   Type 'yes' to continue, anything else to cancel:
```

### **If You Type 'yes':**

- Changes applied to `.env` file
- Bot restarted with new settings
- Cron job created for automatic optimization every 6 hours

### **If You Cancel:**

- Bot restarted with original settings
- No changes applied
- You can re-run anytime

---

## 🔄 Automatic Optimization Schedule

After deployment, the optimizer will run automatically:

**Schedule**: Every 6 hours (00:00, 06:00, 12:00, 18:00)

**What it does each run:**
1. Analyzes last 24 hours of PUMP_DEBUG logs
2. Detects bottlenecks (VOLUME, SCORE, MOMENTUM, etc.)
3. Proposes parameter changes
4. Applies changes if needed (with cooldown protection)
5. Restarts bot if changes applied
6. Logs results to `/var/log/alpha-sniper-optimizer.log`

**Safety limits:**
- ✅ Only changes signal generation params (NOT risk controls)
- ✅ 24-hour cooldown between changes
- ✅ Won't change params if within 10% of bounds
- ✅ Hysteresis (20% margin) prevents oscillation
- ✅ Rollback support via tune_history.json

---

## 📊 Monitoring

### **View Optimizer Logs:**
```bash
tail -f /var/log/alpha-sniper-optimizer.log
```

### **View Tune History:**
```bash
cat /opt/alpha-sniper/tune_history.json
```

### **View Current Bot Logs:**
```bash
tail -f /opt/alpha-sniper/logs/bot.log | grep -E "Signal.*score|Position opened"
```

### **Check Crontab:**
```bash
crontab -l | grep optimizer
```

### **Manually Run Optimizer (dry-run):**
```bash
cd /opt/alpha-sniper
source venv/bin/activate
python tools/auto_env_optimizer.py --log logs/bot.log --env alpha-sniper/.env --dry-run
```

### **Manually Apply Changes:**
```bash
cd /opt/alpha-sniper
source venv/bin/activate
python tools/auto_env_optimizer.py \
  --log logs/bot.log \
  --env alpha-sniper/.env \
  --db /var/lib/alpha-sniper/alpha_sniper.db \
  --apply \
  --restart-cmd "sudo systemctl restart alpha-sniper-live"
```

---

## 🎯 Expected Results

### **Before Optimizer:**
- Signal frequency: 0-1 per scan
- Rejections: VOLUME_TOO_LOW (60%), SCORE_TOO_LOW (30%)
- Bot finding signals but rejecting most

### **After Optimizer (within 24-48 hours):**
- Signal frequency: 2-8 per scan (SIDEWAYS target)
- Balanced rejections across filters
- Bot actively trading pump signals
- Parameters auto-tuned to market conditions

---

## 🛠️ Troubleshooting

### **Issue: Cron job not running**

Check cron service:
```bash
sudo systemctl status cron
```

Check crontab syntax:
```bash
crontab -l
```

### **Issue: Optimizer not making changes**

Check if in cooldown:
```bash
cat /opt/alpha-sniper/tune_history.json | grep last_change_time
```

Run manual dry-run to see why:
```bash
cd /opt/alpha-sniper
source venv/bin/activate
python tools/auto_env_optimizer.py --log logs/bot.log --env alpha-sniper/.env --dry-run
```

### **Issue: Want to disable automatic optimization**

Remove cron job:
```bash
crontab -e
# Delete the line containing "auto_env_optimizer.py"
```

### **Issue: Want to rollback changes**

Restore from backup:
```bash
# Find latest backup
ls -lt ~/backups/

# Restore
cp ~/backups/optimizer_deploy_YYYYMMDD_HHMMSS/env.backup /opt/alpha-sniper/alpha-sniper/.env
sudo systemctl restart alpha-sniper-live.service
```

---

## 📞 Support

- **Optimizer logs**: `/var/log/alpha-sniper-optimizer.log`
- **Tune history**: `/opt/alpha-sniper/tune_history.json`
- **Bot logs**: `/opt/alpha-sniper/logs/bot.log`
- **Backups**: `~/backups/optimizer_deploy_*/`

---

## ✅ Deployment Checklist

- [ ] Bot is currently running on production server
- [ ] You're logged into production server via SSH
- [ ] You've reviewed the PUMP_DEBUG logs (`tail -100 logs/bot.log | grep PUMP_DEBUG`)
- [ ] You understand the proposed changes will auto-tune MIN_SCORE, MIN_VOLUME, etc.
- [ ] You're ready to let the optimizer run automatically every 6 hours

**If all checked, run the deployment script above!** 🚀
