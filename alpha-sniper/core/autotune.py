"""
AutoTune Pro for Alpha Sniper v4.2

Flow-based tuner + sizing autopilot that adjusts thresholds and risk sizing
based on recent performance metrics.

Features:
- Signal flow monitoring (adjust thresholds to hit target signals/hour)
- Sizing autopilot (scale risk based on R-multiple and winrate)
- Live test mode flip (automatic graduation based on guardrails)
- Order quality tracking (IOC rejects, slippage)
"""

from collections import deque
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class AutoTunePro:
    """
    Flow-based tuner + sizing autopilot.

    Tracks recent scans (signals), order outcomes (IOC/slippage), and trade R.
    Adjusts EARLY_RET_5M_MIN, EARLY_VOL_SPIKE_MIN, MIN_SCORE, and RISK_PER_TRADE
    within safe bounds. Can flip LIVE_TEST_MODE off under guardrails.
    """

    def __init__(self, settings, overlay, log: Optional[logging.Logger] = None):
        """
        Initialize AutoTune Pro.

        Args:
            settings: Settings object
            overlay: RuntimeSettings overlay for making adjustments
            log: Optional logger instance
        """
        self.s = settings
        self.ovr = overlay
        self.log = log or logger

        # Signal flow tracking
        self.scan_window = deque(maxlen=self.s.AUTOTUNE_WINDOW_SCANS)

        # Order quality tracking
        self.slip_bps = deque(maxlen=500)
        self.ioc_events = deque(maxlen=500)  # 1 = reject, 0 = ok

        # Trade performance tracking
        self.r_last_trades = deque(maxlen=self.s.SIZING_WINDOW_TRADES)

        # State tracking
        self._last_adjust_scan = -10**9
        self._scan_count = 0

        # Baselines captured at startup (for restore logic)
        self._base_universe_min_quote_volume = float(getattr(self.s, "UNIVERSE_MIN_QUOTE_VOLUME", 100000.0))
        self._base_universe_size = int(getattr(self.s, "UNIVERSE_SIZE", 100))
        self._base_min_depth_usd_abs = float(getattr(self.s, "MIN_DEPTH_USD_ABSOLUTE", 15000.0))

        # Flow loosen/restore counters
        self._quiet_scans = 0
        self._restore_scans = 0
        self._quiet_scans_2 = 0
        self._accel_forced_off = False

        # Check if we're already at max loosening + floor on startup → trigger second notch immediately
        self._check_startup_second_notch()

    def _check_startup_second_notch(self):
        """
        Check if we're already at max loosening + floor thresholds on startup.
        If so, immediately trigger second notch (accel toggle) without waiting for FLOW_LOOSEN.
        """
        if not self.s.AUTO_ACCEL_TOGGLE:
            return

        # Check if already at max loosening
        at_max = (
            self.s.UNIVERSE_SIZE >= self.s.LOOSEN_UNIVERSE_SIZE_MAX and
            self.s.UNIVERSE_MIN_QUOTE_VOLUME <= self.s.LOOSEN_UNIVERSE_MIN_QUOTE_VOLUME_MIN
        )

        # Check if at threshold floor
        at_floor = (
            abs(self.s.EARLY_RET_5M_MIN - self.s.AUTOTUNE_RET5M_BOUNDS[0]) < 1e-9 and
            self.s.MIN_SCORE <= self.s.AUTOTUNE_SCORE_BOUNDS[0]
        )

        # If at max+floor and accel is still on → toggle it off immediately
        if at_max and at_floor:
            if bool(getattr(self.s, "EARLY_ACCEL_REQUIRED", True)):
                self.ovr.set("EARLY_ACCEL_REQUIRED", False)
                self._accel_forced_off = True
                self._quiet_scans_2 = 1  # Mark second notch as triggered
                self.log.info("[FLOW_TOGGLE] accel_required=False (startup at max+floor)")

    # === HOOKS (called by main loop) ===

    def on_scan(self, signals_count: int):
        """
        Record signal count from latest scan.

        Args:
            signals_count: Number of signals generated
        """
        self._scan_count += 1
        self.scan_window.append(int(signals_count))

    def on_order_result(self, ioc_rejected: Optional[bool] = None, slippage_bps: Optional[float] = None):
        """
        Record order execution metrics.

        Args:
            ioc_rejected: Whether IOC order was rejected (None if unknown)
            slippage_bps: Slippage in basis points (None if unknown)
        """
        if ioc_rejected is not None:
            self.ioc_events.append(1 if ioc_rejected else 0)

        if slippage_bps is not None:
            try:
                self.slip_bps.append(float(slippage_bps))
            except (ValueError, TypeError):
                pass

    def on_trade_closed(self, r_multiple: float):
        """
        Record R-multiple from closed trade.

        Args:
            r_multiple: R-multiple (realized PnL / initial risk)
        """
        try:
            self.r_last_trades.append(float(r_multiple))
        except (ValueError, TypeError):
            pass

    # === METRICS ===

    def _signals_per_hour(self) -> float:
        """
        Calculate estimated signals per hour based on recent scan window.

        Returns:
            Signals per hour estimate
        """
        if not self.scan_window:
            return 0.0

        scans_per_hour = max(1, int(3600 / self.s.SCAN_INTERVAL_SECONDS))
        return sum(self.scan_window) * (scans_per_hour / len(self.scan_window))

    def _ioc_reject_rate(self) -> float:
        """
        Calculate IOC order rejection rate.

        Returns:
            Rejection rate (0.0 to 1.0)
        """
        if not self.ioc_events:
            return 0.0
        return sum(self.ioc_events) / len(self.ioc_events)

    def _p95_slip_bps(self) -> float:
        """
        Calculate 95th percentile slippage in basis points.

        Returns:
            P95 slippage in bps
        """
        if not self.slip_bps:
            return 0.0

        arr = sorted(self.slip_bps)
        k = int(0.95 * (len(arr) - 1))
        return arr[max(0, k)]

    def _avgR_winrate(self) -> tuple[float, float]:
        """
        Calculate average R-multiple and winrate from recent trades.

        Returns:
            (avg_r, winrate) tuple
        """
        if not self.r_last_trades:
            return (0.0, 0.0)

        rs = list(self.r_last_trades)
        wins = sum(1 for r in rs if r > 0)
        winrate = wins / len(rs)
        avgR = sum(rs) / len(rs)

        return (avgR, winrate)

    # === ADJUSTERS ===

    def _clamp(self, v: float, lo: float, hi: float) -> float:
        """Clamp value between bounds."""
        return max(lo, min(hi, v))

    def maybe_tune(self):
        """
        Adjust signal thresholds based on recent signal flow.

        - If signals/hr < target min: loosen thresholds (lower values)
        - If signals/hr > target max: tighten thresholds (higher values)
        """
        if not self.s.AUTOTUNE_ENABLE:
            return

        # Cooldown check
        if self._scan_count - self._last_adjust_scan < self.s.AUTOTUNE_COOLDOWN_SCANS:
            return

        per_hour = self._signals_per_hour()
        lo, hi = self.s.AUTOTUNE_TARGET_MIN_HOURLY, self.s.AUTOTUNE_TARGET_MAX_HOURLY

        # Current values
        ret5m = float(self.s.EARLY_RET_5M_MIN)
        vsp = float(self.s.EARLY_VOL_SPIKE_MIN)
        score = int(self.s.MIN_SCORE)

        changed = False

        if per_hour < lo:
            # Too quiet -> loosen (decrease thresholds)
            new_ret = self._clamp(
                ret5m - self.s.AUTOTUNE_STEP_RET5M,
                *self.s.AUTOTUNE_RET5M_BOUNDS
            )
            new_vsp = self._clamp(
                vsp - self.s.AUTOTUNE_STEP_VSPIKE,
                *self.s.AUTOTUNE_VSPIKE_BOUNDS
            )
            new_sc = int(self._clamp(
                score - self.s.AUTOTUNE_STEP_SCORE,
                *self.s.AUTOTUNE_SCORE_BOUNDS
            ))

            if (new_ret, new_vsp, new_sc) != (ret5m, vsp, score):
                self.ovr.set("EARLY_RET_5M_MIN", new_ret)
                self.ovr.set("EARLY_VOL_SPIKE_MIN", new_vsp)
                self.ovr.set("MIN_SCORE", new_sc)
                changed = True

        elif per_hour > hi:
            # Too noisy -> tighten (increase thresholds)
            new_ret = self._clamp(
                ret5m + self.s.AUTOTUNE_STEP_RET5M,
                *self.s.AUTOTUNE_RET5M_BOUNDS
            )
            new_vsp = self._clamp(
                vsp + self.s.AUTOTUNE_STEP_VSPIKE,
                *self.s.AUTOTUNE_VSPIKE_BOUNDS
            )
            new_sc = int(self._clamp(
                score + self.s.AUTOTUNE_STEP_SCORE,
                *self.s.AUTOTUNE_SCORE_BOUNDS
            ))

            if (new_ret, new_vsp, new_sc) != (ret5m, vsp, score):
                self.ovr.set("EARLY_RET_5M_MIN", new_ret)
                self.ovr.set("EARLY_VOL_SPIKE_MIN", new_vsp)
                self.ovr.set("MIN_SCORE", new_sc)
                changed = True

        if changed:
            self._last_adjust_scan = self._scan_count
            self.log.info(
                f"[AUTOTUNE_PRO] signals/hr={per_hour:.2f} -> "
                f"RET5M={self.s.EARLY_RET_5M_MIN:.4f}, "
                f"VSP={self.s.EARLY_VOL_SPIKE_MIN:.2f}, "
                f"SCORE={self.s.MIN_SCORE}"
            )

        # When thresholds are at floor and flow is near zero, consider non-signal gate loosening
        at_floor = (
            abs(self.s.EARLY_RET_5M_MIN - self.s.AUTOTUNE_RET5M_BOUNDS[0]) < 1e-9 and
            abs(self.s.EARLY_VOL_SPIKE_MIN - self.s.AUTOTUNE_VSPIKE_BOUNDS[0]) < 1e-9 and
            self.s.MIN_SCORE <= self.s.AUTOTUNE_SCORE_BOUNDS[0]
        )
        self._auto_loosen_restore(per_hour, at_floor)

    def _auto_loosen_restore(self, per_hour: float, at_floor: bool):
        """
        Auto-loosen universe/depth gates when extremely quiet with thresholds at floor.
        Auto-restore toward baseline when flow recovers.

        Args:
            per_hour: Current signals per hour
            at_floor: Whether signal thresholds are at their minimum bounds
        """
        # Quiet market → Loosen universe/depth gates slowly
        if per_hour < 0.5 and at_floor:
            self._quiet_scans += 1
            self._restore_scans = 0

            if self._quiet_scans >= self.s.FLOW_QUIET_SCANS:
                # Loosen volume floor
                new_vol = max(
                    self.s.LOOSEN_UNIVERSE_MIN_QUOTE_VOLUME_MIN,
                    float(self.s.UNIVERSE_MIN_QUOTE_VOLUME) - self.s.LOOSEN_UNIVERSE_MIN_QUOTE_VOLUME_STEP
                )
                # Expand universe size
                new_size = min(
                    self.s.LOOSEN_UNIVERSE_SIZE_MAX,
                    int(self.s.UNIVERSE_SIZE) + self.s.LOOSEN_UNIVERSE_SIZE_STEP
                )
                # Lower depth floor
                new_depth = max(
                    self.s.LOOSEN_MIN_DEPTH_USD_ABS_MIN,
                    float(self.s.MIN_DEPTH_USD_ABSOLUTE) - self.s.LOOSEN_MIN_DEPTH_USD_ABS_STEP
                )

                changed = False
                if new_vol != self.s.UNIVERSE_MIN_QUOTE_VOLUME:
                    self.ovr.set("UNIVERSE_MIN_QUOTE_VOLUME", new_vol)
                    changed = True
                if new_size != self.s.UNIVERSE_SIZE:
                    self.ovr.set("UNIVERSE_SIZE", new_size)
                    changed = True
                if new_depth != self.s.MIN_DEPTH_USD_ABSOLUTE:
                    self.ovr.set("MIN_DEPTH_USD_ABSOLUTE", new_depth)
                    changed = True

                if changed:
                    self.log.info(
                        f"[FLOW_LOOSEN] vol>={new_vol:.0f} size={new_size} depth>={new_depth:.0f}"
                    )

                self._quiet_scans = 0
                self._quiet_scans_2 += 1

            # Second notch: toggle accel off + relax depth multiple (bounded)
            if self._quiet_scans_2 >= 1 and self.s.AUTO_ACCEL_TOGGLE:
                if bool(getattr(self.s, "EARLY_ACCEL_REQUIRED", True)):
                    self.ovr.set("EARLY_ACCEL_REQUIRED", False)
                    self._accel_forced_off = True
                    self.log.info("[FLOW_TOGGLE] accel_required=False (floor & quiet)")

            if self._quiet_scans_2 * self.s.FLOW_QUIET_SCANS >= self.s.FLOW_QUIET_SCANS_2:
                current_mult = float(getattr(self.s, "MIN_DEPTH_MULTIPLE", 200.0))
                new_mult = max(self.s.LOOSEN2_MIN_DEPTH_MULTIPLE_MIN, current_mult - 40.0)
                if new_mult != current_mult:
                    self.ovr.set("MIN_DEPTH_MULTIPLE", new_mult)
                    self.log.info(f"[FLOW_LOOSEN] depth_multiple>={new_mult:.0f}")
                self._quiet_scans_2 = 0

        # Flow healthy → Restore toward baseline
        elif per_hour > self.s.AUTOTUNE_TARGET_MIN_HOURLY:
            self._restore_scans += 1
            self._quiet_scans = 0
            self._quiet_scans_2 = 0

            if self._restore_scans >= self.s.FLOW_RESTORE_SCANS:
                # Restore volume floor toward baseline
                new_vol = min(
                    self._base_universe_min_quote_volume,
                    float(self.s.UNIVERSE_MIN_QUOTE_VOLUME) + self.s.LOOSEN_UNIVERSE_MIN_QUOTE_VOLUME_STEP
                )
                # Restore universe size toward baseline
                new_size = max(
                    self._base_universe_size,
                    int(self.s.UNIVERSE_SIZE) - self.s.LOOSEN_UNIVERSE_SIZE_STEP
                )
                # Restore depth floor toward baseline
                new_depth = min(
                    self._base_min_depth_usd_abs,
                    float(self.s.MIN_DEPTH_USD_ABSOLUTE) + self.s.LOOSEN_MIN_DEPTH_USD_ABS_STEP
                )

                changed = False
                if new_vol != self.s.UNIVERSE_MIN_QUOTE_VOLUME:
                    self.ovr.set("UNIVERSE_MIN_QUOTE_VOLUME", new_vol)
                    changed = True
                if new_size != self.s.UNIVERSE_SIZE:
                    self.ovr.set("UNIVERSE_SIZE", new_size)
                    changed = True
                if new_depth != self.s.MIN_DEPTH_USD_ABSOLUTE:
                    self.ovr.set("MIN_DEPTH_USD_ABSOLUTE", new_depth)
                    changed = True

                # Restore accel requirement if it was forced off
                if self._accel_forced_off and self.s.AUTO_ACCEL_TOGGLE:
                    self.ovr.set("EARLY_ACCEL_REQUIRED", True)
                    self._accel_forced_off = False
                    self.log.info("[FLOW_TOGGLE] accel_required=True (flow restored)")

                if changed:
                    self.log.info(
                        f"[FLOW_RESTORE] vol>={new_vol:.0f} size={new_size} depth>={new_depth:.0f}"
                    )

                self._restore_scans = 0

    def maybe_sizing_autopilot(self):
        """
        Adjust risk sizing based on recent trade performance.

        - Scale down on poor performance (low/negative avg R)
        - Scale up on good performance (high avg R + good winrate)
        """
        if not self.s.SIZING_AUTOPILOT_ENABLE:
            return

        if len(self.r_last_trades) < 5:  # Need minimum sample
            return

        avgR, winrate = self._avgR_winrate()

        # Scale down on bad performance
        if avgR <= self.s.SIZING_DOWN_AVG_R_MAX and hasattr(self.s, "RISK_PER_TRADE"):
            new_risk = self._clamp(
                self.s.RISK_PER_TRADE - self.s.SIZING_RISK_STEP,
                self.s.SIZING_RISK_MIN,
                self.s.SIZING_RISK_MAX
            )
            if new_risk != self.s.RISK_PER_TRADE:
                self.ovr.set("RISK_PER_TRADE", new_risk)
                self.log.info(
                    f"[SIZING_AUTOPILOT] DOWN: avgR={avgR:.2f} win={winrate:.2%} -> "
                    f"RISK_PER_TRADE={new_risk:.4f}"
                )
                return

        # Scale up on good performance
        if avgR >= self.s.SIZING_UP_AVG_R_MIN and winrate >= self.s.SIZING_UP_WINRATE_MIN:
            new_risk = self._clamp(
                self.s.RISK_PER_TRADE + self.s.SIZING_RISK_STEP,
                self.s.SIZING_RISK_MIN,
                self.s.SIZING_RISK_MAX
            )
            if new_risk != self.s.RISK_PER_TRADE:
                self.ovr.set("RISK_PER_TRADE", new_risk)
                self.log.info(
                    f"[SIZING_AUTOPILOT] UP: avgR={avgR:.2f} win={winrate:.2%} -> "
                    f"RISK_PER_TRADE={new_risk:.4f}"
                )

    def maybe_flip_live_test_off(self):
        """
        Automatically flip LIVE_TEST_MODE off if all guardrails pass.

        Guardrails:
        - Minimum number of trades
        - Minimum avg R-multiple
        - Minimum winrate
        - Maximum p95 slippage
        - Maximum IOC reject rate
        """
        if not self.s.LIVE_FLIP_ENABLE:
            return

        if not getattr(self.s, "LIVE_TEST_MODE", True):
            return  # Already in full live mode

        # Guardrail checks
        if len(self.r_last_trades) < self.s.LIVE_FLIP_MIN_TRADES:
            return

        avgR, winrate = self._avgR_winrate()

        if avgR < self.s.LIVE_FLIP_MIN_AVG_R or winrate < self.s.LIVE_FLIP_MIN_WINRATE:
            return

        if self._p95_slip_bps() > self.s.LIVE_FLIP_MAX_P95_SLIP_BPS:
            return

        if self._ioc_reject_rate() > self.s.LIVE_FLIP_MAX_IOC_REJECT_RATE:
            return

        # All guardrails passed - flip off test mode
        self.ovr.set("LIVE_TEST_MODE", False)
        self.log.info(
            f"[LIVE_FLIP] LIVE_TEST_MODE=False | "
            f"avgR={avgR:.2f} win={winrate:.2%} "
            f"slip_p95={self._p95_slip_bps():.0f}bps "
            f"ioc_rej={self._ioc_reject_rate():.0%}"
        )

    # === SNAPSHOT (for digest) ===

    def snapshot(self) -> dict:
        """
        Get current autotune state snapshot.

        Returns:
            Dict with current metrics and settings
        """
        avgR, winrate = self._avgR_winrate()

        return {
            "signals_per_hour": round(self._signals_per_hour(), 2),
            "p95_slip_bps": round(self._p95_slip_bps(), 0),
            "ioc_reject_rate": round(self._ioc_reject_rate(), 2),
            "avgR": round(avgR, 2),
            "winrate": round(winrate, 2),
            "EARLY_RET_5M_MIN": self.s.EARLY_RET_5M_MIN,
            "EARLY_VOL_SPIKE_MIN": self.s.EARLY_VOL_SPIKE_MIN,
            "MIN_SCORE": self.s.MIN_SCORE,
            "RISK_PER_TRADE": self.s.RISK_PER_TRADE,
            "LIVE_TEST_MODE": getattr(self.s, "LIVE_TEST_MODE", True),
        }
