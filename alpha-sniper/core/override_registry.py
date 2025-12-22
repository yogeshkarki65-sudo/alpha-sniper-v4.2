"""
Override Registry - Central authority for DDL parameter overrides.

Maps DDL keys to runtime targets with bounds checking and type coercion.
Ensures overrides are applied safely and prevent configuration spam.
"""

import logging
from typing import Any, Dict, Optional, Callable

logger = logging.getLogger(__name__)


class OverrideSpec:
    """Specification for a single override parameter."""

    def __init__(
        self,
        key: str,
        target_obj: str,
        target_attr: str,
        value_type: type,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        default: Any = None,
        allowed_in_live: bool = True,
        description: str = ""
    ):
        self.key = key
        self.target_obj = target_obj  # e.g., "config", "scratch_manager", "risk_engine"
        self.target_attr = target_attr  # e.g., "max_concurrent_positions"
        self.value_type = value_type
        self.min_value = min_value
        self.max_value = max_value
        self.default = default
        self.allowed_in_live = allowed_in_live
        self.description = description

    def validate_and_coerce(self, value: Any) -> tuple[bool, Any, Optional[str]]:
        """
        Validate and coerce value to correct type with bounds checking.

        Returns: (is_valid, coerced_value, error_message)
        """
        try:
            # Type coercion
            if self.value_type == int:
                coerced = int(value)
            elif self.value_type == float:
                coerced = float(value)
            elif self.value_type == bool:
                coerced = bool(value)
            else:
                coerced = value

            # Bounds checking
            if self.min_value is not None and coerced < self.min_value:
                return False, None, f"Value {coerced} below minimum {self.min_value}"

            if self.max_value is not None and coerced > self.max_value:
                return False, None, f"Value {coerced} above maximum {self.max_value}"

            return True, coerced, None

        except (ValueError, TypeError) as e:
            return False, None, f"Type coercion failed: {e}"


class OverrideRegistry:
    """
    Central registry for DDL parameter overrides.

    Defines authoritative mapping of DDL keys to runtime targets.
    Prevents "Unknown parameter" warnings by defining all valid overrides.
    """

    def __init__(self):
        self.specs: Dict[str, OverrideSpec] = {}
        self._ignored_keys = set()  # Keys to silently ignore (logged once)
        self._ignore_logged = set()  # Track which ignored keys have been logged

        # Register all supported overrides
        self._register_standard_overrides()

    def _register_standard_overrides(self):
        """Register all supported DDL override parameters."""

        # Position sizing
        self.register(OverrideSpec(
            key="position_size_multiplier",
            target_obj="runtime",  # Applied during position sizing
            target_attr="position_size_multiplier",
            value_type=float,
            min_value=0.0,
            max_value=2.0,
            default=1.0,
            allowed_in_live=True,
            description="Multiplier for position size (0.5=half, 1.2=20% larger)"
        ))

        # Score threshold
        self.register(OverrideSpec(
            key="min_score_multiplier",
            target_obj="runtime",
            target_attr="min_score_multiplier",
            value_type=float,
            min_value=0.5,
            max_value=2.0,
            default=1.0,
            allowed_in_live=True,
            description="Multiplier for minimum score threshold (1.2=20% stricter)"
        ))

        # Max positions (already works via config)
        self.register(OverrideSpec(
            key="max_concurrent_positions",
            target_obj="config",
            target_attr="max_concurrent_positions",
            value_type=int,
            min_value=0,
            max_value=10,
            default=2,
            allowed_in_live=True,
            description="Maximum concurrent positions allowed"
        ))

        # Hold time
        self.register(OverrideSpec(
            key="max_hold_hours",
            target_obj="runtime",
            target_attr="max_hold_hours",
            value_type=float,
            min_value=1.0,
            max_value=168.0,  # 1 week
            default=48.0,
            allowed_in_live=True,
            description="Maximum holding period in hours"
        ))

        # Scratch timeout
        self.register(OverrideSpec(
            key="scratch_timeout_seconds",
            target_obj="scratch_manager",
            target_attr="timeout_override",
            value_type=float,
            min_value=10.0,
            max_value=300.0,
            default=60.0,
            allowed_in_live=True,
            description="Scratch exit timeout in seconds"
        ))

        # Trailing activation (if trailing exists)
        self.register(OverrideSpec(
            key="trailing_activation_pct",
            target_obj="ignored",  # Not implemented yet
            target_attr="trailing_activation_pct",
            value_type=float,
            min_value=0.0,
            max_value=0.20,
            default=0.05,
            allowed_in_live=True,
            description="Trailing stop activation threshold (not implemented)"
        ))

        # Mark trailing_activation_pct as ignored (log once at startup)
        self._ignored_keys.add("trailing_activation_pct")

    def register(self, spec: OverrideSpec):
        """Register an override specification."""
        self.specs[spec.key] = spec

    def is_ignored(self, key: str) -> bool:
        """Check if key is marked as ignored."""
        return key in self._ignored_keys

    def should_log_ignore(self, key: str) -> bool:
        """Check if we should log that this key is ignored (only once)."""
        if key in self._ignore_logged:
            return False
        self._ignore_logged.add(key)
        return True

    def apply_overrides(
        self,
        overrides: Dict[str, Any],
        config,
        scratch_manager,
        is_live: bool
    ) -> Dict[str, Any]:
        """
        Apply overrides to appropriate targets with validation.

        Args:
            overrides: Dict of override key -> value from DDL
            config: Config object
            scratch_manager: ScratchExitManager instance (or None)
            is_live: Whether running in LIVE mode

        Returns:
            Dict of successfully applied overrides with final values
        """
        applied = {}
        runtime_overrides = {}

        for key, value in overrides.items():
            # Check if key is registered
            if key not in self.specs:
                # Unknown parameter - log warning once per session
                if not hasattr(self, '_unknown_logged'):
                    self._unknown_logged = set()
                if key not in self._unknown_logged:
                    logger.warning(f"[DDL_OVERRIDE] Unknown parameter: {key} - add to OverrideRegistry if needed")
                    self._unknown_logged.add(key)
                continue

            spec = self.specs[key]

            # Check if ignored
            if self.is_ignored(key):
                if self.should_log_ignore(key):
                    logger.info(f"[DDL_OVERRIDE] Ignoring {key}: {spec.description}")
                continue

            # Check if allowed in LIVE
            if is_live and not spec.allowed_in_live:
                logger.warning(f"[DDL_OVERRIDE] Skipping {key} in LIVE mode (not allowed)")
                continue

            # Validate and coerce
            is_valid, coerced_value, error_msg = spec.validate_and_coerce(value)
            if not is_valid:
                logger.error(f"[DDL_OVERRIDE] Rejected {key}={value}: {error_msg}")
                continue

            # Apply to target
            if spec.target_obj == "config":
                if hasattr(config, spec.target_attr):
                    old_value = getattr(config, spec.target_attr)
                    setattr(config, spec.target_attr, coerced_value)
                    applied[key] = coerced_value
                    logger.debug(f"[DDL_OVERRIDE] {key}: {old_value} → {coerced_value}")
                else:
                    logger.warning(f"[DDL_OVERRIDE] Config missing attribute: {spec.target_attr}")

            elif spec.target_obj == "scratch_manager":
                if scratch_manager and hasattr(scratch_manager, spec.target_attr):
                    old_value = getattr(scratch_manager, spec.target_attr, None)
                    setattr(scratch_manager, spec.target_attr, coerced_value)
                    applied[key] = coerced_value
                    logger.debug(f"[DDL_OVERRIDE] {key}: {old_value} → {coerced_value}")
                elif not scratch_manager:
                    logger.debug(f"[DDL_OVERRIDE] Scratch manager not available, skipping {key}")

            elif spec.target_obj == "runtime":
                # Store for runtime application during position sizing/entry
                runtime_overrides[key] = coerced_value
                applied[key] = coerced_value
                logger.debug(f"[DDL_OVERRIDE] {key}: {coerced_value} (runtime)")

            elif spec.target_obj == "ignored":
                # Already handled above
                pass

        # Store runtime overrides in config for access during sizing
        config.ddl_runtime_overrides = runtime_overrides

        return applied


def get_override_registry() -> OverrideRegistry:
    """Get singleton override registry instance."""
    if not hasattr(get_override_registry, '_instance'):
        get_override_registry._instance = OverrideRegistry()
    return get_override_registry._instance
