"""
Async SQLAlchemy repository for M12.03 Liquidity Alerts.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, desc, func
from sqlalchemy.orm import selectinload

from backend.app.modules.risk_alerts.liquidity_alerts.models.liquidity_alerts_models import (
    LiquidityAlertRule,
    LiquidityAlertRuleVersion,
    LiquidityMetricObservation,
    LiquidityAlertEvaluation,
    LiquidityAlertEvent,
    LiquidityAlertEvidence,
    LiquidityDeteriorationState,
    LiquidityAlertPortfolioImpact,
    LiquidityAlertReviewLabel,
    LiquidityAlertProcessingLog,
)


class LiquidityAlertsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------
    # Rule operations
    # -------------------------------------------------------------
    async def create_rule(self, rule: LiquidityAlertRule) -> LiquidityAlertRule:
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def get_rule_by_code(self, rule_code: str) -> Optional[LiquidityAlertRule]:
        stmt = (
            select(LiquidityAlertRule)
            .where(LiquidityAlertRule.rule_code == rule_code)
            .options(selectinload(LiquidityAlertRule.versions))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_rule_by_id(self, rule_id: str) -> Optional[LiquidityAlertRule]:
        stmt = (
            select(LiquidityAlertRule)
            .where(LiquidityAlertRule.id == rule_id)
            .options(selectinload(LiquidityAlertRule.versions))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_rules(
        self,
        rule_type: Optional[str] = None,
        market: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[LiquidityAlertRule]:
        stmt = select(LiquidityAlertRule).options(selectinload(LiquidityAlertRule.versions))
        conditions = []
        if rule_type:
            conditions.append(LiquidityAlertRule.rule_type == rule_type)
        if market:
            conditions.append(LiquidityAlertRule.market == market)
        if enabled_only:
            conditions.append(LiquidityAlertRule.enabled == True)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(desc(LiquidityAlertRule.created_at))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -------------------------------------------------------------
    # Observations & Evaluations
    # -------------------------------------------------------------
    async def save_observation(self, obs: LiquidityMetricObservation) -> LiquidityMetricObservation:
        self.session.add(obs)
        await self.session.flush()
        return obs

    async def save_evaluation(self, eval_rec: LiquidityAlertEvaluation) -> LiquidityAlertEvaluation:
        self.session.add(eval_rec)
        await self.session.flush()
        return eval_rec

    # -------------------------------------------------------------
    # State tracking & persistence
    # -------------------------------------------------------------
    async def get_or_create_state(
        self,
        instrument_id: str,
        metric_type: str,
        metric_side: str = "BOTH",
    ) -> LiquidityDeteriorationState:
        stmt = select(LiquidityDeteriorationState).where(and_(
            LiquidityDeteriorationState.instrument_id == instrument_id,
            LiquidityDeteriorationState.metric_type == metric_type,
            LiquidityDeteriorationState.metric_side == metric_side,
        ))
        result = await self.session.execute(stmt)
        state = result.scalar_one_or_none()
        if not state:
            import uuid
            state = LiquidityDeteriorationState(
                id=f"LDS_{uuid.uuid4().hex[:12].upper()}",
                instrument_id=instrument_id,
                metric_type=metric_type,
                metric_side=metric_side,
                current_state="NORMAL",
            )
            self.session.add(state)
            await self.session.flush()
        return state

    # -------------------------------------------------------------
    # Liquidity Alert Events
    # -------------------------------------------------------------
    async def save_liquidity_event(self, event: LiquidityAlertEvent) -> LiquidityAlertEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_event_by_fingerprint(self, fingerprint: str) -> Optional[LiquidityAlertEvent]:
        stmt = (
            select(LiquidityAlertEvent)
            .where(and_(
                LiquidityAlertEvent.event_fingerprint == fingerprint,
                LiquidityAlertEvent.event_state.in_(["ACTIVE", "RECOVERING"]),
            ))
            .options(
                selectinload(LiquidityAlertEvent.evidence_items),
                selectinload(LiquidityAlertEvent.portfolio_impacts),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_event_by_id(self, event_id: str) -> Optional[LiquidityAlertEvent]:
        stmt = (
            select(LiquidityAlertEvent)
            .where(LiquidityAlertEvent.id == event_id)
            .options(
                selectinload(LiquidityAlertEvent.evidence_items),
                selectinload(LiquidityAlertEvent.portfolio_impacts),
                selectinload(LiquidityAlertEvent.review_labels),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_liquidity_events(
        self,
        event_type: Optional[str] = None,
        market: Optional[str] = None,
        instrument_id: Optional[str] = None,
        event_state: Optional[str] = None,
        limit: int = 50,
    ) -> List[LiquidityAlertEvent]:
        stmt = (
            select(LiquidityAlertEvent)
            .options(
                selectinload(LiquidityAlertEvent.evidence_items),
                selectinload(LiquidityAlertEvent.portfolio_impacts),
            )
        )
        conditions = []
        if event_type:
            conditions.append(LiquidityAlertEvent.event_type == event_type)
        if market:
            conditions.append(LiquidityAlertEvent.market == market)
        if instrument_id:
            conditions.append(LiquidityAlertEvent.instrument_id == instrument_id)
        if event_state:
            conditions.append(LiquidityAlertEvent.event_state == event_state)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(desc(LiquidityAlertEvent.detected_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -------------------------------------------------------------
    # Review & Logs
    # -------------------------------------------------------------
    async def add_review_label(self, label: LiquidityAlertReviewLabel) -> LiquidityAlertReviewLabel:
        self.session.add(label)
        await self.session.flush()
        return label

    async def save_processing_log(self, log_entry: LiquidityAlertProcessingLog) -> LiquidityAlertProcessingLog:
        self.session.add(log_entry)
        await self.session.flush()
        return log_entry

    # -------------------------------------------------------------
    # Overview Summary Counts
    # -------------------------------------------------------------
    async def get_overview_counts(self, market: str) -> Dict[str, Any]:
        stmt_active = select(func.count(LiquidityAlertEvent.id)).where(and_(
            LiquidityAlertEvent.market == market,
            LiquidityAlertEvent.event_state == "ACTIVE",
        ))
        active_count = (await self.session.execute(stmt_active)).scalar() or 0

        # Spread
        stmt_spread = select(func.count(LiquidityAlertEvent.id)).where(and_(
            LiquidityAlertEvent.market == market,
            LiquidityAlertEvent.event_type == "SPREAD_WIDENING",
            LiquidityAlertEvent.event_state == "ACTIVE",
        ))
        spread_count = (await self.session.execute(stmt_spread)).scalar() or 0

        # Depth
        stmt_depth = select(func.count(LiquidityAlertEvent.id)).where(and_(
            LiquidityAlertEvent.market == market,
            LiquidityAlertEvent.event_type == "DEPTH_DETERIORATION",
            LiquidityAlertEvent.event_state == "ACTIVE",
        ))
        depth_count = (await self.session.execute(stmt_depth)).scalar() or 0

        # Score
        stmt_score = select(func.count(LiquidityAlertEvent.id)).where(and_(
            LiquidityAlertEvent.market == market,
            LiquidityAlertEvent.event_type == "LOW_LIQUIDITY_SCORE",
            LiquidityAlertEvent.event_state == "ACTIVE",
        ))
        score_count = (await self.session.execute(stmt_score)).scalar() or 0

        # Liquidation Risk (Cost & Horizon)
        stmt_risk = select(func.count(LiquidityAlertEvent.id)).where(and_(
            LiquidityAlertEvent.market == market,
            LiquidityAlertEvent.event_type.in_(["EXCESS_LIQUIDATION_COST", "EXCESS_LIQUIDATION_HORIZON"]),
            LiquidityAlertEvent.event_state == "ACTIVE",
        ))
        risk_count = (await self.session.execute(stmt_risk)).scalar() or 0

        return {
            "active_liquidity_alerts_count": active_count,
            "spread_deterioration_count": spread_count,
            "depth_deterioration_count": depth_count,
            "score_deterioration_count": score_count,
            "liquidation_risk_count": risk_count,
        }
