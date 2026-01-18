"""
Low-noise Telegram notifier for "action needed" situations.

Sends notifications with cooldown periods to avoid spam:
- Low balance warnings
- Unaffordable position skips
- Zero attempts despite candidates
- Service restarts
"""

import time
from typing import Optional
import logging


class ActionNeededNotifier:
    """
    Low-noise notifier for actionable situations.

    Each trigger type has its own cooldown to prevent spam.
    """

    def __init__(self, telegram_async, settings, logger: Optional[logging.Logger] = None):
        """
        Args:
            telegram_async: AsyncTelegram instance (or None if disabled)
            settings: Settings object with TELEGRAM_ACTION_NEEDED_ENABLE and TELEGRAM_ACTION_COOLDOWN_MIN
            logger: Logger instance
        """
        self.telegram = telegram_async
        self.settings = settings
        self.logger = logger or logging.getLogger(__name__)

        # Track last notification time per trigger type
        self.last_notify = {}

        # Track consecutive occurrences (for threshold-based triggers)
        self.consecutive_counts = {
            "low_balance": 0,
            "unaffordable": 0,
            "no_attempts": 0,
        }

        self.enabled = getattr(settings, "TELEGRAM_ACTION_NEEDED_ENABLE", True)
        self.cooldown_minutes = getattr(settings, "TELEGRAM_ACTION_COOLDOWN_MIN", 30)

    async def check_low_balance(self, free_usdt: float, required: float, scan_count: int = 1):
        """
        Check if free USDT is below required amount for several scans.

        Args:
            free_usdt: Current free USDT
            required: Required USDT (reserve + target notional)
            scan_count: How many consecutive scans this has been true
        """
        if not self.enabled or not self.telegram:
            return

        if free_usdt < required:
            self.consecutive_counts["low_balance"] += 1

            # Trigger after 3 consecutive scans (typically ~3 minutes)
            if self.consecutive_counts["low_balance"] >= 3:
                if self._can_notify("low_balance"):
                    msg = (
                        f"⚠️ Action Needed: Low Balance\n\n"
                        f"Free USDT: ${free_usdt:.2f}\n"
                        f"Required: ${required:.2f}\n"
                        f"Deficit: ${required - free_usdt:.2f}\n\n"
                        f"Bot may skip trades due to insufficient funds.\n"
                        f"Consider closing positions or depositing more USDT."
                    )
                    await self.telegram.send(msg)
                    self._mark_notified("low_balance")
                    self.consecutive_counts["low_balance"] = 0  # Reset after notification
        else:
            self.consecutive_counts["low_balance"] = 0  # Reset on recovery

    async def check_unaffordable_skips(self, unaffordable_count: int, candidates_count: int):
        """
        Check if many candidates are being skipped as unaffordable.

        Args:
            unaffordable_count: Number of unaffordable skips in recent scans
            candidates_count: Total candidates found
        """
        if not self.enabled or not self.telegram:
            return

        # Trigger if >50% of candidates are unaffordable and we have at least 3
        if candidates_count >= 3 and unaffordable_count >= candidates_count * 0.5:
            if self._can_notify("unaffordable"):
                msg = (
                    f"⚠️ Action Needed: Many Unaffordable Trades\n\n"
                    f"Skipped: {unaffordable_count}/{candidates_count} candidates\n"
                    f"Reason: Position sizing below exchange minimums\n\n"
                    f"Consider:\n"
                    f"• Increasing SIZING_NOTIONAL_USD\n"
                    f"• Increasing RISK_PER_TRADE\n"
                    f"• Depositing more funds"
                )
                await self.telegram.send(msg)
                self._mark_notified("unaffordable")

    async def check_no_attempts(self, hours_without_attempts: float, recent_candidates: int):
        """
        Check if no trade attempts despite finding candidates.

        Args:
            hours_without_attempts: Hours since last trade attempt
            recent_candidates: Number of candidates found in recent scans
        """
        if not self.enabled or not self.telegram:
            return

        # Trigger if >4 hours without attempts and we've seen candidates
        if hours_without_attempts > 4.0 and recent_candidates > 0:
            if self._can_notify("no_attempts"):
                msg = (
                    f"⚠️ Action Needed: No Trade Attempts\n\n"
                    f"Time without attempts: {hours_without_attempts:.1f}h\n"
                    f"Recent candidates: {recent_candidates}\n\n"
                    f"Possible issues:\n"
                    f"• LIVE_TEST_MODE daily limit reached\n"
                    f"• All candidates failing filters\n"
                    f"• Insufficient balance\n"
                    f"• Check logs for details"
                )
                await self.telegram.send(msg)
                self._mark_notified("no_attempts")

    async def notify_restart(self, sizing_mode: str, sizing_value: float, risk_value: float):
        """
        Send one-time startup notification with current configuration.

        Args:
            sizing_mode: "risk" or "notional"
            sizing_value: SIZING_NOTIONAL_USD if notional mode
            risk_value: RISK_PER_TRADE value
        """
        if not self.enabled or not self.telegram:
            return

        # Startup notifications bypass cooldown
        if sizing_mode == "notional":
            sizing_info = f"Mode: Notional (${sizing_value:.2f}/trade)"
        else:
            sizing_info = f"Mode: Risk ({risk_value:.4f} or {risk_value*100:.2f}%)"

        msg = (
            f"🔄 Bot Restarted\n\n"
            f"Sizing: {sizing_info}\n"
            f"Status: Ready to trade"
        )
        await self.telegram.send(msg)

    def _can_notify(self, trigger_type: str) -> bool:
        """Check if enough time has passed since last notification for this trigger."""
        last_time = self.last_notify.get(trigger_type, 0)
        now = time.time()
        cooldown_seconds = self.cooldown_minutes * 60

        return (now - last_time) >= cooldown_seconds

    def _mark_notified(self, trigger_type: str):
        """Mark that we just sent a notification for this trigger."""
        self.last_notify[trigger_type] = time.time()
        self.logger.info(f"[ACTION_NEEDED] Sent notification: {trigger_type}")
