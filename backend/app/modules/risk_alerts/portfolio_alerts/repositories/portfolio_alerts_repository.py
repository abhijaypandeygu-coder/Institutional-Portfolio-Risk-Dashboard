"""
Async SQLAlchemy repository for M12.04 Portfolio Alerts.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, desc, func
from sqlalchemy.orm import selectinload

from backend.app.modules.risk_alerts.portfolio_alerts.models.portfolio_alerts_models import (
    PortfolioAlertRule,
    PortfolioAlertRuleVersion,
    PortfolioAlertEvent,
    PortfolioAlertEvidence,
    PortfolioAlertOccurrence,
    PortfolioAlertBaseline,
    PortfolioAlertRuleEvaluation,
    PortfolioAlertReconciliationLink,
)


class PortfolioAlertsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------
    # Rule operations
    # -------------------------------------------------------------
    async def create_rule(self, rule: PortfolioAlertRule) -> PortfolioAlertRule:
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def get_rule_by_code(self, rule_code: str) -> Optional[PortfolioAlertRule]:
        stmt = (
            select(PortfolioAlertRule)
            .where(PortfolioAlertRule.rule_code == rule_code)
            .options(selectinload(PortfolioAlertRule.versions))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_rule_by_id(self, rule_id: str) -> Optional[PortfolioAlertRule]:
        stmt = (
            select(PortfolioAlertRule)
            .where(PortfolioAlertRule.id == rule_id)
            .options(selectinload(PortfolioAlertRule.versions))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_rules(
        self,
        portfolio_id: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[PortfolioAlertRule]:
        stmt = select(PortfolioAlertRule).options(selectinload(PortfolioAlertRule.versions))
        conditions = []
        if portfolio_id:
            conditions.append(PortfolioAlertRule.portfolio_id == portfolio_id)
        if category:
            conditions.append(PortfolioAlertRule.category == category)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(desc(PortfolioAlertRule.created_at))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -------------------------------------------------------------
    # Evaluation logging
    # -------------------------------------------------------------
    async def save_evaluation(self, eval_rec: PortfolioAlertRuleEvaluation) -> PortfolioAlertRuleEvaluation:
        self.session.add(eval_rec)
        await self.session.flush()
        return eval_rec

    # -------------------------------------------------------------
    # Portfolio Alert Events
    # -------------------------------------------------------------
    async def save_alert_event(self, event: PortfolioAlertEvent) -> PortfolioAlertEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_event_by_fingerprint(self, fingerprint: str) -> Optional[PortfolioAlertEvent]:
        stmt = (
            select(PortfolioAlertEvent)
            .where(and_(
                PortfolioAlertEvent.idempotency_key == fingerprint,
                PortfolioAlertEvent.event_state == "ACTIVE",
            ))
            .options(
                selectinload(PortfolioAlertEvent.evidence_items),
                selectinload(PortfolioAlertEvent.occurrences),
                selectinload(PortfolioAlertEvent.reconciliation_links),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_event_by_id(self, event_id: str) -> Optional[PortfolioAlertEvent]:
        stmt = (
            select(PortfolioAlertEvent)
            .where(PortfolioAlertEvent.id == event_id)
            .options(
                selectinload(PortfolioAlertEvent.evidence_items),
                selectinload(PortfolioAlertEvent.occurrences),
                selectinload(PortfolioAlertEvent.reconciliation_links),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_events(
        self,
        portfolio_id: Optional[str] = None,
        category: Optional[str] = None,
        event_state: Optional[str] = None,
        limit: int = 50,
    ) -> List[PortfolioAlertEvent]:
        stmt = (
            select(PortfolioAlertEvent)
            .options(selectinload(PortfolioAlertEvent.evidence_items))
        )
        conditions = []
        if portfolio_id:
            conditions.append(PortfolioAlertEvent.portfolio_id == portfolio_id)
        if category:
            conditions.append(PortfolioAlertEvent.category == category)
        if event_state:
            conditions.append(PortfolioAlertEvent.event_state == event_state)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(desc(PortfolioAlertEvent.detected_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -------------------------------------------------------------
    # Overview Summary Counts
    # -------------------------------------------------------------
    async def get_overview_counts(self, portfolio_id: Optional[str] = None) -> Dict[str, Any]:
        base_conds = []
        if portfolio_id:
            base_conds.append(PortfolioAlertEvent.portfolio_id == portfolio_id)

        # Total
        stmt_tot = select(func.count(PortfolioAlertEvent.id))
        if base_conds:
            stmt_tot = stmt_tot.where(and_(*base_conds))
        total_count = (await self.session.execute(stmt_tot)).scalar() or 0

        # Active
        stmt_active = select(func.count(PortfolioAlertEvent.id)).where(PortfolioAlertEvent.event_state == "ACTIVE")
        if base_conds:
            stmt_active = stmt_active.where(and_(*base_conds))
        active_count = (await self.session.execute(stmt_active)).scalar() or 0

        # Loss
        stmt_loss = select(func.count(PortfolioAlertEvent.id)).where(and_(
            PortfolioAlertEvent.category == "PORTFOLIO_LOSS",
            PortfolioAlertEvent.event_state == "ACTIVE",
            *base_conds
        ))
        loss_count = (await self.session.execute(stmt_loss)).scalar() or 0

        # Concentration
        stmt_conc = select(func.count(PortfolioAlertEvent.id)).where(and_(
            PortfolioAlertEvent.category == "CONCENTRATION",
            PortfolioAlertEvent.event_state == "ACTIVE",
            *base_conds
        ))
        conc_count = (await self.session.execute(stmt_conc)).scalar() or 0

        # Positions
        stmt_pos = select(func.count(PortfolioAlertEvent.id)).where(and_(
            PortfolioAlertEvent.category == "POSITION_MOVEMENT",
            PortfolioAlertEvent.event_state == "ACTIVE",
            *base_conds
        ))
        pos_count = (await self.session.execute(stmt_pos)).scalar() or 0

        # Cash
        stmt_cash = select(func.count(PortfolioAlertEvent.id)).where(and_(
            PortfolioAlertEvent.category == "CASH_MOVEMENT",
            PortfolioAlertEvent.event_state == "ACTIVE",
            *base_conds
        ))
        cash_count = (await self.session.execute(stmt_cash)).scalar() or 0

        # Reconciliation
        stmt_rec = select(func.count(PortfolioAlertEvent.id)).where(and_(
            PortfolioAlertEvent.category == "RECONCILIATION_BREAK",
            PortfolioAlertEvent.event_state == "ACTIVE",
            *base_conds
        ))
        rec_count = (await self.session.execute(stmt_rec)).scalar() or 0

        return {
            "portfolio_id": portfolio_id,
            "total_portfolio_alerts": total_count,
            "active_alerts": active_count,
            "loss_alerts_count": loss_count,
            "concentration_alerts_count": conc_count,
            "position_alerts_count": pos_count,
            "cash_alerts_count": cash_count,
            "reconciliation_alerts_count": rec_count,
        }

