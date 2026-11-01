"""
M06.03 Sector Exposure Database Repository.
Persistence and querying of sector exposure policies, runs, sector/industry results,
unclassified holdings, coverage metrics, and benchmark compositions.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.risk_management.sector_exposure.models import (
    SectorExposurePolicy,
    SectorExposureCalculationRun,
    SectorExposureResult,
    IndustryExposureResult,
    UnclassifiedExposureResult,
    ClassificationCoverage,
    BenchmarkSectorComposition,
    RelativeSectorExposureResult,
)
from backend.app.modules.instrument_reference_data.security_classification.models import (
    ClassificationScheme,
    ClassificationSchemeVersion,
    ClassificationNode,
    InstrumentClassificationAssignment,
)


class SectorExposureRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_policy(self, policy: SectorExposurePolicy) -> SectorExposurePolicy:
        self.session.add(policy)
        await self.session.flush()
        return policy

    async def get_active_policy(
        self, portfolio_id: Optional[str] = None, group_id: Optional[str] = None
    ) -> Optional[SectorExposurePolicy]:
        stmt = select(SectorExposurePolicy)
        if portfolio_id:
            stmt = stmt.where(SectorExposurePolicy.portfolio_id == portfolio_id)
        elif group_id:
            stmt = stmt.where(SectorExposurePolicy.group_id == group_id)
        stmt = stmt.order_by(desc(SectorExposurePolicy.created_at))
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def save_run(self, run: SectorExposureCalculationRun) -> SectorExposureCalculationRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run_by_idempotency(self, key: str) -> Optional[SectorExposureCalculationRun]:
        stmt = select(SectorExposureCalculationRun).where(SectorExposureCalculationRun.idempotency_key == key)
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def save_results(
        self,
        sectors: List[SectorExposureResult],
        industries: List[IndustryExposureResult],
        unclassified: List[UnclassifiedExposureResult],
        coverage: ClassificationCoverage,
        relative_results: List[RelativeSectorExposureResult],
    ) -> None:
        self.session.add_all(sectors)
        self.session.add_all(industries)
        self.session.add_all(unclassified)
        self.session.add(coverage)
        self.session.add_all(relative_results)
        await self.session.flush()

    # M04.02 Integration: Resolve Classification Assignment
    async def get_instrument_classification(
        self, instrument_id: str, as_of: datetime, scheme_code: str = "GICS"
    ) -> Optional[tuple[InstrumentClassificationAssignment, ClassificationNode, Optional[ClassificationNode]]]:
        """
        Retrieves the effective bitemporal classification assignment and node names for an instrument.
        """
        # Join assignment with sector node and optional industry node
        stmt = (
            select(
                InstrumentClassificationAssignment,
                ClassificationNode,
            )
            .join(ClassificationScheme, ClassificationScheme.id == InstrumentClassificationAssignment.scheme_id)
            .join(ClassificationNode, ClassificationNode.node_id == InstrumentClassificationAssignment.sector_node_id)
            .where(
                InstrumentClassificationAssignment.instrument_id == instrument_id,
                ClassificationScheme.scheme_code == scheme_code,
            )
            .order_by(desc(InstrumentClassificationAssignment.assignment_version))
        )
        res = await self.session.execute(stmt)
        row = res.first()
        if not row:
            return None

        asn, sector_node = row
        industry_node = None
        if asn.industry_node_id:
            stmt_ind = select(ClassificationNode).where(ClassificationNode.node_id == asn.industry_node_id)
            res_ind = await self.session.execute(stmt_ind)
            industry_node = res_ind.scalars().first()

        return asn, sector_node, industry_node

    # Benchmark Sector Composition
    async def save_benchmark_composition(
        self, comp: BenchmarkSectorComposition
    ) -> BenchmarkSectorComposition:
        self.session.add(comp)
        await self.session.flush()
        return comp

    async def get_benchmark_compositions(
        self, benchmark_id: str, as_of: datetime
    ) -> List[BenchmarkSectorComposition]:
        stmt = (
            select(BenchmarkSectorComposition)
            .where(
                BenchmarkSectorComposition.benchmark_id == benchmark_id,
                BenchmarkSectorComposition.effective_date <= as_of,
            )
            .order_by(BenchmarkSectorComposition.sector_id.asc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
