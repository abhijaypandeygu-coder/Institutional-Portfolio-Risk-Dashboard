"""
M13.09 - Historical Analytics Service.
Institutional orchestration service for querying and aligning authoritative historical records:
- M05.07 / M05.03 Portfolio History and Valuation Snapshots
- M07 Market Risk History (VaR, ES, Volatility, Drawdown)
- M06 Exposure History
- M05.05 Trades / M11 Breaches / M12 Alerts / M10 Scenarios (Event Overlays)
- Point-in-time historical reconstruction with bitemporal provenance manifests
- Downsampling for visualization (LTTB-style min/max preservation)
- User Preferences and Saved Views
"""

import math
import uuid
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, and_, or_, desc, asc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

# M05 Models
from backend.app.modules.portfolio_management.portfolio_history.models import (
    PortfolioBookSnapshot,
    HistoricalPositionSnapshot,
    HistoricalCashSnapshot,
    HistoricalValuationSnapshot,
    SnapshotSourceManifest,
    PortfolioChangeRecord,
)
from backend.app.modules.portfolio_management.position_valuation.models import (
    PortfolioValuationSnapshot,
    PositionValuation,
)
from backend.app.modules.portfolio_management.transaction_management.models import (
    Transaction,
    TransactionType,
    TradeSide,
)

# M07 Models
from backend.app.modules.market_risk.value_at_risk.models import VaRResult, VaRModelConfig
from backend.app.modules.market_risk.expected_shortfall.models import ExpectedShortfallResult
from backend.app.modules.market_risk.historical_volatility.models import HistoricalVolatilityResult
from backend.app.modules.market_risk.drawdown_analytics.models import DrawdownSeriesResult

# M11 & M12 Models
from backend.app.modules.risk_limits.breach_detection.models.breach_detection_models import BreachEvent
from backend.app.modules.risk_alerts.models.risk_alerts_models import AlertEvent

# M13.09 Local Models & Schemas
from backend.app.modules.dashboard_visualization.historical_analytics.models.historical_analytics_models import (
    HistoricalAnalyticsPreference,
    HistoricalAnalyticsSavedView,
    HistoricalAnalyticsAuditLog,
)
from backend.app.modules.dashboard_visualization.historical_analytics.schemas.historical_analytics_schemas import (
    HistoricalMode,
    ConsistencyStatus,
    HistoricalDataPoint,
    HistoricalPortfolioValueResponse,
    HistoricalPnLResponse,
    HistoricalRiskTrendResponse,
    HistoricalExposureResponse,
    EventOverlayItem,
    HistoricalEventsResponse,
    PointInTimePositionHolding,
    PointInTimeCashBalance,
    PointInTimeRiskMetrics,
    ProvenanceManifestResponse,
    PointInTimeStateResponse,
    HistoricalVersionComparisonResponse,
    HistoricalPreferenceResponse,
    HistoricalPreferenceUpdate,
    HistoricalSavedViewResponse,
    HistoricalSavedViewCreate,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HistoricalAnalyticsService:
    """
    Authoritative query and presentation service for Historical Analytics.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # -------------------------------------------------------------
    # 1. Historical Portfolio Values (M05.07 / M05.03)
    # -------------------------------------------------------------
    async def get_historical_portfolio_values(
        self,
        portfolio_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        metric: str = "NAV",
        frequency: str = "DAILY",
        historical_mode: HistoricalMode = HistoricalMode.AS_KNOWN_AT_TIME,
        downsample_limit: int = 500,
    ) -> HistoricalPortfolioValueResponse:
        """
        Retrieves authoritative NAV history from M05.07 PortfolioBookSnapshot or M05.03 PortfolioValuationSnapshot.
        """
        now = utc_now()
        if not end_time:
            end_time = now
        if not start_time:
            start_time = end_time - timedelta(days=90)

        # Query M05.07 PortfolioBookSnapshot
        query = select(PortfolioBookSnapshot).where(
            PortfolioBookSnapshot.portfolio_id == portfolio_id,
            PortfolioBookSnapshot.effective_as_of >= start_time,
            PortfolioBookSnapshot.effective_as_of <= end_time,
        )

        if historical_mode == HistoricalMode.AS_KNOWN_AT_TIME:
            query = query.where(PortfolioBookSnapshot.knowledge_as_of <= end_time)
            query = query.order_by(PortfolioBookSnapshot.effective_as_of.asc(), PortfolioBookSnapshot.knowledge_as_of.desc())
        else: # LATEST_RESTATED
            query = query.order_by(PortfolioBookSnapshot.effective_as_of.asc(), PortfolioBookSnapshot.snapshot_version.desc())

        result = await self.db.execute(query)
        snapshots = result.scalars().all()

        observations: List[HistoricalDataPoint] = []
        seen_effective = set()

        for s in snapshots:
            # If multiple snapshots exist for effective date, take the latest known/version
            eff_key = s.effective_as_of.date() if frequency == "DAILY" else s.effective_as_of
            if eff_key in seen_effective:
                continue
            seen_effective.add(eff_key)

            val = float(s.total_nav_base)
            observations.append(
                HistoricalDataPoint(
                    observation_id=f"NAV_{s.snapshot_id}",
                    portfolio_id=s.portfolio_id,
                    metric_name="NAV",
                    effective_at=s.effective_as_of,
                    known_at=s.knowledge_as_of,
                    calculated_at=s.created_at,
                    value=val,
                    currency=s.base_currency,
                    unit="CURRENCY",
                    frequency=s.snapshot_type,
                    source_module="M05.07_PORTFOLIO_HISTORY",
                    source_record_id=s.snapshot_id,
                    model_version=f"SNAP_V{s.snapshot_version}",
                    quality_status="VALID",
                    is_restated=s.is_restated,
                )
            )

        # Fallback to M05.03 PortfolioValuationSnapshot if M05.07 had no rows
        if not observations:
            val_query = select(PortfolioValuationSnapshot).where(
                PortfolioValuationSnapshot.portfolio_id == portfolio_id,
                PortfolioValuationSnapshot.valuation_timestamp >= start_time,
                PortfolioValuationSnapshot.valuation_timestamp <= end_time,
            ).order_by(PortfolioValuationSnapshot.valuation_timestamp.asc())
            val_res = await self.db.execute(val_query)
            val_snaps = val_res.scalars().all()

            for vs in val_snaps:
                val = float(vs.net_market_value)
                observations.append(
                    HistoricalDataPoint(
                        observation_id=f"VAL_{vs.snapshot_id}",
                        portfolio_id=vs.portfolio_id,
                        metric_name="NAV",
                        effective_at=vs.valuation_timestamp,
                        known_at=vs.created_at,
                        calculated_at=vs.created_at,
                        value=val,
                        currency=vs.base_currency,
                        unit="CURRENCY",
                        frequency="DAILY",
                        source_module="M05.03_POSITION_VALUATION",
                        source_record_id=vs.snapshot_id,
                        quality_status=str(vs.valuation_status),
                    )
                )

        # Downsample if observation count exceeds downsample_limit
        total_raw = len(observations)
        downsampled = False
        if total_raw > downsample_limit and downsample_limit > 10:
            observations = self._downsample_lttb(observations, downsample_limit)
            downsampled = True

        # Calculate Summary KPIs
        summary_kpis = self._compute_portfolio_value_kpis(observations)

        base_curr = observations[0].currency if observations else "USD"

        return HistoricalPortfolioValueResponse(
            portfolio_id=portfolio_id,
            metric=metric,
            currency=base_curr,
            frequency=frequency,
            historical_mode=historical_mode,
            start_time=start_time,
            end_time=end_time,
            observations=observations,
            summary_kpis=summary_kpis,
            downsampled=downsampled,
            total_raw_observations=total_raw,
        )

    # -------------------------------------------------------------
    # 2. Historical P&L (M05.03 / M05.07)
    # -------------------------------------------------------------
    async def get_historical_pnl(
        self,
        portfolio_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        pnl_type: str = "DAILY", # DAILY, CUMULATIVE, REALIZED, UNREALIZED
        frequency: str = "DAILY",
        historical_mode: HistoricalMode = HistoricalMode.AS_KNOWN_AT_TIME,
    ) -> HistoricalPnLResponse:
        """
        Retrieves authoritative historical P&L observations.
        """
        now = utc_now()
        if not end_time:
            end_time = now
        if not start_time:
            start_time = end_time - timedelta(days=90)

        # Fetch valuation snapshots
        val_query = select(PortfolioValuationSnapshot).where(
            PortfolioValuationSnapshot.portfolio_id == portfolio_id,
            PortfolioValuationSnapshot.valuation_timestamp >= start_time,
            PortfolioValuationSnapshot.valuation_timestamp <= end_time,
        ).order_by(PortfolioValuationSnapshot.valuation_timestamp.asc())
        val_res = await self.db.execute(val_query)
        val_snaps = val_res.scalars().all()

        observations: List[HistoricalDataPoint] = []
        running_cumulative = 0.0

        for vs in val_snaps:
            unrealized = float(vs.total_unrealized_pnl)
            realized = float(vs.realized_pnl_period)

            if pnl_type == "REALIZED":
                pnl_val = realized
            elif pnl_type == "UNREALIZED":
                pnl_val = unrealized
            elif pnl_type == "CUMULATIVE":
                running_cumulative += (realized + unrealized)
                pnl_val = running_cumulative
            else: # DAILY
                pnl_val = realized + unrealized

            observations.append(
                HistoricalDataPoint(
                    observation_id=f"PNL_{vs.snapshot_id}",
                    portfolio_id=vs.portfolio_id,
                    metric_name=f"{pnl_type}_PNL",
                    effective_at=vs.valuation_timestamp,
                    known_at=vs.created_at,
                    calculated_at=vs.created_at,
                    value=pnl_val,
                    currency=vs.base_currency,
                    unit="CURRENCY",
                    frequency=frequency,
                    source_module="M05.03_POSITION_VALUATION",
                    source_record_id=vs.snapshot_id,
                    quality_status=str(vs.valuation_status),
                )
            )

        summary_kpis = {
            "observation_count": len(observations),
            "total_pnl": sum(o.value for o in observations if o.value is not None) if pnl_type == "DAILY" else (observations[-1].value if observations else 0.0),
            "max_pnl": max((o.value for o in observations if o.value is not None), default=0.0),
            "min_pnl": min((o.value for o in observations if o.value is not None), default=0.0),
            "currency": observations[0].currency if observations else "USD",
        }

        return HistoricalPnLResponse(
            portfolio_id=portfolio_id,
            pnl_type=pnl_type,
            currency=summary_kpis["currency"],
            frequency=frequency,
            historical_mode=historical_mode,
            observations=observations,
            summary_kpis=summary_kpis,
        )

    # -------------------------------------------------------------
    # 3. Historical Risk Trends (M07 VaR, ES, Volatility, Drawdown)
    # -------------------------------------------------------------
    async def get_historical_risk_trends(
        self,
        portfolio_id: str,
        metric: str = "VAR", # VAR, ES, VOLATILITY, DRAWDOWN
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        confidence_level: Optional[float] = None,
        frequency: str = "DAILY",
        historical_mode: HistoricalMode = HistoricalMode.AS_KNOWN_AT_TIME,
    ) -> HistoricalRiskTrendResponse:
        """
        Retrieves authoritative historical risk observations from M07.
        """
        now = utc_now()
        if not end_time:
            end_time = now
        if not start_time:
            start_time = end_time - timedelta(days=90)

        start_date = start_time.date()
        end_date = end_time.date()

        observations: List[HistoricalDataPoint] = []
        unit = "CURRENCY"
        currency = "USD"

        if metric == "VAR":
            query = select(VaRResult).where(
                VaRResult.portfolio_id == portfolio_id,
                VaRResult.as_of_date >= start_date,
                VaRResult.as_of_date <= end_date,
            )
            if confidence_level:
                query = query.where(VaRResult.confidence_level == Decimal(str(confidence_level)))
            query = query.order_by(VaRResult.as_of_date.asc())
            res = await self.db.execute(query)
            rows = res.scalars().all()

            for r in rows:
                currency = r.reporting_currency
                dt = datetime.combine(r.as_of_date, datetime.min.time(), tzinfo=timezone.utc)
                observations.append(
                    HistoricalDataPoint(
                        observation_id=f"VAR_{r.result_id}",
                        portfolio_id=r.portfolio_id,
                        metric_name=f"VAR_{int(r.confidence_level * 100)}PCT_{r.holding_horizon_days}D",
                        effective_at=dt,
                        known_at=r.calculated_at,
                        calculated_at=r.calculated_at,
                        value=float(r.var_monetary_amount),
                        currency=r.reporting_currency,
                        unit="CURRENCY",
                        source_module="M07.02_VALUE_AT_RISK",
                        source_record_id=r.result_id,
                        model_version=f"{r.methodology.value}",
                        metadata={
                            "confidence_level": float(r.confidence_level),
                            "holding_horizon_days": r.holding_horizon_days,
                            "var_return_pct": float(r.var_return_percentage),
                        },
                    )
                )

        elif metric == "ES":
            query = select(ExpectedShortfallResult).where(
                ExpectedShortfallResult.portfolio_id == portfolio_id,
                ExpectedShortfallResult.as_of_date >= start_date,
                ExpectedShortfallResult.as_of_date <= end_date,
            ).order_by(ExpectedShortfallResult.as_of_date.asc())
            res = await self.db.execute(query)
            rows = res.scalars().all()

            for r in rows:
                currency = r.reporting_currency
                dt = datetime.combine(r.as_of_date, datetime.min.time(), tzinfo=timezone.utc)
                observations.append(
                    HistoricalDataPoint(
                        observation_id=f"ES_{r.result_id}",
                        portfolio_id=r.portfolio_id,
                        metric_name=f"ES_{int(r.confidence_level * 100)}PCT",
                        effective_at=dt,
                        known_at=r.created_at,
                        calculated_at=r.created_at,
                        value=float(r.es_monetary_amount),
                        currency=r.reporting_currency,
                        unit="CURRENCY",
                        source_module="M07.03_EXPECTED_SHORTFALL",
                        source_record_id=r.result_id,
                        model_version=r.methodology.value,
                    )
                )

        elif metric == "VOLATILITY":
            unit = "PERCENTAGE"
            query = select(HistoricalVolatilityResult).where(
                HistoricalVolatilityResult.portfolio_id == portfolio_id,
                HistoricalVolatilityResult.as_of_date >= start_date,
                HistoricalVolatilityResult.as_of_date <= end_date,
            ).order_by(HistoricalVolatilityResult.as_of_date.asc())
            res = await self.db.execute(query)
            rows = res.scalars().all()

            for r in rows:
                dt = datetime.combine(r.as_of_date, datetime.min.time(), tzinfo=timezone.utc)
                observations.append(
                    HistoricalDataPoint(
                        observation_id=f"VOL_{r.result_id}",
                        portfolio_id=r.portfolio_id,
                        metric_name="ANNUALIZED_VOLATILITY",
                        effective_at=dt,
                        known_at=r.created_at,
                        calculated_at=r.created_at,
                        value=float(r.annualized_volatility_pct),
                        unit="PERCENTAGE",
                        source_module="M07.01_HISTORICAL_VOLATILITY",
                        source_record_id=r.result_id,
                        model_version=r.estimator_type.value,
                    )
                )

        elif metric == "DRAWDOWN":
            unit = "PERCENTAGE"
            query = select(DrawdownSeriesResult).where(
                DrawdownSeriesResult.portfolio_id == portfolio_id,
                DrawdownSeriesResult.as_of_date >= start_date,
                DrawdownSeriesResult.as_of_date <= end_date,
            ).order_by(DrawdownSeriesResult.as_of_date.asc())
            res = await self.db.execute(query)
            rows = res.scalars().all()

            for r in rows:
                dt = datetime.combine(r.as_of_date, datetime.min.time(), tzinfo=timezone.utc)
                observations.append(
                    HistoricalDataPoint(
                        observation_id=f"DD_{r.result_id}",
                        portfolio_id=r.portfolio_id,
                        metric_name="CURRENT_DRAWDOWN",
                        effective_at=dt,
                        known_at=r.created_at,
                        calculated_at=r.created_at,
                        value=float(r.drawdown_pct), # preserves signed negative convention
                        unit="PERCENTAGE",
                        source_module="M07.04_DRAWDOWN_ANALYTICS",
                        source_record_id=r.result_id,
                    )
                )

        # Summary statistics
        values = [o.value for o in observations if o.value is not None]
        summary_stats = {
            "observation_count": len(values),
            "average": sum(values) / len(values) if values else 0.0,
            "max": max(values, default=0.0),
            "min": min(values, default=0.0),
            "latest": values[-1] if values else 0.0,
        }

        return HistoricalRiskTrendResponse(
            portfolio_id=portfolio_id,
            metric=metric,
            currency=currency if unit == "CURRENCY" else None,
            unit=unit,
            frequency=frequency,
            historical_mode=historical_mode,
            observations=observations,
            summary_statistics=summary_stats,
        )

    # -------------------------------------------------------------
    # 4. Historical Exposure Trends (M06)
    # -------------------------------------------------------------
    async def get_historical_exposure(
        self,
        portfolio_id: str,
        exposure_type: str = "GROSS", # GROSS, NET, LONG, SHORT
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> HistoricalExposureResponse:
        """
        Retrieves authoritative historical exposure from valuation snapshots.
        """
        now = utc_now()
        if not end_time:
            end_time = now
        if not start_time:
            start_time = end_time - timedelta(days=90)

        query = select(PortfolioValuationSnapshot).where(
            PortfolioValuationSnapshot.portfolio_id == portfolio_id,
            PortfolioValuationSnapshot.valuation_timestamp >= start_time,
            PortfolioValuationSnapshot.valuation_timestamp <= end_time,
        ).order_by(PortfolioValuationSnapshot.valuation_timestamp.asc())
        res = await self.db.execute(query)
        snaps = res.scalars().all()

        observations: List[HistoricalDataPoint] = []
        for s in snaps:
            long_val = float(s.gross_long_market_value)
            short_val = float(s.gross_short_market_value)

            if exposure_type == "GROSS":
                val = long_val + abs(short_val)
            elif exposure_type == "NET":
                val = float(s.net_market_value)
            elif exposure_type == "LONG":
                val = long_val
            else: # SHORT
                val = short_val

            observations.append(
                HistoricalDataPoint(
                    observation_id=f"EXP_{s.snapshot_id}",
                    portfolio_id=s.portfolio_id,
                    metric_name=f"{exposure_type}_EXPOSURE",
                    effective_at=s.valuation_timestamp,
                    known_at=s.created_at,
                    calculated_at=s.created_at,
                    value=val,
                    currency=s.base_currency,
                    unit="CURRENCY",
                    source_module="M06_EXPOSURE_VALUATION",
                    source_record_id=s.snapshot_id,
                )
            )

        values = [o.value for o in observations if o.value is not None]
        summary_stats = {
            "observation_count": len(values),
            "average": sum(values) / len(values) if values else 0.0,
            "max": max(values, default=0.0),
            "min": min(values, default=0.0),
            "latest": values[-1] if values else 0.0,
        }

        return HistoricalExposureResponse(
            portfolio_id=portfolio_id,
            exposure_type=exposure_type,
            currency=snaps[0].base_currency if snaps else "USD",
            unit="CURRENCY",
            observations=observations,
            summary_statistics=summary_stats,
        )

    # -------------------------------------------------------------
    # 5. Historical Event Overlays (M12, M11, M05.05, M05.07)
    # -------------------------------------------------------------
    async def get_historical_events(
        self,
        portfolio_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        severity: Optional[str] = None,
        instrument_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> HistoricalEventsResponse:
        """
        Gathers material historical events from authoritative upstream modules.
        """
        now = utc_now()
        if not end_time:
            end_time = now
        if not start_time:
            start_time = end_time - timedelta(days=90)

        events: List[EventOverlayItem] = []

        types_filter = [t.upper() for t in (event_types or ["ALERT", "BREACH", "TRADE", "CHANGE"])]

        # 1. Alerts (M12)
        if "ALERT" in types_filter or "ALERTS" in types_filter:
            alert_q = select(AlertEvent).where(
                AlertEvent.created_at >= start_time,
                AlertEvent.created_at <= end_time,
            )
            if portfolio_id:
                alert_q = alert_q.where(AlertEvent.portfolio_id == portfolio_id)
            if severity:
                alert_q = alert_q.where(AlertEvent.priority == severity)
            if instrument_id:
                alert_q = alert_q.where(AlertEvent.instrument_id == instrument_id)

            a_res = await self.db.execute(alert_q)
            for a in a_res.scalars().all():
                events.append(
                    EventOverlayItem(
                        event_id=f"EV_ALERT_{a.id}",
                        event_category="ALERT",
                        event_title=a.title,
                        event_description=a.description,
                        portfolio_id=a.portfolio_id,
                        instrument_id=a.instrument_id,
                        occurrence_time=a.first_seen_at or a.created_at,
                        detection_time=a.created_at,
                        severity=str(a.priority),
                        source_module=a.source_module or "M12_RISK_ALERTS",
                        source_record_id=a.id,
                    )
                )

        # 2. Limit Breaches (M11)
        if "BREACH" in types_filter or "BREACHES" in types_filter:
            breach_q = select(BreachEvent).where(
                BreachEvent.detected_at >= start_time,
                BreachEvent.detected_at <= end_time,
            )
            if portfolio_id:
                breach_q = breach_q.where(BreachEvent.portfolio_id == portfolio_id)
            if severity:
                breach_q = breach_q.where(BreachEvent.severity == severity)
            if instrument_id:
                breach_q = breach_q.where(BreachEvent.target_entity_id == instrument_id)

            b_res = await self.db.execute(breach_q)
            for b in b_res.scalars().all():
                events.append(
                    EventOverlayItem(
                        event_id=f"EV_BREACH_{b.id}",
                        event_category="BREACH",
                        event_title=f"Limit Breach: {b.risk_limit_id}",
                        event_description=f"Observed: {b.observed_value} vs Limit: {b.threshold_value}",
                        portfolio_id=b.portfolio_id,
                        instrument_id=b.target_entity_id if b.target_entity_type == "INSTRUMENT" else None,
                        occurrence_time=b.metric_timestamp or b.detected_at,
                        detection_time=b.detected_at,
                        severity=str(b.severity),
                        source_module="M11_RISK_LIMITS",
                        source_record_id=b.id,
                    )
                )

        # 3. Trades (M05.05)
        if "TRADE" in types_filter or "TRADES" in types_filter:
            trade_q = select(Transaction).where(
                Transaction.created_at >= start_time,
                Transaction.created_at <= end_time,
            )
            if portfolio_id:
                trade_q = trade_q.where(Transaction.portfolio_id == portfolio_id)
            if instrument_id:
                trade_q = trade_q.where(Transaction.instrument_id == instrument_id)

            t_res = await self.db.execute(trade_q)
            for t in t_res.scalars().all():
                events.append(
                    EventOverlayItem(
                        event_id=f"EV_TRADE_{t.transaction_id}",
                        event_category="TRADE",
                        event_title=f"Trade {t.trade_side.value if t.trade_side else t.transaction_type.value} {t.executed_quantity} {t.instrument_id or ''}",
                        event_description=f"Price: {t.average_execution_price} {t.transaction_currency}",
                        portfolio_id=t.portfolio_id,
                        instrument_id=t.instrument_id,
                        occurrence_time=t.first_execution_at or t.created_at,
                        detection_time=t.created_at,
                        source_module="M05.05_TRANSACTION_MANAGEMENT",
                        source_record_id=t.transaction_id,
                    )
                )

        # Sort all events chronologically
        events.sort(key=lambda x: x.occurrence_time, reverse=True)

        total_count = len(events)
        start_idx = (page - 1) * page_size
        paginated_events = events[start_idx : start_idx + page_size]

        return HistoricalEventsResponse(
            portfolio_id=portfolio_id,
            events=paginated_events,
            total_count=total_count,
            page=page,
            page_size=page_size,
        )

    # -------------------------------------------------------------
    # 6. Point-in-Time Historical State Reconstruction & Manifest
    # -------------------------------------------------------------
    async def reconstruct_point_in_time_state(
        self,
        portfolio_id: str,
        effective_at: datetime,
        known_at: Optional[datetime] = None,
        historical_mode: HistoricalMode = HistoricalMode.AS_KNOWN_AT_TIME,
    ) -> PointInTimeStateResponse:
        """
        Reconstructs what the system knew at a specific point in time using M05.07 bitemporal snapshots.
        """
        if not known_at:
            known_at = effective_at if historical_mode == HistoricalMode.AS_KNOWN_AT_TIME else utc_now()

        # Find best matching PortfolioBookSnapshot
        snap_q = select(PortfolioBookSnapshot).options(
            selectinload(PortfolioBookSnapshot.positions),
            selectinload(PortfolioBookSnapshot.cash_balances),
            selectinload(PortfolioBookSnapshot.source_manifests),
        ).where(
            PortfolioBookSnapshot.portfolio_id == portfolio_id,
            PortfolioBookSnapshot.effective_as_of <= effective_at,
        )

        if historical_mode == HistoricalMode.AS_KNOWN_AT_TIME:
            snap_q = snap_q.where(PortfolioBookSnapshot.knowledge_as_of <= known_at)
            snap_q = snap_q.order_by(
                PortfolioBookSnapshot.effective_as_of.desc(),
                PortfolioBookSnapshot.knowledge_as_of.desc(),
            )
        else:
            snap_q = snap_q.order_by(
                PortfolioBookSnapshot.effective_as_of.desc(),
                PortfolioBookSnapshot.snapshot_version.desc(),
            )

        snap_res = await self.db.execute(snap_q)
        snapshot = snap_res.scalars().first()

        positions_list: List[PointInTimePositionHolding] = []
        cash_list: List[PointInTimeCashBalance] = []
        base_currency = "USD"
        total_nav = 0.0
        total_mkt = 0.0
        total_cash = 0.0
        total_unrealized = 0.0
        snap_id = None
        source_modules = ["M05.07_PORTFOLIO_HISTORY"]
        consistency_status = ConsistencyStatus.CONSISTENT
        consistency_notes = None

        if snapshot:
            snap_id = snapshot.snapshot_id
            base_currency = snapshot.base_currency
            total_nav = float(snapshot.total_nav_base)
            total_mkt = float(snapshot.total_market_value_base)
            total_cash = float(snapshot.total_cash_value_base)

            for p in snapshot.positions:
                positions_list.append(
                    PointInTimePositionHolding(
                        instrument_id=p.instrument_id,
                        signed_quantity=float(p.net_signed_quantity),
                        market_price=float(p.market_price) if p.market_price else None,
                        market_value_base=float(p.market_value_base),
                        cost_basis_base=float(p.cost_basis_base),
                        unrealized_pnl_base=float(p.unrealized_pnl_base),
                        currency=p.currency,
                    )
                )
                total_unrealized += float(p.unrealized_pnl_base)

            for c in snapshot.cash_balances:
                cash_list.append(
                    PointInTimeCashBalance(
                        currency=c.currency,
                        settled_cash=float(c.settled_cash),
                        available_cash=float(c.available_cash),
                        available_cash_base=float(c.available_cash_base),
                    )
                )

            for sm in snapshot.source_manifests:
                if sm.source_module not in source_modules:
                    source_modules.append(sm.source_module)

            if snapshot.is_restated:
                consistency_status = ConsistencyStatus.RESTATED
                consistency_notes = snapshot.restatement_reason or "Snapshot marked restated"
        else:
            consistency_status = ConsistencyStatus.INCOMPLETE
            consistency_notes = f"No authoritative portfolio snapshot found at or prior to {effective_at.isoformat()}"

        # Retrieve Risk State at that date
        eff_date = effective_at.date()
        var_q = select(VaRResult).where(
            VaRResult.portfolio_id == portfolio_id,
            VaRResult.as_of_date <= eff_date,
        ).order_by(VaRResult.as_of_date.desc())
        var_res = await self.db.execute(var_q)
        latest_var = var_res.scalars().first()

        risk_metrics = None
        risk_calc_ids = []
        model_versions = {}

        if latest_var:
            risk_calc_ids.append(latest_var.result_id)
            model_versions["VAR"] = latest_var.methodology.value
            source_modules.append("M07.02_VALUE_AT_RISK")
            risk_metrics = PointInTimeRiskMetrics(
                var_99_1d=float(latest_var.var_monetary_amount),
                model_version=latest_var.methodology.value,
                calculation_timestamp=latest_var.calculated_at,
            )

        # Gather contemporaneous events around this timestamp (+/- 2 days)
        event_resp = await self.get_historical_events(
            portfolio_id=portfolio_id,
            start_time=effective_at - timedelta(days=2),
            end_time=effective_at + timedelta(days=1),
            page_size=20,
        )

        manifest = ProvenanceManifestResponse(
            manifest_id=f"MNF_{uuid.uuid4().hex[:12].upper()}",
            portfolio_id=portfolio_id,
            selected_effective_at=effective_at,
            selected_knowledge_at=known_at,
            historical_mode=historical_mode,
            position_snapshot_id=snap_id,
            risk_calculation_ids=risk_calc_ids,
            market_data_watermark=snapshot.snapshot_hash if snapshot else None,
            model_versions=model_versions,
            source_modules=source_modules,
            consistency_status=consistency_status,
            consistency_notes=consistency_notes,
            created_at=utc_now(),
        )

        # Audit log point-in-time reconstruction
        audit = HistoricalAnalyticsAuditLog(
            user_id="system_or_user",
            action_type="POINT_IN_TIME_RECONSTRUCT",
            portfolio_id=portfolio_id,
            effective_at=effective_at,
            knowledge_at=known_at,
            historical_mode=historical_mode.value,
            details={"snapshot_id": snap_id, "consistency": consistency_status.value},
        )
        self.db.add(audit)
        await self.db.commit()

        return PointInTimeStateResponse(
            portfolio_id=portfolio_id,
            effective_at=effective_at,
            known_at=known_at,
            historical_mode=historical_mode,
            base_currency=base_currency,
            total_nav_base=total_nav,
            total_market_value_base=total_mkt,
            total_cash_value_base=total_cash,
            total_unrealized_pnl_base=total_unrealized,
            positions=positions_list,
            cash_balances=cash_list,
            risk_metrics=risk_metrics,
            recent_events=event_resp.events,
            manifest=manifest,
        )

    # -------------------------------------------------------------
    # 7. Historical Version Comparison
    # -------------------------------------------------------------
    async def compare_historical_versions(
        self,
        portfolio_id: str,
        metric: str,
        effective_at: datetime,
        version_a_id: str,
        version_b_id: str,
    ) -> HistoricalVersionComparisonResponse:
        """
        Compares two historical calculation or snapshot versions without overwriting records.
        """
        # Example comparing two PortfolioBookSnapshots
        snap_a = await self.db.get(PortfolioBookSnapshot, version_a_id)
        snap_b = await self.db.get(PortfolioBookSnapshot, version_b_id)

        if not snap_a or not snap_b:
            return HistoricalVersionComparisonResponse(
                portfolio_id=portfolio_id,
                metric=metric,
                effective_at=effective_at,
                version_a_label=version_a_id,
                version_b_label=version_b_id,
                is_compatible=False,
                compatibility_warning="One or both snapshots could not be found.",
            )

        val_a = float(snap_a.total_nav_base)
        val_b = float(snap_b.total_nav_base)
        diff = val_b - val_a
        pct_diff = (diff / val_a * 100.0) if val_a != 0.0 else 0.0

        return HistoricalVersionComparisonResponse(
            portfolio_id=portfolio_id,
            metric=metric,
            effective_at=effective_at,
            version_a_label=f"Version {snap_a.snapshot_version} ({snap_a.snapshot_id})",
            version_a_value=val_a,
            version_a_timestamp=snap_a.knowledge_as_of,
            version_a_model_version=f"SNAP_V{snap_a.snapshot_version}",
            version_b_label=f"Version {snap_b.snapshot_version} ({snap_b.snapshot_id})",
            version_b_value=val_b,
            version_b_timestamp=snap_b.knowledge_as_of,
            version_b_model_version=f"SNAP_V{snap_b.snapshot_version}",
            absolute_difference=diff,
            percentage_difference=pct_diff,
            restatement_reason=snap_b.restatement_reason,
            is_compatible=True,
        )

    # -------------------------------------------------------------
    # 8. User Preferences & Saved Views
    # -------------------------------------------------------------
    async def get_or_create_user_preferences(
        self,
        user_id: str = "default_user",
        dashboard_name: Optional[str] = None,
    ) -> HistoricalPreferenceResponse:
        query = select(HistoricalAnalyticsPreference).where(
            HistoricalAnalyticsPreference.user_id == user_id
        ).order_by(HistoricalAnalyticsPreference.updated_at.desc())
        res = await self.db.execute(query)
        pref = res.scalars().first()

        if not pref:
            pref = HistoricalAnalyticsPreference(
                user_id=user_id,
                dashboard_name=dashboard_name or "Default Historical Analytics",
            )
            self.db.add(pref)
            await self.db.commit()
            await self.db.refresh(pref)

        return HistoricalPreferenceResponse(
            id=pref.id,
            user_id=pref.user_id,
            dashboard_name=pref.dashboard_name,
            default_portfolio_id=pref.default_portfolio_id,
            default_lookback_days=pref.default_lookback_days,
            default_frequency=pref.default_frequency,
            default_historical_mode=pref.default_historical_mode,
            default_timezone=pref.default_timezone,
            enabled_event_overlays=pref.enabled_event_overlays,
            downsample_threshold=pref.downsample_threshold,
            created_at=pref.created_at,
            updated_at=pref.updated_at,
        )

    async def update_user_preferences(
        self,
        update_data: HistoricalPreferenceUpdate,
        user_id: str = "default_user",
    ) -> HistoricalPreferenceResponse:
        query = select(HistoricalAnalyticsPreference).where(
            HistoricalAnalyticsPreference.user_id == user_id
        ).order_by(HistoricalAnalyticsPreference.updated_at.desc())
        res = await self.db.execute(query)
        pref = res.scalars().first()

        if not pref:
            pref = HistoricalAnalyticsPreference(user_id=user_id)
            self.db.add(pref)

        for k, v in update_data.model_dump(exclude_unset=True).items():
            setattr(pref, k, v)

        pref.updated_at = utc_now()
        await self.db.commit()
        await self.db.refresh(pref)

        return HistoricalPreferenceResponse(
            id=pref.id,
            user_id=pref.user_id,
            dashboard_name=pref.dashboard_name,
            default_portfolio_id=pref.default_portfolio_id,
            default_lookback_days=pref.default_lookback_days,
            default_frequency=pref.default_frequency,
            default_historical_mode=pref.default_historical_mode,
            default_timezone=pref.default_timezone,
            enabled_event_overlays=pref.enabled_event_overlays,
            downsample_threshold=pref.downsample_threshold,
            created_at=pref.created_at,
            updated_at=pref.updated_at,
        )

    async def list_saved_views(
        self,
        user_id: str = "default_user",
    ) -> List[HistoricalSavedViewResponse]:
        query = select(HistoricalAnalyticsSavedView).where(
            or_(
                HistoricalAnalyticsSavedView.user_id == user_id,
                HistoricalAnalyticsSavedView.is_public == True,
            )
        ).order_by(HistoricalAnalyticsSavedView.created_at.desc())
        res = await self.db.execute(query)
        views = res.scalars().all()

        return [
            HistoricalSavedViewResponse(
                id=v.id,
                user_id=v.user_id,
                view_name=v.view_name,
                description=v.description,
                portfolio_ids=v.portfolio_ids,
                start_time=v.start_time,
                end_time=v.end_time,
                frequency=v.frequency,
                historical_mode=v.historical_mode,
                selected_metrics=v.selected_metrics,
                event_overlay_filters=v.event_overlay_filters,
                is_public=v.is_public,
                created_at=v.created_at,
                updated_at=v.updated_at,
            )
            for v in views
        ]

    async def create_saved_view(
        self,
        payload: HistoricalSavedViewCreate,
        user_id: str = "default_user",
    ) -> HistoricalSavedViewResponse:
        view = HistoricalAnalyticsSavedView(
            user_id=user_id,
            view_name=payload.view_name,
            description=payload.description,
            portfolio_ids=payload.portfolio_ids,
            start_time=payload.start_time,
            end_time=payload.end_time,
            frequency=payload.frequency,
            historical_mode=payload.historical_mode,
            selected_metrics=payload.selected_metrics,
            event_overlay_filters=payload.event_overlay_filters,
            is_public=payload.is_public,
        )
        self.db.add(view)
        await self.db.commit()
        await self.db.refresh(view)

        return HistoricalSavedViewResponse(
            id=view.id,
            user_id=view.user_id,
            view_name=view.view_name,
            description=view.description,
            portfolio_ids=view.portfolio_ids,
            start_time=view.start_time,
            end_time=view.end_time,
            frequency=view.frequency,
            historical_mode=view.historical_mode,
            selected_metrics=view.selected_metrics,
            event_overlay_filters=view.event_overlay_filters,
            is_public=view.is_public,
            created_at=view.created_at,
            updated_at=view.updated_at,
        )

    # -------------------------------------------------------------
    # Helper: Downsampling (LTTB - Largest Triangle Three Buckets)
    # -------------------------------------------------------------
    def _downsample_lttb(self, data: List[HistoricalDataPoint], threshold: int) -> List[HistoricalDataPoint]:
        """
        Reduces number of points for chart rendering while preserving peaks, troughs, and visual fidelity.
        """
        if len(data) <= threshold or threshold <= 2:
            return data

        sampled: List[HistoricalDataPoint] = [data[0]]
        every = (len(data) - 2) / (threshold - 2)
        a = 0

        for i in range(threshold - 2):
            avg_x = 0.0
            avg_y = 0.0
            avg_range_start = int(math.floor((i + 1) * every)) + 1
            avg_range_end = int(math.floor((i + 2) * every)) + 1
            avg_range_end = min(avg_range_end, len(data))

            avg_range_length = avg_range_end - avg_range_start
            for j in range(avg_range_start, avg_range_end):
                avg_x += data[j].effective_at.timestamp()
                avg_y += (data[j].value or 0.0)

            if avg_range_length > 0:
                avg_x /= avg_range_length
                avg_y /= avg_range_length

            range_offs = int(math.floor(i * every)) + 1
            range_to = int(math.floor((i + 1) * every)) + 1

            point_a_x = data[a].effective_at.timestamp()
            point_a_y = data[a].value or 0.0

            max_area = -1.0
            next_a = range_offs

            for k in range(range_offs, min(range_to, len(data))):
                area = abs(
                    (point_a_x - avg_x) * ((data[k].value or 0.0) - point_a_y)
                    - (point_a_x - data[k].effective_at.timestamp()) * (avg_y - point_a_y)
                ) * 0.5
                if area > max_area:
                    max_area = area
                    next_a = k

            sampled.append(data[next_a])
            a = next_a

        sampled.append(data[-1])
        return sampled

    def _compute_portfolio_value_kpis(self, observations: List[HistoricalDataPoint]) -> Dict[str, Any]:
        if not observations:
            return {
                "observation_count": 0,
                "starting_nav": 0.0,
                "ending_nav": 0.0,
                "absolute_nav_change": 0.0,
                "percentage_nav_change": 0.0,
                "highest_nav": 0.0,
                "lowest_nav": 0.0,
            }

        valid_vals = [o.value for o in observations if o.value is not None]
        start_nav = valid_vals[0] if valid_vals else 0.0
        end_nav = valid_vals[-1] if valid_vals else 0.0
        abs_change = end_nav - start_nav
        pct_change = (abs_change / start_nav * 100.0) if start_nav != 0.0 else 0.0

        return {
            "observation_count": len(valid_vals),
            "starting_nav": start_nav,
            "ending_nav": end_nav,
            "absolute_nav_change": abs_change,
            "percentage_nav_change": pct_change,
            "highest_nav": max(valid_vals, default=0.0),
            "lowest_nav": min(valid_vals, default=0.0),
        }
