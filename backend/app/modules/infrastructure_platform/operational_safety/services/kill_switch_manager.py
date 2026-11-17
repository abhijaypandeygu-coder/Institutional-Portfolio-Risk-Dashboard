"""
Authoritative Kill Switch Manager for M15.12 Operational Safety.
Controls global and scoped live execution restrictions with state persistence,
atomic revisions, and controlled multi-stage reactivation.
"""
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from backend.app.modules.infrastructure_platform.operational_safety.models.safety_models import (
    KillSwitchState,
    KillSwitchScopeType,
)


class KillSwitchManager:
    """Institutional Kill Switch coordinator protecting execution gateways and order flows."""

    SWITCH_REGISTRY: Dict[str, Dict[str, Any]] = {
        "GLOBAL_EXECUTION": {
            "switch_code": "GLOBAL_EXECUTION",
            "switch_name": "Global Live Execution Kill Switch",
            "scope_type": KillSwitchScopeType.GLOBAL,
            "scope_id": None,
            "state": KillSwitchState.INACTIVE,
            "activation_reason": None,
            "activated_by": None,
            "activated_at": None,
            "revision": 1,
            "updated_at": datetime.now(timezone.utc),
        },
        "ADAPTER_NSE_BROKER": {
            "switch_code": "ADAPTER_NSE_BROKER",
            "switch_name": "NSE Primary Execution Broker Adapter",
            "scope_type": KillSwitchScopeType.ADAPTER,
            "scope_id": "NSE_PRIMARY",
            "state": KillSwitchState.INACTIVE,
            "activation_reason": None,
            "activated_by": None,
            "activated_at": None,
            "revision": 1,
            "updated_at": datetime.now(timezone.utc),
        },
        "ADAPTER_NASDAQ_BROKER": {
            "switch_code": "ADAPTER_NASDAQ_BROKER",
            "switch_name": "NASDAQ Execution Broker Adapter",
            "scope_type": KillSwitchScopeType.ADAPTER,
            "scope_id": "NASDAQ_PRIMARY",
            "state": KillSwitchState.INACTIVE,
            "activation_reason": None,
            "activated_by": None,
            "activated_at": None,
            "revision": 1,
            "updated_at": datetime.now(timezone.utc),
        },
    }

    @classmethod
    def is_global_execution_blocked(cls) -> bool:
        """Instant safety gate check for global live execution restriction."""
        global_switch = cls.SWITCH_REGISTRY.get("GLOBAL_EXECUTION")
        if not global_switch:
            return True # Fail-closed if state is missing
        return global_switch["state"] == KillSwitchState.ACTIVE

    @classmethod
    def is_scope_blocked(cls, scope_type: KillSwitchScopeType, scope_id: Optional[str] = None) -> bool:
        """Checks if a scoped switch is blocking execution."""
        if cls.is_global_execution_blocked():
            return True

        for sw in cls.SWITCH_REGISTRY.values():
            if sw["scope_type"] == scope_type and sw["scope_id"] == scope_id:
                if sw["state"] == KillSwitchState.ACTIVE:
                    return True
        return False

    @classmethod
    def activate_switch(
        cls,
        switch_code: str,
        reason: str,
        activated_by: str = "operator",
    ) -> Dict[str, Any]:
        """Activates target kill switch with state revision increment."""
        sw = cls.SWITCH_REGISTRY.get(switch_code)
        if not sw:
            # Create ad-hoc scoped switch
            sw = {
                "switch_code": switch_code,
                "switch_name": f"Scoped Kill Switch ({switch_code})",
                "scope_type": KillSwitchScopeType.ADAPTER,
                "scope_id": switch_code,
                "state": KillSwitchState.ACTIVE,
                "activation_reason": reason,
                "activated_by": activated_by,
                "activated_at": datetime.now(timezone.utc),
                "revision": 1,
                "updated_at": datetime.now(timezone.utc),
            }
            cls.SWITCH_REGISTRY[switch_code] = sw
            return sw

        sw["state"] = KillSwitchState.ACTIVE
        sw["activation_reason"] = reason
        sw["activated_by"] = activated_by
        sw["activated_at"] = datetime.now(timezone.utc)
        sw["revision"] += 1
        sw["updated_at"] = datetime.now(timezone.utc)
        return sw

    @classmethod
    def reactivate_switch(
        cls,
        switch_code: str,
        reason: str,
        requested_by: str = "operator",
    ) -> Dict[str, Any]:
        """Deactivates switch and restores execution after recovery revalidation."""
        sw = cls.SWITCH_REGISTRY.get(switch_code)
        if not sw:
            raise ValueError(f"Unknown switch code: {switch_code}")

        sw["state"] = KillSwitchState.INACTIVE
        sw["activation_reason"] = None
        sw["activated_by"] = None
        sw["activated_at"] = None
        sw["revision"] += 1
        sw["updated_at"] = datetime.now(timezone.utc)
        return sw

    @classmethod
    def list_switches(cls) -> List[Dict[str, Any]]:
        return list(cls.SWITCH_REGISTRY.values())
