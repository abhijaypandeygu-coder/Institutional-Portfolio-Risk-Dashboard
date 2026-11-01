"""
Repository layer for M04.02 Security Classification.
Handles scheme queries, hierarchical taxonomy searches, bitemporal point-in-time queries,
bulk analytical aggregations, and coverage statistics.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, update, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.instrument_reference_data.security_classification.models import (
    ClassificationScheme,
    ClassificationSchemeVersion,
    ClassificationNode,
    AssetCategory,
    InstrumentClassificationAssignment,
    InstrumentAssetCategoryAssignment,
    ClassificationReviewCase,
    ClassificationAuditEvent,
    utc_now,
)
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument


class ClassificationRepository:
    """Repository handling database queries and atomic transactions for Security Classification."""

    @staticmethod
    async def create_audit_event(
        session: AsyncSession,
        action_type: str,
        new_state: str,
        actor_id: str,
        reason: str,
        instrument_id: Optional[str] = None,
        previous_state: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ClassificationAuditEvent:
        event = ClassificationAuditEvent(
            instrument_id=instrument_id,
            action_type=action_type,
            previous_state=previous_state,
            new_state=new_state,
            actor_id=actor_id,
            reason=reason,
            metadata_snapshot=metadata,
        )
        session.add(event)
        return event

    @staticmethod
    async def get_scheme_by_code(
        session: AsyncSession, scheme_code: str
    ) -> Optional[ClassificationScheme]:
        stmt = select(ClassificationScheme).where(ClassificationScheme.scheme_code == scheme_code)
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def get_default_primary_scheme(
        session: AsyncSession,
    ) -> Optional[ClassificationScheme]:
        stmt = select(ClassificationScheme).where(ClassificationScheme.is_primary_default.is_(True))
        scheme = (await session.execute(stmt)).scalars().first()
        if not scheme:
            # Fallback to first active scheme
            stmt_fallback = select(ClassificationScheme).where(ClassificationScheme.is_active.is_(True))
            scheme = (await session.execute(stmt_fallback)).scalars().first()
        return scheme

    @staticmethod
    async def get_latest_version_for_scheme(
        session: AsyncSession, scheme_id: int
    ) -> Optional[ClassificationSchemeVersion]:
        stmt = (
            select(ClassificationSchemeVersion)
            .where(ClassificationSchemeVersion.scheme_id == scheme_id, ClassificationSchemeVersion.is_active.is_(True))
            .order_by(desc(ClassificationSchemeVersion.effective_from))
        )
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def get_version_by_code(
        session: AsyncSession, scheme_id: int, version_code: str
    ) -> Optional[ClassificationSchemeVersion]:
        stmt = select(ClassificationSchemeVersion).where(
            ClassificationSchemeVersion.scheme_id == scheme_id,
            ClassificationSchemeVersion.version_code == version_code,
        )
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def get_node_by_code(
        session: AsyncSession, scheme_id: int, scheme_version_id: int, node_code: str
    ) -> Optional[ClassificationNode]:
        stmt = select(ClassificationNode).where(
            ClassificationNode.scheme_id == scheme_id,
            ClassificationNode.scheme_version_id == scheme_version_id,
            ClassificationNode.node_code == node_code,
        )
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def get_node_by_id(
        session: AsyncSession, node_id: str
    ) -> Optional[ClassificationNode]:
        stmt = select(ClassificationNode).where(ClassificationNode.node_id == node_id)
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def list_sectors(
        session: AsyncSession, scheme_id: int, version_id: Optional[int] = None
    ) -> List[ClassificationNode]:
        stmt = select(ClassificationNode).where(
            ClassificationNode.scheme_id == scheme_id,
            ClassificationNode.node_type == "SECTOR",
            ClassificationNode.node_status == "ACTIVE",
        )
        if version_id:
            stmt = stmt.where(ClassificationNode.scheme_version_id == version_id)
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def list_industries_for_sector(
        session: AsyncSession, sector_node_id: str
    ) -> List[ClassificationNode]:
        stmt = select(ClassificationNode).where(
            ClassificationNode.parent_node_id == sector_node_id,
            ClassificationNode.node_type == "INDUSTRY",
            ClassificationNode.node_status == "ACTIVE",
        )
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get_active_classification(
        session: AsyncSession,
        instrument_id: str,
        scheme_id: int,
        as_of_valid_time: Optional[datetime] = None,
        as_of_transaction_time: Optional[datetime] = None,
    ) -> Optional[InstrumentClassificationAssignment]:
        """
        Bitemporal Point-In-Time resolution:
        Filters by valid_from <= as_of_valid_time < valid_to
        and recorded_at <= as_of_transaction_time.
        """
        v_time = as_of_valid_time or utc_now()
        t_time = as_of_transaction_time or utc_now()

        stmt = (
            select(InstrumentClassificationAssignment)
            .where(
                InstrumentClassificationAssignment.instrument_id == instrument_id,
                InstrumentClassificationAssignment.scheme_id == scheme_id,
                InstrumentClassificationAssignment.valid_from <= v_time,
                or_(
                    InstrumentClassificationAssignment.valid_to.is_(None),
                    InstrumentClassificationAssignment.valid_to > v_time,
                ),
                InstrumentClassificationAssignment.recorded_at <= t_time,
            )
            .order_by(desc(InstrumentClassificationAssignment.recorded_at))
        )
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def get_active_asset_category(
        session: AsyncSession,
        instrument_id: str,
        as_of_time: Optional[datetime] = None,
    ) -> Optional[InstrumentAssetCategoryAssignment]:
        t = as_of_time or utc_now()
        stmt = (
            select(InstrumentAssetCategoryAssignment)
            .where(
                InstrumentAssetCategoryAssignment.instrument_id == instrument_id,
                InstrumentAssetCategoryAssignment.valid_from <= t,
                or_(
                    InstrumentAssetCategoryAssignment.valid_to.is_(None),
                    InstrumentAssetCategoryAssignment.valid_to > t,
                ),
            )
            .order_by(desc(InstrumentAssetCategoryAssignment.recorded_at))
        )
        return (await session.execute(stmt)).scalars().first()

    @staticmethod
    async def list_classification_history(
        session: AsyncSession, instrument_id: str, scheme_id: Optional[int] = None
    ) -> List[InstrumentClassificationAssignment]:
        stmt = select(InstrumentClassificationAssignment).where(
            InstrumentClassificationAssignment.instrument_id == instrument_id
        )
        if scheme_id:
            stmt = stmt.where(InstrumentClassificationAssignment.scheme_id == scheme_id)
        stmt = stmt.order_by(desc(InstrumentClassificationAssignment.recorded_at))
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def get_coverage_metrics(session: AsyncSession) -> Dict[str, Any]:
        """Computes live classification coverage percentage across canonical active instruments."""
        total_active_inst = (
            await session.execute(
                select(func.count(Instrument.id)).where(Instrument.lifecycle_status == "ACTIVE")
            )
        ).scalar() or 0

        classified_count = (
            await session.execute(
                select(func.count(func.distinct(InstrumentClassificationAssignment.instrument_id)))
            )
        ).scalar() or 0

        industry_count = (
            await session.execute(
                select(func.count(func.distinct(InstrumentClassificationAssignment.instrument_id))).where(
                    InstrumentClassificationAssignment.industry_node_id.isnot(None)
                )
            )
        ).scalar() or 0

        category_count = (
            await session.execute(
                select(func.count(func.distinct(InstrumentAssetCategoryAssignment.instrument_id)))
            )
        ).scalar() or 0

        sector_pct = round((classified_count / total_active_inst * 100.0), 2) if total_active_inst > 0 else 0.0
        industry_pct = round((industry_count / total_active_inst * 100.0), 2) if total_active_inst > 0 else 0.0
        cat_pct = round((category_count / total_active_inst * 100.0), 2) if total_active_inst > 0 else 0.0

        return {
            "total_active_instruments": total_active_inst,
            "classified_instruments": classified_count,
            "sector_coverage_percentage": sector_pct,
            "industry_coverage_percentage": industry_pct,
            "asset_category_coverage_percentage": cat_pct,
            "conflicted_assignments_count": 0,
        }
