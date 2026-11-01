"""Database repository for M05.01 - Portfolio Creation."""
import json
import uuid
from datetime import date, datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.portfolio_management.portfolio_creation.models import (
    Portfolio,
    PortfolioTypeEnum,
    PortfolioLifecycleStatus,
    PortfolioStrategy,
    PortfolioStrategyAssignment,
    PortfolioMandate,
    PortfolioMandateAssignment,
    PortfolioBenchmark,
    PortfolioOwnership,
    PortfolioHierarchy,
    PortfolioValuationSettings,
    PortfolioAccountingSettings,
    PortfolioLimit,
    PortfolioConfigurationVersion,
    PortfolioLifecycleEvent,
    PortfolioAuditEvent,
    HierarchyTypeEnum,
)


class PortfolioRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -----------------------------------------------------------------------
    # PORTFOLIO CRUD
    # -----------------------------------------------------------------------
    async def create_portfolio(self, portfolio: Portfolio) -> Portfolio:
        self.session.add(portfolio)
        await self.session.flush()
        return portfolio

    async def get_by_id(self, portfolio_id: str) -> Optional[Portfolio]:
        stmt = select(Portfolio).where(Portfolio.portfolio_id == portfolio_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_code(self, portfolio_code: str) -> Optional[Portfolio]:
        stmt = select(Portfolio).where(Portfolio.portfolio_code == portfolio_code)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_portfolios(
        self,
        status: Optional[PortfolioLifecycleStatus] = None,
        base_currency: Optional[str] = None,
        portfolio_type: Optional[PortfolioTypeEnum] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Portfolio]:
        stmt = select(Portfolio)
        if status:
            stmt = stmt.where(Portfolio.lifecycle_status == status)
        if base_currency:
            stmt = stmt.where(Portfolio.base_currency == base_currency)
        if portfolio_type:
            stmt = stmt.where(Portfolio.portfolio_type == portfolio_type)
        stmt = stmt.order_by(Portfolio.id.desc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # STRATEGY & MANDATE
    # -----------------------------------------------------------------------
    async def create_strategy(self, strategy: PortfolioStrategy) -> PortfolioStrategy:
        self.session.add(strategy)
        await self.session.flush()
        return strategy

    async def get_strategy_by_code(self, strategy_code: str) -> Optional[PortfolioStrategy]:
        stmt = select(PortfolioStrategy).where(PortfolioStrategy.strategy_code == strategy_code)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_strategies(self) -> List[PortfolioStrategy]:
        stmt = select(PortfolioStrategy).where(PortfolioStrategy.is_active == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def assign_strategy(self, assignment: PortfolioStrategyAssignment) -> PortfolioStrategyAssignment:
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def list_strategy_assignments(self, portfolio_id: str) -> List[PortfolioStrategyAssignment]:
        stmt = select(PortfolioStrategyAssignment).where(
            PortfolioStrategyAssignment.portfolio_id == portfolio_id
        ).order_by(PortfolioStrategyAssignment.effective_from.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_mandate(self, mandate: PortfolioMandate) -> PortfolioMandate:
        self.session.add(mandate)
        await self.session.flush()
        return mandate

    async def get_mandate_by_code(self, mandate_code: str) -> Optional[PortfolioMandate]:
        stmt = select(PortfolioMandate).where(PortfolioMandate.mandate_code == mandate_code)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_mandates(self) -> List[PortfolioMandate]:
        stmt = select(PortfolioMandate).where(PortfolioMandate.is_active == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def assign_mandate(self, assignment: PortfolioMandateAssignment) -> PortfolioMandateAssignment:
        self.session.add(assignment)
        await self.session.flush()
        return assignment

    async def list_mandate_assignments(self, portfolio_id: str) -> List[PortfolioMandateAssignment]:
        stmt = select(PortfolioMandateAssignment).where(
            PortfolioMandateAssignment.portfolio_id == portfolio_id
        ).order_by(PortfolioMandateAssignment.effective_from.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # BENCHMARKS
    # -----------------------------------------------------------------------
    async def add_benchmark(self, benchmark: PortfolioBenchmark) -> PortfolioBenchmark:
        self.session.add(benchmark)
        await self.session.flush()
        return benchmark

    async def list_benchmarks(self, portfolio_id: str) -> List[PortfolioBenchmark]:
        stmt = select(PortfolioBenchmark).where(
            PortfolioBenchmark.portfolio_id == portfolio_id
        ).order_by(PortfolioBenchmark.effective_from.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_benchmark_by_id(self, association_id: str) -> Optional[PortfolioBenchmark]:
        stmt = select(PortfolioBenchmark).where(PortfolioBenchmark.association_id == association_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # -----------------------------------------------------------------------
    # OWNERSHIP
    # -----------------------------------------------------------------------
    async def add_ownership(self, ownership: PortfolioOwnership) -> PortfolioOwnership:
        self.session.add(ownership)
        await self.session.flush()
        return ownership

    async def list_ownerships(self, portfolio_id: str) -> List[PortfolioOwnership]:
        stmt = select(PortfolioOwnership).where(
            PortfolioOwnership.portfolio_id == portfolio_id
        ).order_by(PortfolioOwnership.effective_from.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # HIERARCHY
    # -----------------------------------------------------------------------
    async def add_hierarchy_relationship(self, rel: PortfolioHierarchy) -> PortfolioHierarchy:
        self.session.add(rel)
        await self.session.flush()
        return rel

    async def list_child_relationships(self, parent_portfolio_id: str) -> List[PortfolioHierarchy]:
        stmt = select(PortfolioHierarchy).where(
            PortfolioHierarchy.parent_portfolio_id == parent_portfolio_id,
            PortfolioHierarchy.is_active == True,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_parent_relationships(self, child_portfolio_id: str) -> List[PortfolioHierarchy]:
        stmt = select(PortfolioHierarchy).where(
            PortfolioHierarchy.child_portfolio_id == child_portfolio_id,
            PortfolioHierarchy.is_active == True,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def check_cycle(self, parent_id: str, child_id: str) -> bool:
        """
        Defensively checks if making child_id a child of parent_id introduces a cycle.
        Returns True if a cycle would be introduced (i.e. parent is already a descendant of child).
        """
        if parent_id == child_id:
            return True

        visited = set()
        queue = [child_id]

        while queue:
            curr = queue.pop(0)
            if curr == parent_id:
                return True
            if curr in visited:
                continue
            visited.add(curr)

            children_rels = await self.list_child_relationships(curr)
            for r in children_rels:
                if r.child_portfolio_id not in visited:
                    queue.append(r.child_portfolio_id)

        return False

    # -----------------------------------------------------------------------
    # VALUATION & ACCOUNTING SETTINGS
    # -----------------------------------------------------------------------
    async def set_valuation_settings(self, settings: PortfolioValuationSettings) -> PortfolioValuationSettings:
        self.session.add(settings)
        await self.session.flush()
        return settings

    async def get_valuation_settings(self, portfolio_id: str) -> Optional[PortfolioValuationSettings]:
        stmt = select(PortfolioValuationSettings).where(
            PortfolioValuationSettings.portfolio_id == portfolio_id
        ).order_by(PortfolioValuationSettings.configuration_version.desc())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def set_accounting_settings(self, settings: PortfolioAccountingSettings) -> PortfolioAccountingSettings:
        self.session.add(settings)
        await self.session.flush()
        return settings

    async def get_accounting_settings(self, portfolio_id: str) -> Optional[PortfolioAccountingSettings]:
        stmt = select(PortfolioAccountingSettings).where(
            PortfolioAccountingSettings.portfolio_id == portfolio_id
        ).order_by(PortfolioAccountingSettings.policy_version.desc())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # -----------------------------------------------------------------------
    # LIMITS
    # -----------------------------------------------------------------------
    async def add_limit(self, limit_obj: PortfolioLimit) -> PortfolioLimit:
        self.session.add(limit_obj)
        await self.session.flush()
        return limit_obj

    async def get_limit_by_id(self, limit_id: str) -> Optional[PortfolioLimit]:
        stmt = select(PortfolioLimit).where(PortfolioLimit.limit_id == limit_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_limits(self, portfolio_id: str) -> List[PortfolioLimit]:
        stmt = select(PortfolioLimit).where(
            PortfolioLimit.portfolio_id == portfolio_id
        ).order_by(PortfolioLimit.effective_from.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # SNAPSHOTS, LIFECYCLE & AUDIT
    # -----------------------------------------------------------------------
    async def save_configuration_version(self, version: PortfolioConfigurationVersion) -> PortfolioConfigurationVersion:
        self.session.add(version)
        await self.session.flush()
        return version

    async def get_configuration_version(self, portfolio_id: str, version_number: int) -> Optional[PortfolioConfigurationVersion]:
        stmt = select(PortfolioConfigurationVersion).where(
            PortfolioConfigurationVersion.portfolio_id == portfolio_id,
            PortfolioConfigurationVersion.version_number == version_number,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_configuration_as_of(self, portfolio_id: str, as_of_date: date) -> Optional[PortfolioConfigurationVersion]:
        stmt = select(PortfolioConfigurationVersion).where(
            PortfolioConfigurationVersion.portfolio_id == portfolio_id,
            PortfolioConfigurationVersion.valid_from <= as_of_date,
            or_(
                PortfolioConfigurationVersion.valid_to == None,
                PortfolioConfigurationVersion.valid_to >= as_of_date,
            )
        ).order_by(PortfolioConfigurationVersion.version_number.desc())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def record_lifecycle_event(self, event: PortfolioLifecycleEvent) -> PortfolioLifecycleEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_lifecycle_events(self, portfolio_id: str) -> List[PortfolioLifecycleEvent]:
        stmt = select(PortfolioLifecycleEvent).where(
            PortfolioLifecycleEvent.portfolio_id == portfolio_id
        ).order_by(PortfolioLifecycleEvent.recorded_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def record_audit_event(self, audit: PortfolioAuditEvent) -> PortfolioAuditEvent:
        self.session.add(audit)
        await self.session.flush()
        return audit

    # -----------------------------------------------------------------------
    # METRICS
    # -----------------------------------------------------------------------
    async def get_operational_metrics(self) -> Dict[str, Any]:
        stmt_total = select(func.count(Portfolio.id))
        total = (await self.session.execute(stmt_total)).scalar_one()

        stmt_active = select(func.count(Portfolio.id)).where(Portfolio.lifecycle_status == PortfolioLifecycleStatus.ACTIVE)
        active = (await self.session.execute(stmt_active)).scalar_one()

        stmt_draft = select(func.count(Portfolio.id)).where(Portfolio.lifecycle_status == PortfolioLifecycleStatus.DRAFT)
        draft = (await self.session.execute(stmt_draft)).scalar_one()

        stmt_suspended = select(func.count(Portfolio.id)).where(Portfolio.lifecycle_status == PortfolioLifecycleStatus.SUSPENDED)
        suspended = (await self.session.execute(stmt_suspended)).scalar_one()

        stmt_closed = select(func.count(Portfolio.id)).where(Portfolio.lifecycle_status == PortfolioLifecycleStatus.CLOSED)
        closed = (await self.session.execute(stmt_closed)).scalar_one()

        # by currency
        stmt_curr = select(Portfolio.base_currency, func.count(Portfolio.id)).group_by(Portfolio.base_currency)
        curr_res = (await self.session.execute(stmt_curr)).all()
        portfolios_by_currency = {r[0]: r[1] for r in curr_res}

        # by type
        stmt_type = select(Portfolio.portfolio_type, func.count(Portfolio.id)).group_by(Portfolio.portfolio_type)
        type_res = (await self.session.execute(stmt_type)).all()
        portfolios_by_type = {r[0].value if hasattr(r[0], 'value') else str(r[0]): r[1] for r in type_res}

        # by market
        stmt_mkt = select(Portfolio.market_scope, func.count(Portfolio.id)).group_by(Portfolio.market_scope)
        mkt_res = (await self.session.execute(stmt_mkt)).all()
        portfolios_by_market = {r[0].value if hasattr(r[0], 'value') else str(r[0]): r[1] for r in mkt_res}

        return {
            "total_portfolios": total,
            "active_portfolios": active,
            "draft_portfolios": draft,
            "suspended_portfolios": suspended,
            "closed_portfolios": closed,
            "portfolios_by_currency": portfolios_by_currency,
            "portfolios_by_type": portfolios_by_type,
            "portfolios_by_market": portfolios_by_market,
        }

