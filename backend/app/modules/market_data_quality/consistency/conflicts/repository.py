"""
Data Consistency Incident, Precedence, and Result Repository.
Handles CRUD and audit persistence for comparisons, conflicts, and rules.
"""

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_data_quality.consistency.models import (
    ConsistencyComparisonRule,
    ConsistencyComparisonResult,
    FieldConsistencyResult,
    ConsistencyConflict,
    SourcePrecedenceRule,
    ConsistencyResolutionHistory,
)
from backend.app.modules.market_data_quality.consistency.schemas import (
    SourcePrecedenceRuleCreate,
    ConflictResolutionActionRequest,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConsistencyRepository:
    """
    Data access repository for M03.06.
    """

    @staticmethod
    async def create_precedence_rule(
        session: AsyncSession, rule_in: SourcePrecedenceRuleCreate
    ) -> SourcePrecedenceRule:
        rule = SourcePrecedenceRule(**rule_in.model_dump())
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule

    @staticmethod
    async def list_precedence_rules(session: AsyncSession) -> List[SourcePrecedenceRule]:
        stmt = select(SourcePrecedenceRule).order_by(SourcePrecedenceRule.priority.asc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def save_comparison_result(
        session: AsyncSession, data: Dict[str, Any]
    ) -> ConsistencyComparisonResult:
        res = ConsistencyComparisonResult(**data)
        session.add(res)
        await session.commit()
        await session.refresh(res)
        return res

    @staticmethod
    async def save_field_consistency_result(
        session: AsyncSession, data: Dict[str, Any]
    ) -> FieldConsistencyResult:
        res = FieldConsistencyResult(**data)
        session.add(res)
        await session.commit()
        await session.refresh(res)
        return res

    @staticmethod
    async def create_or_update_conflict(
        session: AsyncSession,
        conflict_key: str,
        instrument_id: str,
        exchange: str,
        conflict_type: str,
        observation_type: str,
        comparison_result_id: Optional[str],
        severity: str,
        evidence: Optional[Dict[str, Any]] = None,
        selected_source: Optional[str] = None,
        selected_observation_id: Optional[str] = None,
        resolution_method: Optional[str] = None,
        resolution_rule_code: Optional[str] = None,
        resolution_reason: Optional[str] = None,
        conflict_status: str = "DETECTED",
    ) -> ConsistencyConflict:
        stmt = select(ConsistencyConflict).where(ConsistencyConflict.conflict_key == conflict_key)
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.severity = severity
            existing.conflict_status = conflict_status
            existing.evidence = evidence
            existing.selected_source = selected_source
            existing.selected_observation_id = selected_observation_id
            existing.resolution_method = resolution_method
            existing.resolution_rule_code = resolution_rule_code
            existing.resolution_reason = resolution_reason
            if conflict_status in ["AUTO_RESOLVED", "MANUALLY_RESOLVED"]:
                existing.resolved_at = utc_now()
            await session.commit()
            await session.refresh(existing)
            return existing

        conflict = ConsistencyConflict(
            conflict_key=conflict_key,
            instrument_id=instrument_id,
            exchange=exchange,
            conflict_type=conflict_type,
            observation_type=observation_type,
            comparison_result_id=comparison_result_id,
            severity=severity,
            conflict_status=conflict_status,
            selected_source=selected_source,
            selected_observation_id=selected_observation_id,
            resolution_method=resolution_method,
            resolution_rule_code=resolution_rule_code,
            resolution_reason=resolution_reason,
            detected_at=utc_now(),
            resolved_at=utc_now() if conflict_status in ["AUTO_RESOLVED", "MANUALLY_RESOLVED"] else None,
            evidence=evidence,
        )
        session.add(conflict)
        await session.commit()
        await session.refresh(conflict)
        return conflict

    @staticmethod
    async def get_conflict_by_key(
        session: AsyncSession, conflict_key: str
    ) -> Optional[ConsistencyConflict]:
        stmt = select(ConsistencyConflict).where(ConsistencyConflict.conflict_key == conflict_key)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_conflicts(
        session: AsyncSession,
        status: Optional[str] = None,
        instrument_id: Optional[str] = None
    ) -> List[ConsistencyConflict]:
        stmt = select(ConsistencyConflict)
        conditions = []
        if status:
            conditions.append(ConsistencyConflict.conflict_status == status)
        if instrument_id:
            conditions.append(ConsistencyConflict.instrument_id == instrument_id)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(ConsistencyConflict.id.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def apply_manual_resolution(
        session: AsyncSession,
        conflict: ConsistencyConflict,
        resolution: ConflictResolutionActionRequest,
        actor_id: str
    ) -> ConsistencyConflict:
        prev_status = conflict.conflict_status
        new_status = "MANUALLY_RESOLVED" if resolution.action != "REJECT_BOTH" else "UNRESOLVED"

        conflict.conflict_status = new_status
        conflict.resolution_method = "MANUAL_OVERRIDE"
        conflict.resolution_reason = f"[{resolution.action}] {resolution.justification}"
        conflict.resolved_at = utc_now()
        if resolution.selected_observation_id:
            conflict.selected_observation_id = resolution.selected_observation_id

        # Log resolution audit history
        hist = ConsistencyResolutionHistory(
            history_id=f"HIST_{uuid.uuid4().hex[:12].upper()}",
            conflict_id=conflict.id,
            conflict_key=conflict.conflict_key,
            resolution_action=resolution.action,
            selected_source_id=conflict.selected_source,
            selected_observation_id=conflict.selected_observation_id,
            previous_status=prev_status,
            new_status=new_status,
            actor_type="OPERATOR",
            actor_id=actor_id,
            justification=resolution.justification,
            evidence={"action_details": resolution.model_dump()},
            created_at=utc_now(),
        )
        session.add(hist)
        await session.commit()
        await session.refresh(conflict)
        return conflict

    @staticmethod
    async def get_summary_metrics(
        session: AsyncSession,
        instrument_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculates consistency metrics and open conflict counts.
        """
        stmt_comp = select(ConsistencyComparisonResult)
        if instrument_id:
            stmt_comp = stmt_comp.where(ConsistencyComparisonResult.instrument_id == instrument_id)
        res_comp = await session.execute(stmt_comp)
        comparisons = res_comp.scalars().all()

        total = len(comparisons)
        consistent = sum(1 for c in comparisons if c.comparison_status == "CONSISTENT")
        inconsistent = sum(1 for c in comparisons if c.comparison_status == "INCONSISTENT")
        uncomparable = sum(1 for c in comparisons if c.comparison_status in ["UNCOMPARABLE", "CURRENCY_MISMATCH", "TIMESTAMP_MISMATCH"])

        stmt_open_cnf = select(func.count(ConsistencyConflict.id)).where(
            ConsistencyConflict.conflict_status.in_(["DETECTED", "PENDING_MANUAL_REVIEW", "UNRESOLVED"])
        )
        stmt_res_cnf = select(func.count(ConsistencyConflict.id)).where(
            ConsistencyConflict.conflict_status.in_(["AUTO_RESOLVED", "MANUALLY_RESOLVED"])
        )

        res_open = await session.execute(stmt_open_cnf)
        res_resolved = await session.execute(stmt_res_cnf)

        open_cnf = res_open.scalar() or 0
        resolved_cnf = res_resolved.scalar() or 0

        rate = round((consistent / total * 100), 2) if total > 0 else 100.0

        return {
            "total_comparisons": total,
            "consistent_count": consistent,
            "inconsistent_count": inconsistent,
            "uncomparable_count": uncomparable,
            "open_conflicts": open_cnf,
            "resolved_conflicts": resolved_cnf,
            "consistency_rate_percentage": rate,
        }
