"""
Async SQLAlchemy repository for M12.02 Market Alerts.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, desc, func
from sqlalchemy.orm import selectinload

from backend.app.modules.risk_alerts.market_alerts.models.market_alerts_models import (
    MarketAlertRule,
    MarketAlertRuleVersion,
    MarketEventObservation,
    MarketAlertEvaluation,
    MarketEvent,
    MarketEventEvidence,
    MarketEventStatusHistory,
    MarketHaltEvent,
    MarketWideEvent,
    MarketEventPortfolioImpact,
    MarketAlertReviewLabel,
    MarketDetectionProcessingLog,
)


class MarketAlertsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------
    # Rule operations
    # -------------------------------------------------------------
    async def create_rule(self, rule: MarketAlertRule) -> MarketAlertRule:
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def create_rule_version(self, version: MarketAlertRuleVersion) -> MarketAlertRuleVersion:
        self.session.add(version)
        await self.session.flush()
        return version

    async def get_rule_by_code(self, rule_code: str) -> Optional[MarketAlertRule]:
        stmt = (
            select(MarketAlertRule)
            .where(MarketAlertRule.rule_code == rule_code)
            .options(selectinload(MarketAlertRule.versions))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_rule_by_id(self, rule_id: str) -> Optional[MarketAlertRule]:
        stmt = (
            select(MarketAlertRule)
            .where(MarketAlertRule.id == rule_id)
            .options(selectinload(MarketAlertRule.versions))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_rules(
        self,
        rule_type: Optional[str] = None,
        market: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[MarketAlertRule]:
        stmt = select(MarketAlertRule).options(selectinload(MarketAlertRule.versions))
        conditions = []
        if rule_type:
            conditions.append(MarketAlertRule.rule_type == rule_type)
        if market:
            conditions.append(MarketAlertRule.market == market)
        if enabled_only:
            conditions.append(MarketAlertRule.enabled == True)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(desc(MarketAlertRule.created_at))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -------------------------------------------------------------
    # Evaluation & Observation
    # -------------------------------------------------------------
    async def save_observation(self, obs: MarketEventObservation) -> MarketEventObservation:
        self.session.add(obs)
        await self.session.flush()
        return obs

    async def save_evaluation(self, eval_rec: MarketAlertEvaluation) -> MarketAlertEvaluation:
        self.session.add(eval_rec)
        await self.session.flush()
        return eval_rec

    # -------------------------------------------------------------
    # Market Event operations
    # -------------------------------------------------------------
    async def save_market_event(self, event: MarketEvent) -> MarketEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_market_event_by_fingerprint(self, fingerprint: str) -> Optional[MarketEvent]:
        stmt = (
            select(MarketEvent)
            .where(and_(
                MarketEvent.event_fingerprint == fingerprint,
                MarketEvent.event_state.in_(["ACTIVE", "CONFIRMED", "RECOVERING"]),
            ))
            .options(
                selectinload(MarketEvent.evidence_items),
                selectinload(MarketEvent.portfolio_impacts),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_market_event_by_id(self, event_id: str) -> Optional[MarketEvent]:
        stmt = (
            select(MarketEvent)
            .where(MarketEvent.id == event_id)
            .options(
                selectinload(MarketEvent.evidence_items),
                selectinload(MarketEvent.portfolio_impacts),
                selectinload(MarketEvent.status_history),
                selectinload(MarketEvent.review_labels),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_market_events(
        self,
        event_type: Optional[str] = None,
        market: Optional[str] = None,
        exchange: Optional[str] = None,
        instrument_id: Optional[str] = None,
        event_state: Optional[str] = None,
        limit: int = 50,
    ) -> List[MarketEvent]:
        stmt = (
            select(MarketEvent)
            .options(
                selectinload(MarketEvent.evidence_items),
                selectinload(MarketEvent.portfolio_impacts),
            )
        )
        conditions = []
        if event_type:
            conditions.append(MarketEvent.event_type == event_type)
        if market:
            conditions.append(MarketEvent.market == market)
        if exchange:
            conditions.append(MarketEvent.exchange == exchange)
        if instrument_id:
            conditions.append(MarketEvent.instrument_id == instrument_id)
        if event_state:
            conditions.append(MarketEvent.event_state == event_state)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(desc(MarketEvent.detected_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -------------------------------------------------------------
    # Halts & Resumptions
    # -------------------------------------------------------------
    async def save_halt_event(self, halt: MarketHaltEvent) -> MarketHaltEvent:
        self.session.add(halt)
        await self.session.flush()
        return halt

    async def get_active_halt(self, instrument_id: str, exchange: str) -> Optional[MarketHaltEvent]:
        stmt = select(MarketHaltEvent).where(and_(
            MarketHaltEvent.instrument_id == instrument_id,
            MarketHaltEvent.exchange == exchange,
            MarketHaltEvent.normalized_status.in_(["HALTED", "SUSPENDED", "RESTRICTED", "AUCTION_ONLY"]),
            MarketHaltEvent.actual_resumption_timestamp.is_(None),
        )).order_by(desc(MarketHaltEvent.halt_start_timestamp))
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_halts(self, active_only: bool = True, limit: int = 50) -> List[MarketHaltEvent]:
        stmt = select(MarketHaltEvent)
        if active_only:
            stmt = stmt.where(MarketHaltEvent.actual_resumption_timestamp.is_(None))
        stmt = stmt.order_by(desc(MarketHaltEvent.halt_start_timestamp)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # -------------------------------------------------------------
    # Market-wide events
    # -------------------------------------------------------------
    async def save_market_wide_event(self, mwe: MarketWideEvent) -> MarketWideEvent:
        self.session.add(mwe)
        await self.session.flush()
        return mwe

    # -------------------------------------------------------------
    # Review labels & processing log
    # -------------------------------------------------------------
    async def add_review_label(self, label: MarketAlertReviewLabel) -> MarketAlertReviewLabel:
        self.session.add(label)
        await self.session.flush()
        return label

    async def save_processing_log(self, log_entry: MarketDetectionProcessingLog) -> MarketDetectionProcessingLog:
        self.session.add(log_entry)
        await self.session.flush()
        return log_entry

    # -------------------------------------------------------------
    # Overview aggregation
    # -------------------------------------------------------------
    async def get_overview_counts(self, market: str) -> Dict[str, Any]:
        # Count active events
        stmt_active = select(func.count(MarketEvent.id)).where(and_(
            MarketEvent.market == market,
            MarketEvent.event_state.in_(["ACTIVE", "CONFIRMED"]),
        ))
        active_count = (await self.session.execute(stmt_active)).scalar() or 0

        # Halts
        stmt_halts = select(func.count(MarketHaltEvent.id)).where(and_(
            MarketHaltEvent.actual_resumption_timestamp.is_(None),
        ))
        halts_count = (await self.session.execute(stmt_halts)).scalar() or 0

        # Volatility spikes
        stmt_vol = select(func.count(MarketEvent.id)).where(and_(
            MarketEvent.market == market,
            MarketEvent.event_type == "VOLATILITY_SPIKE",
            MarketEvent.event_state.in_(["ACTIVE", "CONFIRMED"]),
        ))
        vol_count = (await self.session.execute(stmt_vol)).scalar() or 0

        # Price anomalies
        stmt_price = select(func.count(MarketEvent.id)).where(and_(
            MarketEvent.market == market,
            MarketEvent.event_type.in_(["ABNORMAL_PRICE_MOVEMENT", "HISTORICAL_DEVIATION", "MARKET_BAND_BREACH"]),
            MarketEvent.event_state.in_(["ACTIVE", "CONFIRMED"]),
        ))
        price_count = (await self.session.execute(stmt_price)).scalar() or 0

        # Market-wide events
        stmt_mw = select(func.count(MarketEvent.id)).where(and_(
            MarketEvent.market == market,
            MarketEvent.event_type == "MARKET_WIDE_EVENT",
            MarketEvent.event_state.in_(["ACTIVE", "CONFIRMED"]),
        ))
        mw_count = (await self.session.execute(stmt_mw)).scalar() or 0

        return {
            "active_events_count": active_count,
            "halts_count": halts_count,
            "volatility_spikes_count": vol_count,
            "price_anomalies_count": price_count,
            "market_wide_events_count": mw_count,
        }

