"""
M05.07 - Portfolio History Repository.
Data access layer for temporal snapshots, historical positions/cash, change timeline, and risk manifests.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Sequence
from sqlalchemy import select, and_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.modules.portfolio_management.portfolio_history.models import (
    PortfolioBookSnapshot,
    HistoricalPositionSnapshot,
    HistoricalCashSnapshot,
    HistoricalValuationSnapshot,
    SnapshotSourceManifest,
    PortfolioChangeRecord,
    RiskRunInputManifest,
)


class PortfolioHistoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ==========================================
    # Snapshot Persistence & Retrieval
    # ==========================================

    async def create_snapshot(self, snapshot: PortfolioBookSnapshot) -> PortfolioBookSnapshot:
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def get_snapshot_by_id(self, snapshot_id: str) -> Optional[PortfolioBookSnapshot]:
        stmt = (
            select(PortfolioBookSnapshot)
            .where(PortfolioBookSnapshot.snapshot_id == snapshot_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_snapshots_for_portfolio(
        self,
        portfolio_id: str,
        limit: int = 50,
    ) -> Sequence[PortfolioBookSnapshot]:
        stmt = (
            select(PortfolioBookSnapshot)
            .where(PortfolioBookSnapshot.portfolio_id == portfolio_id)
            .order_by(desc(PortfolioBookSnapshot.effective_as_of), desc(PortfolioBookSnapshot.knowledge_as_of))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def find_snapshot_bitemporal(
        self,
        portfolio_id: str,
        effective_as_of: datetime,
        knowledge_as_of: datetime,
    ) -> Optional[PortfolioBookSnapshot]:
        """
        Finds the most authoritative snapshot effective at or before `effective_as_of`
        and recorded at or before `knowledge_as_of`.
        """
        stmt = (
            select(PortfolioBookSnapshot)
            .where(
                and_(
                    PortfolioBookSnapshot.portfolio_id == portfolio_id,
                    PortfolioBookSnapshot.effective_as_of <= effective_as_of,
                    PortfolioBookSnapshot.knowledge_as_of <= knowledge_as_of,
                )
            )
            .order_by(
                desc(PortfolioBookSnapshot.effective_as_of),
                desc(PortfolioBookSnapshot.knowledge_as_of),
                desc(PortfolioBookSnapshot.snapshot_version),
            )
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_snapshot_positions(self, snapshot_id: str) -> Sequence[HistoricalPositionSnapshot]:
        stmt = (
            select(HistoricalPositionSnapshot)
            .where(HistoricalPositionSnapshot.snapshot_id == snapshot_id)
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_snapshot_cash(self, snapshot_id: str) -> Sequence[HistoricalCashSnapshot]:
        stmt = (
            select(HistoricalCashSnapshot)
            .where(HistoricalCashSnapshot.snapshot_id == snapshot_id)
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def get_snapshot_valuations(self, snapshot_id: str) -> Sequence[HistoricalValuationSnapshot]:
        stmt = (
            select(HistoricalValuationSnapshot)
            .where(HistoricalValuationSnapshot.snapshot_id == snapshot_id)
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    # ==========================================
    # Change Timeline Records
    # ==========================================

    async def add_change_record(self, record: PortfolioChangeRecord) -> PortfolioChangeRecord:
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_next_sequence_number(self, portfolio_id: str) -> int:
        stmt = (
            select(PortfolioChangeRecord.sequence_number)
            .where(PortfolioChangeRecord.portfolio_id == portfolio_id)
            .order_by(desc(PortfolioChangeRecord.sequence_number))
            .limit(1)
        )
        res = await self.session.execute(stmt)
        curr = res.scalar_one_or_none()
        return int(curr or 0) + 1

    async def get_change_timeline(
        self,
        portfolio_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        knowledge_cutoff: Optional[datetime] = None,
        instrument_id: Optional[str] = None,
        limit: int = 100,
    ) -> Sequence[PortfolioChangeRecord]:
        conditions = [PortfolioChangeRecord.portfolio_id == portfolio_id]
        if start_time:
            conditions.append(PortfolioChangeRecord.effective_at >= start_time)
        if end_time:
            conditions.append(PortfolioChangeRecord.effective_at <= end_time)
        if knowledge_cutoff:
            conditions.append(PortfolioChangeRecord.recorded_at <= knowledge_cutoff)
        if instrument_id:
            conditions.append(PortfolioChangeRecord.instrument_id == instrument_id)

        stmt = (
            select(PortfolioChangeRecord)
            .where(and_(*conditions))
            .order_by(asc(PortfolioChangeRecord.sequence_number))
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return res.scalars().all()

    # ==========================================
    # Risk Run Manifests
    # ==========================================

    async def create_risk_manifest(self, manifest: RiskRunInputManifest) -> RiskRunInputManifest:
        self.session.add(manifest)
        await self.session.flush()
        return manifest

    async def get_risk_manifest(self, manifest_id: str) -> Optional[RiskRunInputManifest]:
        stmt = select(RiskRunInputManifest).where(RiskRunInputManifest.manifest_id == manifest_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_risk_manifest_by_run_id(self, risk_run_id: str) -> Optional[RiskRunInputManifest]:
        stmt = select(RiskRunInputManifest).where(RiskRunInputManifest.risk_run_id == risk_run_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

