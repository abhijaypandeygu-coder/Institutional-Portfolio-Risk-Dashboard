"""
Incident Management & Runbook Registry for M15.12.
Manages operational safety incident lifecycle, evidence references, and structured runbooks.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid
from backend.app.modules.infrastructure_platform.operational_safety.models.safety_models import (
    IncidentSeverity,
    IncidentStatus,
)


class IncidentManager:
    """Coordinates operational incidents, containment lifecycle, and emergency recovery runbooks."""

    INCIDENT_STORE: List[Dict[str, Any]] = [
        {
            "incident_reference": "INC-20261117-001",
            "title": "Baseline System Initialization & Gateway Ready",
            "description": "Routine verification of kill switches and preflight boundaries.",
            "severity": IncidentSeverity.SEV4_LOW,
            "status": IncidentStatus.RESOLVED,
            "affected_scope": "GLOBAL",
            "detected_at": datetime.now(timezone.utc),
            "acknowledged_at": datetime.now(timezone.utc),
            "resolved_at": datetime.now(timezone.utc),
        }
    ]

    RUNBOOK_CATALOGUE: List[Dict[str, Any]] = [
        {
            "runbook_code": "RB-EMERGENCY-SHUTDOWN",
            "title": "Emergency Execution Shutdown & Order Containment",
            "severity": "SEV1_CRITICAL",
            "summary": "Procedures for activating the Global Execution Kill Switch and verifying zero in-flight orders.",
            "steps": [
                "1. Authenticate with Administrator or Operator permissions.",
                "2. Dispatch POST /api/v1/operational-safety/kill-switches/activate with switch_code='GLOBAL_EXECUTION'.",
                "3. Verify response confirms state='ACTIVE'.",
                "4. Inspect broker-side pending orders (distinguish cancellation from submission blockage).",
                "5. Freeze background automated execution workers.",
                "6. Preserve audit snapshot and notify Trading Risk Desk.",
            ],
        },
        {
            "runbook_code": "RB-DATA-INTEGRITY",
            "title": "Market Data & Feed Stale Recovery Runbook",
            "severity": "SEV2_HIGH",
            "summary": "Steps to handle sequence gaps, stale feeds, and L2 order-book desynchronization.",
            "steps": [
                "1. Inspect M03 exception logs for dropped sequence packets.",
                "2. Invalidate downstream dependent pre-trade checks.",
                "3. Reconnect provider feed and request fresh L2 snapshot.",
                "4. Verify book reconstruction consistency and depth continuity.",
                "5. Revalidate M11 limit evaluation cache before permitting order routing.",
            ],
        },
        {
            "runbook_code": "RB-RECOVERY-REACTIVATION",
            "title": "Multi-Stage Controlled Reactivation Procedure",
            "severity": "SEV2_HIGH",
            "summary": "Evidence-based checklist for deactivating kill switches after incident resolution.",
            "steps": [
                "1. Confirm root cause remediation.",
                "2. Validate database transaction integrity and portfolio position ledgers.",
                "3. Perform pre-flight execution gateway check on synthetic test order.",
                "4. Obtain dual-authorization sign-off.",
                "5. Deactivate kill switch and monitor order latency for 15 minutes.",
            ],
        },
    ]

    @classmethod
    def list_incidents(cls) -> List[Dict[str, Any]]:
        return list(cls.INCIDENT_STORE)

    @classmethod
    def create_incident(
        cls,
        title: str,
        description: str,
        severity: IncidentSeverity = IncidentSeverity.SEV3_MEDIUM,
        affected_scope: str = "GLOBAL",
        detected_by: str = "operator",
    ) -> Dict[str, Any]:
        """Creates an incident record in the registry."""
        ref = f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
        inc = {
            "incident_reference": ref,
            "title": title,
            "description": description,
            "severity": severity,
            "status": IncidentStatus.DETECTED,
            "affected_scope": affected_scope,
            "detected_at": datetime.now(timezone.utc),
            "acknowledged_at": None,
            "resolved_at": None,
        }
        cls.INCIDENT_STORE.insert(0, inc)
        return inc

    @classmethod
    def list_runbooks(cls) -> List[Dict[str, Any]]:
        return list(cls.RUNBOOK_CATALOGUE)
