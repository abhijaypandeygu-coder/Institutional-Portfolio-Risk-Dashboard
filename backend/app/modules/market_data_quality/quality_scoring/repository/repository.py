"""
M03.07 - Quality Scoring Repository.
Data persistence and query layer for scoring policies, reliability, completeness,
freshness, composite snapshots, and eligibility decisions.
"""

import uuid
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_data_quality.quality_scoring.models import (
    QualityScoringPolicy,
    QualityScoreRun,
    FeedReliabilityScore,
    CompletenessScore,
    FreshnessScore,
    DataQualitySnapshot,
    UseEligibilityProfile,
    UseEligibilityDecision,
    utc_now,
)
from backend.app.modules.market_data_quality.quality_scoring.schemas import (
    QualityScoringPolicyCreate,
)


class QualityScoringRepository:
    """
    Data access repository for M03.07.
    """

    @staticmethod
    async def create_policy(
        session: AsyncSession, policy_in: QualityScoringPolicyCreate
    ) -> QualityScoringPolicy:
        policy = QualityScoringPolicy(**policy_in.model_dump())
        session.add(policy)
        await session.commit()
        await session.refresh(policy)
        return policy

    @staticmethod
    async def list_policies(session: AsyncSession) -> List[QualityScoringPolicy]:
        stmt = select(QualityScoringPolicy).order_by(QualityScoringPolicy.id.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_policy_by_code(
        session: AsyncSession, policy_code: str
    ) -> Optional[QualityScoringPolicy]:
        stmt = select(QualityScoringPolicy).where(QualityScoringPolicy.policy_code == policy_code)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def save_reliability_score(
        session: AsyncSession, data: Dict[str, Any]
    ) -> FeedReliabilityScore:
        rec = FeedReliabilityScore(**data)
        session.add(rec)
        await session.commit()
        await session.refresh(rec)
        return rec

    @staticmethod
    async def save_completeness_score(
        session: AsyncSession, data: Dict[str, Any]
    ) -> CompletenessScore:
        rec = CompletenessScore(**data)
        session.add(rec)
        await session.commit()
        await session.refresh(rec)
        return rec

    @staticmethod
    async def save_freshness_score(
        session: AsyncSession, data: Dict[str, Any]
    ) -> FreshnessScore:
        rec = FreshnessScore(**data)
        session.add(rec)
        await session.commit()
        await session.refresh(rec)
        return rec

    @staticmethod
    async def save_quality_snapshot(
        session: AsyncSession, data: Dict[str, Any]
    ) -> DataQualitySnapshot:
        rec = DataQualitySnapshot(**data)
        session.add(rec)
        await session.commit()
        await session.refresh(rec)
        return rec

    @staticmethod
    async def save_eligibility_decision(
        session: AsyncSession, data: Dict[str, Any]
    ) -> UseEligibilityDecision:
        rec = UseEligibilityDecision(**data)
        session.add(rec)
        await session.commit()
        await session.refresh(rec)
        return rec

    @staticmethod
    async def list_eligibility_decisions(
        session: AsyncSession,
        feed_id: Optional[str] = None,
        profile_code: Optional[str] = None,
        limit: int = 100
    ) -> List[UseEligibilityDecision]:
        stmt = select(UseEligibilityDecision)
        conditions = []
        if feed_id:
            conditions.append(UseEligibilityDecision.feed_id == feed_id)
        if profile_code:
            conditions.append(UseEligibilityDecision.profile_code == profile_code)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(UseEligibilityDecision.id.desc()).limit(limit)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_summary_scores(
        session: AsyncSession, feed_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Aggregates recent composite scores and decisions.
        """
        stmt = select(DataQualitySnapshot)
        if feed_id:
            stmt = stmt.where(DataQualitySnapshot.feed_id == feed_id)
        res = await session.execute(stmt)
        snaps = res.scalars().all()

        if not snaps:
            return {
                "total_snapshots": 0,
                "average_composite_score": Decimal("100.00"),
                "average_reliability": Decimal("100.00"),
                "average_completeness": Decimal("100.00"),
                "average_freshness": Decimal("100.00"),
            }

        total = len(snaps)
        avg_comp = sum(s.composite_quality_score for s in snaps) / total
        avg_rel = sum(s.reliability_score for s in snaps) / total
        avg_compl = sum(s.completeness_score for s in snaps) / total
        avg_fresh = sum(s.freshness_score for s in snaps) / total

        return {
            "total_snapshots": total,
            "average_composite_score": round(avg_comp, 2),
            "average_reliability": round(avg_rel, 2),
            "average_completeness": round(avg_compl, 2),
            "average_freshness": round(avg_fresh, 2),
        }

