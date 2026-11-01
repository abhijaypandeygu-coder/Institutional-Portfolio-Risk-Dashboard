"""
M06.08 Exposure Limits Service.

Core engine for configuring, evaluating, and monitoring risk limits across instruments,
sectors, industries, portfolio gross/net, countries, and regions.
Calculates utilization, headroom, warning/breach states, and records breach audit histories.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.risk_management.exposure_limits.models import (
    ExposureLimitConfig,
    ExposureLimitEvaluation,
    ExposureLimitBreachHistory,
    ExposureLimitCategory,
    ExposureMeasurementBasis,
    ExposureLimitDirection,
    ExposureLimitDenominatorType,
    ExposureLimitStatus,
    ExposureBreachEventType,
)
from backend.app.modules.risk_management.exposure_limits.schemas import (
    ExposureLimitConfigCreateRequest,
    ExposureLimitConfigResponse,
    ExposureLimitEvaluateRequest,
    ExposureLimitEvaluationItemResponse,
    ExposureLimitEvaluationSummaryResponse,
    ExposureLimitBreachHistoryItemResponse,
    ExposureLimitSimulateRequest,
    ExposureLimitSimulationResponse,
)
from backend.app.modules.risk_management.exposure_limits.repositories.repository import (
    ExposureLimitRepository,
)

# Upstream Authoritative Risk & Exposure Integrations
from backend.app.modules.risk_management.gross_exposure.services.service import (
    GrossExposureService,
)
from backend.app.modules.risk_management.net_exposure.services.service import (
    NetExposureService,
)
from backend.app.modules.risk_management.instrument_exposure.services.service import (
    InstrumentExposureService,
)
from backend.app.modules.risk_management.instrument_exposure.schemas import (
    InstrumentExposureCalculateRequest,
)
from backend.app.modules.risk_management.sector_exposure.services.service import (
    SectorExposureService,
)
from backend.app.modules.risk_management.sector_exposure.schemas import (
    SectorExposureCalculateRequest,
)
from backend.app.modules.risk_management.geographic_exposure.services.service import (
    GeographicExposureService,
)
from backend.app.modules.risk_management.geographic_exposure.schemas import (
    GeographicExposureCalculateRequest,
)
from backend.app.modules.portfolio_management.multi_portfolio_management.services.service import (
    MultiPortfolioService,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExposureLimitService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ExposureLimitRepository(session)
        self.inst_exp_svc = InstrumentExposureService(session)
        self.sector_exp_svc = SectorExposureService(session)
        self.geo_exp_svc = GeographicExposureService(session)
        self.gross_exp_svc = GrossExposureService(session)
        self.net_exp_svc = NetExposureService(session)
        self.multi_port_svc = MultiPortfolioService(session)

    async def create_limit_config(
        self, req: ExposureLimitConfigCreateRequest
    ) -> ExposureLimitConfigResponse:
        """
        Creates an effective-dated exposure limit configuration rule.
        """
        cfg = ExposureLimitConfig(
            limit_code=req.limit_code,
            limit_name=req.limit_name,
            limit_category=req.limit_category,
            portfolio_id=req.portfolio_id,
            portfolio_group_id=req.portfolio_group_id,
            target_entity_id=req.target_entity_id,
            target_entity_name=req.target_entity_name,
            exposure_basis=req.exposure_basis,
            limit_direction=req.limit_direction,
            denominator_type=req.denominator_type,
            limit_value=req.limit_value,
            warning_threshold_ratio=req.warning_threshold_ratio,
            severe_breach_threshold_ratio=req.severe_breach_threshold_ratio,
            reporting_currency=req.reporting_currency,
            is_active=True,
            policy_version=req.policy_version,
            effective_from=utc_now(),
        )
        await self.repo.create_limit_config(cfg)
        return ExposureLimitConfigResponse.model_validate(cfg)

    async def evaluate_limits(
        self, req: ExposureLimitEvaluateRequest
    ) -> ExposureLimitEvaluationSummaryResponse:
        """
        Evaluates all active configured limits against authoritative upstream exposure results.
        Computes utilization percentage, remaining headroom/shortfall, determines breach severity,
        and records breach transition history.
        """
        active_limits = await self.repo.list_active_limit_configs(
            portfolio_id=req.portfolio_id,
            portfolio_group_id=req.portfolio_group_id,
        )

        # 1. Preload upstream exposure measurements
        inst_summary = None
        sec_summary = None
        geo_summary = None

        inst_req = InstrumentExposureCalculateRequest(
            portfolio_id=req.portfolio_id,
            portfolio_group_id=req.portfolio_group_id,
            as_of=req.as_of_date,
            reporting_currency=req.reporting_currency,
        )
        if req.portfolio_group_id:
            inst_summary = await self.inst_exp_svc.calculate_group_instrument_exposure(
                req.portfolio_group_id, inst_req
            )
        else:
            inst_summary = await self.inst_exp_svc.calculate_portfolio_instrument_exposure(
                req.portfolio_id or "", inst_req
            )

        # Build quick lookups from instrument exposure
        inst_map = {item.instrument_id: item for item in (inst_summary.instruments or [])}
        total_nav = inst_summary.nav if inst_summary.nav > Decimal("0.0") else inst_summary.total_gross_exposure
        total_gross = inst_summary.total_gross_exposure
        total_long = inst_summary.total_long_exposure
        total_short = inst_summary.total_short_exposure
        total_net = inst_summary.total_net_exposure

        eval_records: List[ExposureLimitEvaluation] = []
        within_c = 0
        warning_c = 0
        breached_c = 0
        severe_c = 0
        unavail_c = 0

        for limit in active_limits:
            measured_exp = Decimal("0.0")
            den_val = Decimal("1.0")
            status = ExposureLimitStatus.WITHIN_LIMIT
            completeness = "COMPLETE"

            # A. Resolve Denominator
            if limit.denominator_type == ExposureLimitDenominatorType.PORTFOLIO_NAV:
                den_val = total_nav
            elif limit.denominator_type == ExposureLimitDenominatorType.PORTFOLIO_GROSS_EXPOSURE:
                den_val = total_gross
            elif limit.denominator_type == ExposureLimitDenominatorType.PORTFOLIO_LONG_EXPOSURE:
                den_val = total_long
            elif limit.denominator_type == ExposureLimitDenominatorType.PORTFOLIO_SHORT_EXPOSURE:
                den_val = total_short
            else:
                den_val = Decimal("1.0")  # Absolute amount

            if limit.denominator_type != ExposureLimitDenominatorType.ABSOLUTE_AMOUNT and den_val == Decimal("0.0"):
                status = ExposureLimitStatus.EVALUATION_UNAVAILABLE
                unavail_c += 1
                eval_entry = ExposureLimitEvaluation(
                    limit_id=limit.limit_id,
                    portfolio_id=req.portfolio_id,
                    portfolio_group_id=req.portfolio_group_id,
                    snapshot_id=req.snapshot_id,
                    measured_exposure=Decimal("0.0"),
                    denominator_value=Decimal("0.0"),
                    limit_value=limit.limit_value,
                    utilization_percentage=Decimal("0.0"),
                    headroom=Decimal("0.0"),
                    shortfall=Decimal("0.0"),
                    status=status,
                    data_completeness_status="DENOMINATOR_UNAVAILABLE",
                    evaluated_at=utc_now(),
                )
                eval_records.append(eval_entry)
                continue

            # B. Resolve Measured Exposure by Category
            if limit.limit_category == ExposureLimitCategory.INSTRUMENT_LIMIT:
                item = inst_map.get(limit.target_entity_id)
                if not item:
                    measured_exp = Decimal("0.0")
                else:
                    if limit.exposure_basis == ExposureMeasurementBasis.LONG_MARKET_VALUE:
                        measured_exp = item.long_market_value
                    elif limit.exposure_basis == ExposureMeasurementBasis.SHORT_MARKET_VALUE:
                        measured_exp = item.short_market_value
                    elif limit.exposure_basis == ExposureMeasurementBasis.NET_MARKET_VALUE:
                        measured_exp = item.net_market_value
                    elif limit.exposure_basis == ExposureMeasurementBasis.ABSOLUTE_NET_MARKET_VALUE:
                        measured_exp = abs(item.net_market_value)
                    elif limit.exposure_basis == ExposureMeasurementBasis.NAV_PERCENTAGE:
                        measured_exp = (item.gross_market_value / total_nav) if total_nav > 0 else Decimal("0.0")
                    else:
                        measured_exp = item.gross_market_value

            elif limit.limit_category in (ExposureLimitCategory.SECTOR_LIMIT, ExposureLimitCategory.INDUSTRY_LIMIT):
                if sec_summary is None:
                    sec_req = SectorExposureCalculateRequest(
                        portfolio_id=req.portfolio_id,
                        portfolio_group_id=req.portfolio_group_id,
                        as_of=req.as_of_date,
                        reporting_currency=req.reporting_currency,
                    )
                    if req.portfolio_group_id:
                        sec_summary = await self.sector_exp_svc.calculate_group_sector_exposure(
                            req.portfolio_group_id, sec_req
                        )
                    else:
                        sec_summary = await self.sector_exp_svc.calculate_portfolio_sector_exposure(
                            req.portfolio_id or "", sec_req
                        )

                target_list = sec_summary.sectors if limit.limit_category == ExposureLimitCategory.SECTOR_LIMIT else sec_summary.industries
                match_item = next((s for s in target_list if (getattr(s, "sector_code", None) == limit.target_entity_id or getattr(s, "industry_code", None) == limit.target_entity_id)), None)
                if match_item:
                    if limit.exposure_basis == ExposureMeasurementBasis.LONG_MARKET_VALUE:
                        measured_exp = match_item.long_exposure
                    elif limit.exposure_basis == ExposureMeasurementBasis.SHORT_MARKET_VALUE:
                        measured_exp = match_item.short_exposure
                    elif limit.exposure_basis == ExposureMeasurementBasis.NET_MARKET_VALUE:
                        measured_exp = match_item.net_exposure
                    elif limit.exposure_basis == ExposureMeasurementBasis.NAV_PERCENTAGE:
                        measured_exp = (match_item.gross_exposure / total_nav) if total_nav > 0 else Decimal("0.0")
                    else:
                        measured_exp = match_item.gross_exposure
                else:
                    measured_exp = Decimal("0.0")

            elif limit.limit_category == ExposureLimitCategory.PORTFOLIO_GROSS_LIMIT:
                if limit.exposure_basis == ExposureMeasurementBasis.NAV_PERCENTAGE:
                    measured_exp = (total_gross / total_nav) if total_nav > 0 else Decimal("0.0")
                else:
                    measured_exp = total_gross

            elif limit.limit_category == ExposureLimitCategory.PORTFOLIO_NET_LIMIT:
                if limit.exposure_basis == ExposureMeasurementBasis.NAV_PERCENTAGE:
                    measured_exp = (total_net / total_nav) if total_nav > 0 else Decimal("0.0")
                elif limit.exposure_basis == ExposureMeasurementBasis.ABSOLUTE_NET_MARKET_VALUE:
                    measured_exp = abs(total_net)
                else:
                    measured_exp = total_net

            elif limit.limit_category in (ExposureLimitCategory.COUNTRY_LIMIT, ExposureLimitCategory.REGION_LIMIT):
                if geo_summary is None:
                    geo_req = GeographicExposureCalculateRequest(
                        portfolio_id=req.portfolio_id,
                        portfolio_group_id=req.portfolio_group_id,
                        as_of=req.as_of_date,
                        reporting_currency=req.reporting_currency,
                    )
                    if req.portfolio_group_id:
                        geo_summary = await self.geo_exp_svc.calculate_group_geographic_exposure(
                            req.portfolio_group_id, geo_req
                        )
                    else:
                        geo_summary = await self.geo_exp_svc.calculate_portfolio_geographic_exposure(
                            req.portfolio_id or "", geo_req
                        )

                target_list = geo_summary.countries if limit.limit_category == ExposureLimitCategory.COUNTRY_LIMIT else geo_summary.regions
                match_item = next((g for g in target_list if (getattr(g, "country_iso3", None) == limit.target_entity_id or getattr(g, "region_code", None) == limit.target_entity_id)), None)
                if match_item:
                    if limit.exposure_basis == ExposureMeasurementBasis.LONG_MARKET_VALUE:
                        measured_exp = match_item.long_exposure
                    elif limit.exposure_basis == ExposureMeasurementBasis.SHORT_MARKET_VALUE:
                        measured_exp = match_item.short_exposure
                    elif limit.exposure_basis == ExposureMeasurementBasis.NAV_PERCENTAGE:
                        measured_exp = (match_item.gross_exposure / total_nav) if total_nav > 0 else Decimal("0.0")
                    else:
                        measured_exp = match_item.gross_exposure
                else:
                    measured_exp = Decimal("0.0")

            # C. Calculate Utilization and Headroom
            utilization = Decimal("0.0")
            headroom = Decimal("0.0")
            shortfall = Decimal("0.0")

            if limit.limit_value == Decimal("0.0"):
                # Zero Limit edge-case: any positive measured exposure is a breach
                if measured_exp > Decimal("0.0"):
                    status = ExposureLimitStatus.ZERO_LIMIT_BREACH
                    breached_c += 1
                else:
                    status = ExposureLimitStatus.WITHIN_LIMIT
                    within_c += 1
                headroom = -measured_exp
            else:
                utilization = ((measured_exp / limit.limit_value) * Decimal("100.0")).quantize(
                    Decimal("0.000001"), rounding=ROUND_HALF_UP
                )
                headroom = (limit.limit_value - measured_exp).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
                shortfall = (measured_exp - limit.limit_value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

                # Status Evaluation based on thresholds
                util_ratio = (measured_exp / limit.limit_value)
                if util_ratio >= limit.severe_breach_threshold_ratio:
                    status = ExposureLimitStatus.SEVERELY_BREACHED
                    severe_c += 1
                elif util_ratio > Decimal("1.0"):
                    status = ExposureLimitStatus.BREACHED
                    breached_c += 1
                elif util_ratio >= limit.warning_threshold_ratio:
                    status = ExposureLimitStatus.WARNING
                    warning_c += 1
                elif util_ratio >= (limit.warning_threshold_ratio * Decimal("0.90")):
                    status = ExposureLimitStatus.APPROACHING_LIMIT
                    within_c += 1
                else:
                    status = ExposureLimitStatus.WITHIN_LIMIT
                    within_c += 1

            eval_entry = ExposureLimitEvaluation(
                limit_id=limit.limit_id,
                portfolio_id=req.portfolio_id,
                portfolio_group_id=req.portfolio_group_id,
                snapshot_id=req.snapshot_id,
                measured_exposure=measured_exp,
                denominator_value=den_val,
                limit_value=limit.limit_value,
                utilization_percentage=utilization,
                headroom=headroom,
                shortfall=shortfall,
                status=status,
                data_completeness_status=completeness,
                source_reference=limit.target_entity_id,
                evaluated_at=utc_now(),
            )
            eval_records.append(eval_entry)

            # Check status transition against prior evaluation or initial breach/warning
            prior_eval = await self.repo.get_latest_evaluation(limit.limit_id)
            if prior_eval is None and status in (
                ExposureLimitStatus.BREACHED,
                ExposureLimitStatus.SEVERELY_BREACHED,
                ExposureLimitStatus.ZERO_LIMIT_BREACH,
                ExposureLimitStatus.WARNING,
            ):
                event_type = (
                    ExposureBreachEventType.NEW_WARNING
                    if status == ExposureLimitStatus.WARNING
                    else ExposureBreachEventType.NEW_BREACH
                )
                breach_evt = ExposureLimitBreachHistory(
                    limit_id=limit.limit_id,
                    portfolio_id=req.portfolio_id,
                    target_entity_id=limit.target_entity_id,
                    previous_status=None,
                    new_status=status,
                    event_type=event_type,
                    measured_exposure=measured_exp,
                    limit_value=limit.limit_value,
                    headroom=headroom,
                    details=f"Initial evaluation resulted in {status.value}",
                    recorded_at=utc_now(),
                )
                await self.repo.create_breach_event(breach_evt)
            elif prior_eval and prior_eval.status != status:
                event_type = ExposureBreachEventType.NEW_BREACH
                if status in (ExposureLimitStatus.BREACHED, ExposureLimitStatus.SEVERELY_BREACHED, ExposureLimitStatus.ZERO_LIMIT_BREACH):
                    event_type = ExposureBreachEventType.NEW_BREACH if prior_eval.status not in (ExposureLimitStatus.BREACHED, ExposureLimitStatus.SEVERELY_BREACHED) else ExposureBreachEventType.BREACH_WORSENED
                elif status == ExposureLimitStatus.WITHIN_LIMIT and prior_eval.status in (ExposureLimitStatus.BREACHED, ExposureLimitStatus.SEVERELY_BREACHED):
                    event_type = ExposureBreachEventType.BREACH_RESOLVED
                elif status == ExposureLimitStatus.WARNING:
                    event_type = ExposureBreachEventType.NEW_WARNING
                elif status == ExposureLimitStatus.WITHIN_LIMIT and prior_eval.status == ExposureLimitStatus.WARNING:
                    event_type = ExposureBreachEventType.WARNING_RESOLVED

                breach_evt = ExposureLimitBreachHistory(
                    limit_id=limit.limit_id,
                    portfolio_id=req.portfolio_id,
                    target_entity_id=limit.target_entity_id,
                    previous_status=prior_eval.status,
                    new_status=status,
                    event_type=event_type,
                    measured_exposure=measured_exp,
                    limit_value=limit.limit_value,
                    headroom=headroom,
                    details=f"Status transitioned from {prior_eval.status.value} to {status.value}",
                    recorded_at=utc_now(),
                )
                await self.repo.create_breach_event(breach_evt)

        await self.repo.create_evaluations(eval_records)

        # Build response items mapping config fields
        config_map = {l.limit_id: l for l in active_limits}
        item_responses = []
        for e in eval_records:
            cfg = config_map.get(e.limit_id)
            item_responses.append(
                ExposureLimitEvaluationItemResponse(
                    evaluation_id=e.evaluation_id,
                    limit_id=e.limit_id,
                    limit_code=cfg.limit_code if cfg else e.limit_id,
                    limit_name=cfg.limit_name if cfg else "Limit",
                    limit_category=cfg.limit_category if cfg else ExposureLimitCategory.INSTRUMENT_LIMIT,
                    target_entity_id=cfg.target_entity_id if cfg else None,
                    target_entity_name=cfg.target_entity_name if cfg else None,
                    exposure_basis=cfg.exposure_basis if cfg else ExposureMeasurementBasis.GROSS_MARKET_VALUE,
                    limit_direction=cfg.limit_direction if cfg else ExposureLimitDirection.MAXIMUM,
                    denominator_type=cfg.denominator_type if cfg else ExposureLimitDenominatorType.PORTFOLIO_NAV,
                    measured_exposure=e.measured_exposure,
                    denominator_value=e.denominator_value,
                    limit_value=e.limit_value,
                    utilization_percentage=e.utilization_percentage,
                    headroom=e.headroom,
                    shortfall=e.shortfall,
                    status=e.status,
                    data_completeness_status=e.data_completeness_status,
                    source_reference=e.source_reference,
                    evaluated_at=e.evaluated_at,
                )
            )

        return ExposureLimitEvaluationSummaryResponse(
            portfolio_id=req.portfolio_id,
            portfolio_group_id=req.portfolio_group_id,
            total_evaluated_limits=len(eval_records),
            within_limit_count=within_c,
            warning_count=warning_c,
            breached_count=breached_c,
            severely_breached_count=severe_c,
            unavailable_count=unavail_c,
            items=item_responses,
        )

    async def simulate_hypothetical_exposure(
        self, req: ExposureLimitSimulateRequest
    ) -> ExposureLimitSimulationResponse:
        """
        Simulates proposed exposure changes against a configured limit without mutating positions.
        """
        limit = await self.repo.get_limit_config_by_id(req.limit_id)
        if not limit:
            raise ValueError(f"Limit config '{req.limit_id}' not found.")

        latest_eval = await self.repo.get_latest_evaluation(limit.limit_id)
        current_exp = latest_eval.measured_exposure if latest_eval else Decimal("0.0")
        current_util = latest_eval.utilization_percentage if latest_eval else Decimal("0.0")
        current_hr = latest_eval.headroom if latest_eval else limit.limit_value
        current_stat = latest_eval.status if latest_eval else ExposureLimitStatus.WITHIN_LIMIT

        proj_exp = current_exp + req.proposed_exposure_delta
        proj_hr = limit.limit_value - proj_exp
        proj_util = Decimal("0.0")
        proj_stat = ExposureLimitStatus.WITHIN_LIMIT

        if limit.limit_value > Decimal("0.0"):
            proj_util = ((proj_exp / limit.limit_value) * Decimal("100.0")).quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_UP
            )
            util_ratio = proj_exp / limit.limit_value
            if util_ratio >= limit.severe_breach_threshold_ratio:
                proj_stat = ExposureLimitStatus.SEVERELY_BREACHED
            elif util_ratio > Decimal("1.0"):
                proj_stat = ExposureLimitStatus.BREACHED
            elif util_ratio >= limit.warning_threshold_ratio:
                proj_stat = ExposureLimitStatus.WARNING

        return ExposureLimitSimulationResponse(
            portfolio_id=req.portfolio_id,
            limit_id=req.limit_id,
            current_exposure=current_exp,
            proposed_exposure_delta=req.proposed_exposure_delta,
            projected_exposure=proj_exp,
            limit_value=limit.limit_value,
            current_utilization=current_util,
            projected_utilization=proj_util,
            current_headroom=current_hr,
            projected_headroom=proj_hr,
            current_status=current_stat,
            projected_status=proj_stat,
        )
