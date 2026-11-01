"""
Module 03.01: Missing Data Detection - Missing Data Service Layer.
Coordinates detectors, policy evaluation, coverage calculation, and incident persistence.
"""
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Set, Union
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_data_quality.missing_data.coverage.calculator import CoverageCalculator
from backend.app.modules.market_data_quality.missing_data.detectors.candle_detector import MissingCandleDetector
from backend.app.modules.market_data_quality.missing_data.detectors.orderbook_detector import MissingOrderBookDetector
from backend.app.modules.market_data_quality.missing_data.detectors.tick_detector import MissingTickDetector
from backend.app.modules.market_data_quality.missing_data.incidents.repository import MissingDataRepository
from backend.app.modules.market_data_quality.missing_data.models import (
    CoverageWindow,
    ExpectedObservationPolicy,
    IncidentSeverity,
    IncidentStatus,
    MissingDataIncident,
)
from backend.app.modules.market_data_quality.missing_data.policies.resolver import ExpectationPolicyResolver
from backend.app.modules.market_data_quality.missing_data.schemas import (
    PolicyCreate,
    QualitySummaryResponse,
)


class MissingDataService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = MissingDataRepository(session)
        self.resolver = ExpectationPolicyResolver()
        self.tick_detector = MissingTickDetector(self.resolver)
        self.candle_detector = MissingCandleDetector(self.resolver)
        self.orderbook_detector = MissingOrderBookDetector(self.resolver)

    async def create_policy(self, payload: Union[PolicyCreate, dict]) -> ExpectedObservationPolicy:
        if isinstance(payload, dict):
            payload = PolicyCreate(**payload)
        policy = ExpectedObservationPolicy(
            policy_code=payload.policy_code,
            instrument_id=payload.instrument_id,
            exchange=payload.exchange,
            provider_id=payload.provider_id,
            feed_id=payload.feed_id,
            data_channel=payload.data_channel,
            observation_type=payload.observation_type,
            expected_frequency=payload.expected_frequency,
            grace_period_seconds=payload.grace_period_seconds,
            inactivity_threshold_seconds=payload.inactivity_threshold_seconds,
            policy_parameters=payload.policy_parameters,
            priority=payload.priority,
        )
        saved = await self.repo.create_policy(policy)
        await self.session.commit()
        return saved

    async def list_policies(self) -> List[ExpectedObservationPolicy]:
        return await self.repo.list_policies()

    # -------------------------------------------------------------------------
    # Detection Runners
    # -------------------------------------------------------------------------
    async def evaluate_tick_sequence_gap(
        self,
        feed_id: str,
        provider_id: str,
        instrument_id: str,
        exchange: str,
        expected_seq: int,
        observed_seq: int,
        channel: str = "TICK",
    ) -> Optional[MissingDataIncident]:
        incident = self.tick_detector.detect_sequence_gap(
            feed_id=feed_id,
            provider_id=provider_id,
            instrument_id=instrument_id,
            exchange=exchange,
            expected_seq=expected_seq,
            observed_seq=observed_seq,
            channel=channel,
        )
        if incident:
            saved = await self.repo.upsert_incident(incident)
            await self.session.commit()
            return saved
        return None

    async def evaluate_daily_candles(
        self,
        instrument_id: str,
        feed_id: str,
        provider_id: str,
        exchange: str,
        start_date: date,
        end_date: date,
        observed_dates: Set[date],
    ) -> List[MissingDataIncident]:
        incidents = self.candle_detector.detect_missing_daily_candles(
            instrument_id=instrument_id,
            feed_id=feed_id,
            provider_id=provider_id,
            exchange=exchange,
            start_date=start_date,
            end_date=end_date,
            observed_dates=observed_dates,
        )
        saved_list = []
        for inc in incidents:
            saved = await self.repo.upsert_incident(inc)
            saved_list.append(saved)
        await self.session.commit()
        return saved_list

    async def evaluate_order_book_health(
        self,
        instrument_id: str,
        feed_id: str,
        provider_id: str,
        exchange: str,
        is_synchronized: bool,
        last_sequence: int,
        last_update_timestamp: datetime,
    ) -> Optional[MissingDataIncident]:
        now = datetime.now(timezone.utc)
        incident = self.orderbook_detector.check_order_book_status(
            instrument_id=instrument_id,
            feed_id=feed_id,
            provider_id=provider_id,
            exchange=exchange,
            is_synchronized=is_synchronized,
            last_sequence=last_sequence,
            last_update_timestamp=last_update_timestamp,
            current_time=now,
        )
        if incident:
            saved = await self.repo.upsert_incident(incident)
            await self.session.commit()
            return saved
        return None

    async def calculate_and_record_coverage(
        self,
        instrument_id: str,
        feed_id: str,
        provider_id: str,
        exchange: str,
        data_type: str,
        interval_type: str,
        window_start: datetime,
        window_end: datetime,
        expected_units: int,
        observed_units: int,
    ) -> CoverageWindow:
        window = CoverageCalculator.calculate_coverage(
            instrument_id=instrument_id,
            feed_id=feed_id,
            provider_id=provider_id,
            exchange=exchange,
            data_type=data_type,
            interval_type=interval_type,
            window_start=window_start,
            window_end=window_end,
            expected_units=expected_units,
            observed_units=observed_units,
        )
        saved = await self.repo.save_coverage_window(window)
        await self.session.commit()
        return saved

    # -------------------------------------------------------------------------
    # Incident Management
    # -------------------------------------------------------------------------
    async def list_incidents(
        self,
        instrument_id: Optional[str] = None,
        issue_status: Optional[str] = None,
        limit: int = 100,
    ) -> List[MissingDataIncident]:
        return await self.repo.list_incidents(
            instrument_id=instrument_id,
            issue_status=issue_status,
            limit=limit,
        )

    async def resolve_incident(self, incident_id: UUID, reason: str) -> MissingDataIncident:
        resolved = await self.repo.resolve_incident(incident_id, reason)
        if not resolved:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found.")
        await self.session.commit()
        return resolved

    async def get_summary(self) -> QualitySummaryResponse:
        open_incidents = await self.repo.list_incidents(issue_status=IncidentStatus.OPEN.value)
        critical_count = sum(1 for i in open_incidents if i.severity == IncidentSeverity.CRITICAL.value)
        coverage_windows = await self.repo.list_coverage_windows(limit=20)
        avg_cov = 100.0
        if coverage_windows:
            avg_cov = round(sum(w.coverage_percentage for w in coverage_windows) / len(coverage_windows), 2)

        health = "HEALTHY"
        if critical_count > 0:
            health = "CRITICAL_GAPS"
        elif len(open_incidents) > 0:
            health = "WARNING_GAPS"

        return QualitySummaryResponse(
            open_incidents_count=len(open_incidents),
            critical_incidents_count=critical_count,
            recent_coverage_average=avg_cov,
            status=health,
        )
