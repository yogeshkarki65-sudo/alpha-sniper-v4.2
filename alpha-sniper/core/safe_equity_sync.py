"""
Safe Equity Sync - Prevents catastrophic equity drops from pricing failures.

Implements sanity checks and fallback logic to ensure LIVE equity updates
are safe and don't death-spiral the bot.
"""

import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class EquitySyncResult:
    """Result of equity sync operation."""

    def __init__(
        self,
        success: bool,
        final_equity: float,
        computed_equity: Optional[float],
        reported_equity: Optional[float],
        deviation_pct: float,
        pricing_coverage_pct: float,
        priced_assets: int,
        unpriced_assets: int,
        unpriced_symbols: list,
        warning: Optional[str] = None,
        should_enter_defense: bool = False
    ):
        self.success = success
        self.final_equity = final_equity
        self.computed_equity = computed_equity
        self.reported_equity = reported_equity
        self.deviation_pct = deviation_pct
        self.pricing_coverage_pct = pricing_coverage_pct
        self.priced_assets = priced_assets
        self.unpriced_assets = unpriced_assets
        self.unpriced_symbols = unpriced_symbols
        self.warning = warning
        self.should_enter_defense = should_enter_defense


class SafeEquitySync:
    """
    Safe equity synchronization with catastrophic drop prevention.

    Protects against:
    - Missing price data causing equity to crater
    - Valuation failures being treated as losses
    - Death-spiral into DEFENSE mode due to sync issues
    """

    def __init__(self, config):
        self.config = config

        # Thresholds
        self.max_deviation_pct = getattr(config, 'equity_sync_max_deviation_pct', 40.0)
        self.min_coverage_pct = getattr(config, 'equity_sync_min_coverage_pct', 80.0)
        self.max_unpriced_assets = getattr(config, 'equity_sync_max_unpriced', 5)

        # State
        self.last_valid_equity = None
        self.pricing_failures_count = 0
        self.sync_anomaly_active = False  # Flag to prevent daily loss logic from triggering

    def sync_equity(
        self,
        exchange,
        current_equity: float,
        is_live: bool
    ) -> EquitySyncResult:
        """
        Safely sync equity from exchange with validation.

        Args:
            exchange: Exchange instance
            current_equity: Current equity value
            is_live: Whether running in LIVE mode

        Returns:
            EquitySyncResult with validated equity and diagnostics
        """
        if not is_live:
            # SIM mode: use simple balance fetch
            return EquitySyncResult(
                success=True,
                final_equity=current_equity,
                computed_equity=current_equity,
                reported_equity=None,
                deviation_pct=0.0,
                pricing_coverage_pct=100.0,
                priced_assets=1,
                unpriced_assets=0,
                unpriced_symbols=[],
                warning=None
            )

        # LIVE mode: get portfolio valuation with detailed tracking
        valuation = self._compute_portfolio_value(exchange)

        if not valuation['success']:
            # Complete failure - keep current equity
            logger.error(
                f"[EQUITY_SYNC] Portfolio valuation failed completely, "
                f"keeping previous equity: ${current_equity:.2f}"
            )
            return EquitySyncResult(
                success=False,
                final_equity=current_equity,
                computed_equity=None,
                reported_equity=None,
                deviation_pct=0.0,
                pricing_coverage_pct=0.0,
                priced_assets=0,
                unpriced_assets=0,
                unpriced_symbols=[],
                warning="Portfolio valuation failed completely"
            )

        computed_equity = valuation['total_value_usdt']
        priced_assets = valuation['priced_count']
        unpriced_assets = valuation['unpriced_count']
        unpriced_symbols = valuation['unpriced_symbols']
        total_assets = priced_assets + unpriced_assets

        # Calculate pricing coverage
        pricing_coverage_pct = (priced_assets / total_assets * 100) if total_assets > 0 else 100.0

        # Calculate deviation from current equity
        deviation_pct = abs((computed_equity - current_equity) / current_equity * 100) if current_equity > 0 else 0

        # Sanity checks
        warning = None
        should_enter_defense = False
        final_equity = computed_equity  # Default: use computed

        # Check 1: Pricing coverage
        if pricing_coverage_pct < self.min_coverage_pct or unpriced_assets > self.max_unpriced_assets:
            warning = (
                f"Low pricing coverage: {pricing_coverage_pct:.1f}% "
                f"({priced_assets}/{total_assets} assets priced, "
                f"{unpriced_assets} unpriced: {', '.join(unpriced_symbols[:5])}{'...' if len(unpriced_symbols) > 5 else ''})"
            )
            logger.warning(f"[EQUITY_SYNC] {warning}")

            # Keep previous equity if coverage is too low
            if pricing_coverage_pct < 50.0:
                final_equity = current_equity
                self.sync_anomaly_active = True
                logger.warning(
                    f"[EQUITY_SYNC] Coverage too low ({pricing_coverage_pct:.1f}%), "
                    f"REJECTING computed equity ${computed_equity:.2f}, "
                    f"keeping previous ${current_equity:.2f}"
                )

        # Check 2: Deviation threshold
        if deviation_pct > self.max_deviation_pct:
            warning = (
                f"Large deviation: {deviation_pct:.1f}% "
                f"(${current_equity:.2f} → ${computed_equity:.2f})"
            )
            logger.error(f"[EQUITY_SYNC] {warning}")

            # Log detailed breakdown
            logger.error(
                f"[EQUITY_SYNC] Equity breakdown:\n"
                f"  Previous: ${current_equity:.2f}\n"
                f"  Computed: ${computed_equity:.2f}\n"
                f"  USDT: ${valuation.get('usdt_balance', 0):.2f}\n"
                f"  Other assets: ${valuation.get('other_assets_value', 0):.2f}\n"
                f"  Priced: {priced_assets}/{total_assets} assets\n"
                f"  Unpriced: {', '.join(unpriced_symbols) if unpriced_symbols else 'none'}"
            )

            # Catastrophic drop: reject and enter defense
            if computed_equity < current_equity * 0.7:  # >30% drop
                final_equity = current_equity
                should_enter_defense = True
                self.sync_anomaly_active = True
                self.pricing_failures_count += 1

                logger.error(
                    f"[EQUITY_SYNC] CATASTROPHIC DROP PREVENTED: "
                    f"Computed equity ${computed_equity:.2f} is {deviation_pct:.1f}% below current ${current_equity:.2f}. "
                    f"REJECTING update and ENTERING DEFENSE MODE. "
                    f"Pricing failures: {self.pricing_failures_count}"
                )
            else:
                # Moderate deviation: accept but warn
                logger.warning(
                    f"[EQUITY_SYNC] Accepting computed equity ${computed_equity:.2f} "
                    f"despite {deviation_pct:.1f}% deviation (within tolerance)"
                )

        # Check 3: Recovery from anomaly
        if self.sync_anomaly_active and pricing_coverage_pct >= self.min_coverage_pct and deviation_pct < 10.0:
            logger.info(
                f"[EQUITY_SYNC] Sync anomaly cleared: coverage {pricing_coverage_pct:.1f}%, "
                f"deviation {deviation_pct:.1f}%"
            )
            self.sync_anomaly_active = False
            self.pricing_failures_count = 0

        # Update last valid equity if we're using computed
        if final_equity == computed_equity:
            self.last_valid_equity = computed_equity

        return EquitySyncResult(
            success=True,
            final_equity=final_equity,
            computed_equity=computed_equity,
            reported_equity=None,  # MEXC doesn't provide this directly
            deviation_pct=deviation_pct,
            pricing_coverage_pct=pricing_coverage_pct,
            priced_assets=priced_assets,
            unpriced_assets=unpriced_assets,
            unpriced_symbols=unpriced_symbols,
            warning=warning,
            should_enter_defense=should_enter_defense
        )

    def _compute_portfolio_value(self, exchange) -> Dict[str, Any]:
        """
        Compute portfolio value with detailed asset tracking.

        Returns dict with:
        - success: bool
        - total_value_usdt: float
        - usdt_balance: float
        - other_assets_value: float
        - priced_count: int
        - unpriced_count: int
        - unpriced_symbols: list
        - asset_details: list
        """
        try:
            balance = exchange.fetch_balance()
            if not balance:
                return {'success': False}

            # Start with USDT
            usdt_free = balance.get('USDT', {}).get('free', 0) or 0
            usdt_used = balance.get('USDT', {}).get('used', 0) or 0
            usdt_balance = usdt_free + usdt_used
            total_value_usdt = usdt_balance
            other_assets_value = 0.0

            # Track pricing results
            priced_assets = []
            unpriced_assets = []
            priced_count = 0
            unpriced_count = 0

            # Convert all other assets
            for asset, asset_balance in balance.items():
                # Skip USDT and metadata
                if asset == 'USDT' or asset in ['info', 'free', 'used', 'total']:
                    continue

                try:
                    total_amount = asset_balance.get('total', 0) or 0
                    if total_amount <= 0 or total_amount < 0.00001:  # Skip dust
                        continue

                    # Try to get price
                    symbol = f"{asset}/USDT"
                    ticker = exchange.get_ticker(symbol)

                    if ticker and ticker.get('last'):
                        price = ticker.get('last', ticker.get('close', 0)) or 0
                        if price > 0:
                            asset_value_usdt = total_amount * price
                            total_value_usdt += asset_value_usdt
                            other_assets_value += asset_value_usdt
                            priced_count += 1
                            priced_assets.append({
                                'asset': asset,
                                'amount': total_amount,
                                'price': price,
                                'value_usdt': asset_value_usdt
                            })
                        else:
                            # Price is 0
                            unpriced_count += 1
                            unpriced_assets.append(asset)
                            logger.debug(f"[EQUITY_SYNC] Asset {asset} has zero price")
                    else:
                        # Ticker fetch failed
                        unpriced_count += 1
                        unpriced_assets.append(asset)
                        logger.debug(f"[EQUITY_SYNC] Could not fetch ticker for {asset}")

                except Exception as e:
                    unpriced_count += 1
                    unpriced_assets.append(asset)
                    logger.debug(f"[EQUITY_SYNC] Error pricing {asset}: {e}")

            # Log detailed breakdown
            logger.info(
                f"[EQUITY_SYNC] Portfolio valuation: "
                f"USDT=${usdt_balance:.2f} | "
                f"Other=${other_assets_value:.2f} | "
                f"Total=${total_value_usdt:.2f} | "
                f"Priced={priced_count} | "
                f"Unpriced={unpriced_count}"
            )

            if priced_assets:
                top_holdings = sorted(priced_assets, key=lambda x: x['value_usdt'], reverse=True)[:5]
                holdings_str = ' | '.join([
                    f"{h['asset']}=${h['value_usdt']:.2f}" for h in top_holdings
                ])
                logger.info(f"[EQUITY_SYNC] Top holdings: {holdings_str}")

            if unpriced_assets:
                logger.warning(f"[EQUITY_SYNC] Unpriced assets: {', '.join(unpriced_assets)}")

            return {
                'success': True,
                'total_value_usdt': total_value_usdt,
                'usdt_balance': usdt_balance,
                'other_assets_value': other_assets_value,
                'priced_count': priced_count,
                'unpriced_count': unpriced_count,
                'unpriced_symbols': unpriced_assets,
                'asset_details': priced_assets
            }

        except Exception as e:
            logger.error(f"[EQUITY_SYNC] Error computing portfolio value: {e}")
            return {'success': False}

    def is_sync_anomaly_active(self) -> bool:
        """Check if sync anomaly is currently active (prevents daily loss logic)."""
        return self.sync_anomaly_active
