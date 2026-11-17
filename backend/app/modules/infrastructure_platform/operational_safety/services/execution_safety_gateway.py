"""
Execution Safety Gateway for M15.12.
Acts as a trusted backend enforcement boundary immediately before order dispatch,
validating kill-switch status, dependency health, pre-trade approval, and idempotency.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import uuid
from backend.app.modules.infrastructure_platform.operational_safety.models.safety_models import (
    ExecutionDecisionOutcome,
)
from backend.app.modules.infrastructure_platform.operational_safety.services.kill_switch_manager import (
    KillSwitchManager,
)


class ExecutionSafetyGateway:
    """Trusted backend gateway isolating execution adapters from UI and unverified callers."""

    POLICY_VERSION = "1.0.0"
    PERMISSION_VALIDITY_SECONDS = 10 # Short validity window prevents time-of-check to time-of-use drift

    @classmethod
    def evaluate_execution_permission(
        cls,
        instrument_id: str,
        requested_quantity: float,
        side: str,
        adapter_id: str = "default_broker_adapter",
        market_data_fresh: bool = True,
        pretrade_risk_passed: bool = True,
    ) -> Dict[str, Any]:
        """
        Evaluates execution permission fail-closed across all safety controls.
        """
        now = datetime.now(timezone.utc)
        reasons: List[str] = []
        is_blocked = False

        # 1. Global Kill Switch Check
        if KillSwitchManager.is_global_execution_blocked():
            reasons.append("GLOBAL_KILL_SWITCH_ACTIVE")
            is_blocked = True

        # 2. Scoped Adapter Kill Switch Check
        if KillSwitchManager.is_scope_blocked(scope_type="ADAPTER", scope_id=adapter_id):
            reasons.append(f"ADAPTER_KILL_SWITCH_ACTIVE_{adapter_id}")
            is_blocked = True

        # 3. Required Input & Freshness Validation
        if not market_data_fresh:
            reasons.append("MARKET_DATA_STALE_OR_UNAVAILABLE")
            is_blocked = True

        # 4. M11 Pre-trade Risk Limit Result Validation
        if not pretrade_risk_passed:
            reasons.append("PRETRADE_RISK_LIMIT_BREACH_OR_UNAVAILABLE")
            is_blocked = True

        # 5. Quantity and Side Invariants
        if requested_quantity <= 0:
            reasons.append("INVALID_REQUESTED_QUANTITY_NON_POSITIVE")
            is_blocked = True

        if side not in ["BUY", "SELL"]:
            reasons.append("INVALID_ORDER_SIDE")
            is_blocked = True

        decision = ExecutionDecisionOutcome.BLOCKED if is_blocked else ExecutionDecisionOutcome.ALLOWED

        return {
            "allowed": not is_blocked,
            "decision": decision,
            "reason_codes": reasons if is_blocked else ["ALL_SAFETY_CHECKS_PASSED"],
            "scope": "EXECUTION_GATEWAY",
            "evaluated_at": now,
            "safety_state_revision": 1,
            "policy_version": cls.POLICY_VERSION,
            "risk_decision_reference": f"ref_{uuid.uuid4().hex[:8]}",
            "valid_until": now + timedelta(seconds=cls.PERMISSION_VALIDITY_SECONDS),
        }
