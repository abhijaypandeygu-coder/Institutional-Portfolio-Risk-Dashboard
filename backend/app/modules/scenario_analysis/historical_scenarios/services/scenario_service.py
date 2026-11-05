"""
Historical Scenarios Service (M10.01).
Orchestrates event library, observation mapping, portfolio revaluation,
reconciliation, caveat generation, and historical difference analysis.
"""

import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.scenario_models import (
    HistoricalScenarioEvent,
    HistoricalScenarioEventVersion,
    HistoricalScenarioObservation,
    HistoricalScenarioReplayRun,
    HistoricalShockMappingResult,
    HistoricalScenarioReplayPosition,
    HistoricalScenarioReplayWarning,
    HistoricalScenarioReplayPath
)
from ..schemas.scenario_schemas import (
    HistoricalEventCreate,
    HistoricalEventResponse,
    HistoricalObservationInput,
    PortfolioPositionInput,
    ReplayExecutionRequest,
    PositionReplayResponse,
    ReplayWarningResponse,
    ReplayPathPoint,
    ReplayRunSummaryResponse,
    HistoricalDifferenceReport
)
from ..repositories.scenario_repository import HistoricalScenariosRepository
from ..calculations.scenario_math import (
    to_decimal,
    compute_cumulative_compounded_return,
    compute_currency_adjusted_return,
    estimate_factor_shock,
    revalue_position,
    aggregate_portfolio_replay
)


class HistoricalScenariosService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = HistoricalScenariosRepository(db)

    async def create_event(self, req: HistoricalEventCreate) -> HistoricalEventResponse:
        existing = await self.repo.get_event_by_code(req.event_code)
        if existing:
            return HistoricalEventResponse.model_validate(existing)

        ev_id = f"hevt_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc)

        event = HistoricalScenarioEvent(
            id=ev_id,
            event_code=req.event_code,
            event_name=req.event_name,
            description=req.description,
            category=req.category,
            tags=req.tags,
            global_scope=req.global_scope,
            affected_regions=req.affected_regions,
            affected_markets=req.affected_markets,
            start_date=req.start_date,
            end_date=req.end_date,
            reference_timezone=req.reference_timezone,
            primary_reference_index=req.primary_reference_index,
            event_narrative=req.event_narrative,
            data_coverage_status=req.data_coverage_status,
            event_status="ACTIVE",
            current_version=req.current_version,
            created_at=now_utc,
            updated_at=now_utc,
            created_by="QUANT_USER"
        )
        saved = await self.repo.create_event(event)
        return HistoricalEventResponse.model_validate(saved)

    async def add_observations(
        self,
        event_id: str,
        observations: List[HistoricalObservationInput]
    ) -> int:
        count = 0
        now_utc = datetime.now(timezone.utc)
        for obs in observations:
            model = HistoricalScenarioObservation(
                id=f"hobs_{uuid.uuid4().hex[:12]}",
                event_id=event_id,
                instrument_id=obs.instrument_id,
                listing_id=obs.listing_id,
                factor_id=obs.factor_id,
                observation_date=obs.observation_date,
                observation_timestamp=obs.observation_timestamp,
                reference_price=obs.reference_price,
                adjusted_price=obs.adjusted_price,
                return_value=obs.return_value,
                return_type=obs.return_type,
                currency=obs.currency,
                quality_status=obs.quality_status,
                created_at=now_utc
            )
            await self.repo.save_observation(model)
            count += 1
        return count

    async def execute_replay(self, req: ReplayExecutionRequest) -> ReplayRunSummaryResponse:
        """
        Executes historical scenario replay against current or historical portfolio positions.
        """
        event = await self.repo.get_event_by_id(req.event_id)
        if not event:
            raise ValueError(f"Historical event {req.event_id} not found")

        # Retrieve all observations for this event
        all_obs = await self.repo.get_event_observations(req.event_id)
        
        # Group observations by instrument_id and factor_id
        inst_obs_map: Dict[str, List[HistoricalScenarioObservation]] = {}
        factor_obs_map: Dict[str, List[HistoricalScenarioObservation]] = {}
        for o in all_obs:
            if o.instrument_id:
                inst_obs_map.setdefault(o.instrument_id, []).append(o)
            if o.factor_id:
                factor_obs_map.setdefault(o.factor_id, []).append(o)

        replay_id = f"hrun_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc)
        
        position_models: List[HistoricalScenarioReplayPosition] = []
        warning_models: List[HistoricalScenarioReplayWarning] = []
        mapping_models: List[HistoricalShockMappingResult] = []
        
        calc_pos_results: List[Dict[str, Any]] = []
        calc_excluded_results: List[Dict[str, Any]] = []

        excluded_set = set(req.excluded_instrument_ids or [])
        fx_shocks = req.fx_shocks or {}

        # Process each position
        for pos in req.positions:
            is_excluded = pos.instrument_id in excluded_set
            
            # 1. Determine Shock via Mapping Hierarchy
            mapping_method = "UNMAPPED"
            confidence = "LOW"
            chosen_local_shock = Decimal("0")
            rationale = "No eligible historical observation found"
            source_inst_id = None
            source_factor_id = None

            # Priority 1: User manual override
            if req.manual_overrides and pos.instrument_id in req.manual_overrides:
                mapping_method = "MANUAL_OVERRIDE"
                confidence = "HIGH"
                chosen_local_shock = req.manual_overrides[pos.instrument_id]
                rationale = "User explicitly specified scenario shock"
            # Priority 2: Direct instrument match
            elif pos.instrument_id in inst_obs_map:
                obs_list = sorted(inst_obs_map[pos.instrument_id], key=lambda x: x.observation_date)
                ret_list = [o.return_value for o in obs_list]
                chosen_local_shock = compute_cumulative_compounded_return(ret_list)
                mapping_method = "EXACT_DIRECT"
                confidence = "HIGH"
                source_inst_id = pos.instrument_id
                rationale = f"Direct historical return compounded from {len(obs_list)} observations"
            # Priority 3: Approved Proxy
            elif req.manual_proxy_mappings and pos.instrument_id in req.manual_proxy_mappings:
                proxy_id = req.manual_proxy_mappings[pos.instrument_id]
                if proxy_id in inst_obs_map:
                    obs_list = sorted(inst_obs_map[proxy_id], key=lambda x: x.observation_date)
                    ret_list = [o.return_value for o in obs_list]
                    chosen_local_shock = compute_cumulative_compounded_return(ret_list)
                    mapping_method = "APPROVED_PROXY"
                    confidence = "MEDIUM"
                    source_inst_id = proxy_id
                    rationale = f"Mapped using approved proxy {proxy_id}"
                    warning_models.append(HistoricalScenarioReplayWarning(
                        id=f"hwrn_{uuid.uuid4().hex[:12]}",
                        replay_id=replay_id,
                        instrument_id=pos.instrument_id,
                        warning_code="PROXY_SHOCK_USED",
                        severity="WARNING",
                        warning_category="PROXY_BIAS",
                        message=f"Position {pos.instrument_id} shocked using proxy {proxy_id}"
                    ))
            # Priority 4: Factor-based estimation
            elif pos.factor_sensitivities and any(f in factor_obs_map for f in pos.factor_sensitivities):
                factor_returns: Dict[str, Decimal] = {}
                for f_name in pos.factor_sensitivities:
                    if f_name in factor_obs_map:
                        f_rets = [o.return_value for o in factor_obs_map[f_name]]
                        factor_returns[f_name] = compute_cumulative_compounded_return(f_rets)
                chosen_local_shock = estimate_factor_shock(pos.factor_sensitivities, factor_returns)
                mapping_method = "FACTOR_MODEL"
                confidence = "MEDIUM"
                rationale = "Estimated via M08 multi-factor sensitivity model"
                warning_models.append(HistoricalScenarioReplayWarning(
                    id=f"hwrn_{uuid.uuid4().hex[:12]}",
                    replay_id=replay_id,
                    instrument_id=pos.instrument_id,
                    warning_code="FACTOR_ESTIMATE_USED",
                    severity="WARNING",
                    warning_category="MODEL_ESTIMATION",
                    message=f"Position {pos.instrument_id} shocked using factor model"
                ))
            else:
                # Unmapped
                warning_models.append(HistoricalScenarioReplayWarning(
                    id=f"hwrn_{uuid.uuid4().hex[:12]}",
                    replay_id=replay_id,
                    instrument_id=pos.instrument_id,
                    warning_code="UNMAPPED_EXPOSURE",
                    severity="HIGH",
                    warning_category="DATA_COVERAGE",
                    message=f"Position {pos.instrument_id} has no direct or proxy historical shock"
                ))

            # 2. Currency Conversion
            pos_fx_return = Decimal("0")
            if pos.currency != req.base_currency:
                pos_fx_return = fx_shocks.get(pos.currency, Decimal("0"))
                base_currency_shock = compute_currency_adjusted_return(chosen_local_shock, pos_fx_return)
            else:
                base_currency_shock = chosen_local_shock

            # 3. Position Revaluation
            reval = revalue_position(
                signed_quantity=pos.signed_quantity,
                baseline_price=pos.baseline_price,
                scenario_return=base_currency_shock,
                baseline_nav=req.baseline_nav
            )

            # Strict policy check
            if req.missing_data_policy == "STRICT" and mapping_method == "UNMAPPED":
                raise ValueError(f"Strict policy failed: Position {pos.instrument_id} is unmapped")

            pos_res_dict = {
                "instrument_id": pos.instrument_id,
                "listing_id": pos.listing_id,
                "signed_quantity": pos.signed_quantity,
                "baseline_price": pos.baseline_price,
                "baseline_market_value": reval["baseline_market_value"],
                "local_currency": pos.currency,
                "local_return": chosen_local_shock,
                "fx_return": pos_fx_return,
                "base_currency_return": base_currency_shock,
                "scenario_price": reval["scenario_price"],
                "scenario_market_value": reval["scenario_market_value"],
                "scenario_pnl": reval["scenario_pnl"],
                "portfolio_weight": reval["portfolio_weight"],
                "portfolio_contribution": reval["portfolio_contribution"],
                "mapping_method": mapping_method,
                "mapping_status": "SUCCESS" if mapping_method != "UNMAPPED" else "UNMAPPED",
                "quality_status": "VALID",
                "is_excluded": is_excluded
            }

            if is_excluded:
                calc_excluded_results.append(pos_res_dict)
            else:
                calc_pos_results.append(pos_res_dict)

            pos_model = HistoricalScenarioReplayPosition(
                id=f"hpos_{uuid.uuid4().hex[:12]}",
                replay_id=replay_id,
                instrument_id=pos.instrument_id,
                listing_id=pos.listing_id,
                signed_quantity=pos.signed_quantity,
                baseline_price=pos.baseline_price,
                baseline_market_value=reval["baseline_market_value"],
                local_currency=pos.currency,
                local_return=chosen_local_shock,
                fx_return=pos_fx_return,
                base_currency_return=base_currency_shock,
                scenario_price=reval["scenario_price"],
                scenario_market_value=reval["scenario_market_value"],
                scenario_pnl=reval["scenario_pnl"],
                portfolio_weight=reval["portfolio_weight"],
                portfolio_contribution=reval["portfolio_contribution"],
                mapping_method=mapping_method,
                mapping_status="SUCCESS" if mapping_method != "UNMAPPED" else "UNMAPPED",
                quality_status="VALID",
                is_excluded=is_excluded,
                exclusion_reason="Excluded by user configuration" if is_excluded else None,
                created_at=now_utc
            )
            position_models.append(pos_model)

            mapping_models.append(HistoricalShockMappingResult(
                id=f"hmap_{uuid.uuid4().hex[:12]}",
                replay_id=replay_id,
                instrument_id=pos.instrument_id,
                listing_id=pos.listing_id,
                mapping_method=mapping_method,
                source_instrument_id=source_inst_id,
                source_factor_id=source_factor_id,
                historical_shock=chosen_local_shock,
                fx_shock=pos_fx_return,
                base_currency_shock=base_currency_shock,
                confidence_level=confidence,
                quality_status="VALID",
                mapping_rationale=rationale,
                override_status=mapping_method == "MANUAL_OVERRIDE",
                override_reason="Manual override" if mapping_method == "MANUAL_OVERRIDE" else None,
                mapping_rule_version="1.0.0",
                created_at=now_utc
            ))

        # 4. Aggregate Portfolio Replay
        agg = aggregate_portfolio_replay(
            baseline_nav=req.baseline_nav,
            position_results=calc_pos_results,
            excluded_positions=calc_excluded_results
        )

        # 5. Daily Path Replay (Optional)
        daily_path_models: List[HistoricalScenarioReplayPath] = []
        daily_path_points: List[ReplayPathPoint] = []
        if req.include_daily_path:
            # Collect unique observation dates across instruments
            obs_dates = sorted(list({o.observation_date for o in all_obs}))
            for dt in obs_dates:
                # Value portfolio on date dt
                step_pnl = Decimal("0")
                for pos in req.positions:
                    if pos.instrument_id in inst_obs_map:
                        dt_obs = [o for o in inst_obs_map[pos.instrument_id] if o.observation_date <= dt]
                        if dt_obs:
                            dt_ret = compute_cumulative_compounded_return([o.return_value for o in dt_obs])
                            step_pnl += pos.signed_quantity * pos.baseline_price * dt_ret
                step_nav = req.baseline_nav + step_pnl
                step_ret = (step_pnl / req.baseline_nav).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
                
                pt_model = HistoricalScenarioReplayPath(
                    id=f"hpth_{uuid.uuid4().hex[:12]}",
                    replay_id=replay_id,
                    observation_date=dt,
                    observation_timestamp=dt,
                    baseline_nav=req.baseline_nav,
                    scenario_nav=step_nav,
                    scenario_pnl=step_pnl,
                    scenario_return=step_ret,
                    coverage_ratio=agg["direct_coverage"],
                    quality_status="VALID",
                    created_at=now_utc
                )
                daily_path_models.append(pt_model)
                daily_path_points.append(ReplayPathPoint(
                    observation_date=dt,
                    scenario_nav=step_nav,
                    scenario_pnl=step_pnl,
                    scenario_return=step_ret
                ))

        # Status definition
        run_status = "COMPLETED"
        if warning_models:
            run_status = "COMPLETED_WITH_WARNINGS"
        if agg["unmapped_coverage"] > Decimal("0"):
            run_status = "PARTIAL"

        replay_run = HistoricalScenarioReplayRun(
            id=replay_id,
            replay_code=f"REP_{event.event_code}_{now_utc.strftime('%Y%m%d%H%M%S')}",
            portfolio_id=req.portfolio_id,
            scenario_event_id=req.event_id,
            scenario_event_version_id="1.0.0",
            portfolio_snapshot_id=req.portfolio_snapshot_id,
            replay_mode=req.replay_mode,
            return_definition=req.return_definition,
            base_currency=req.base_currency,
            mapping_policy_version="1.0.0",
            missing_data_policy=req.missing_data_policy,
            valuation_baseline=req.valuation_baseline,
            calculation_version="1.0.0",
            replay_status=run_status,
            baseline_nav=agg["baseline_nav"],
            scenario_nav=agg["scenario_nav"],
            scenario_pnl=agg["scenario_pnl"],
            scenario_return=agg["scenario_return"],
            direct_coverage=agg["direct_coverage"],
            proxy_coverage=agg["proxy_coverage"],
            factor_coverage=agg["factor_coverage"],
            unmapped_coverage=agg["unmapped_coverage"],
            started_at=now_utc,
            completed_at=now_utc,
            created_by="QUANT_ANALYST"
        )

        await self.repo.save_replay_run(replay_run)
        await self.repo.save_replay_positions(position_models)
        if mapping_models:
            self.db.add_all(mapping_models)
            await self.db.flush()
        if warning_models:
            await self.repo.save_replay_warnings(warning_models)
        if daily_path_models:
            await self.repo.save_replay_paths(daily_path_models)

        caveat_text = (
            "This result applies historical market shocks to the selected portfolio holdings. "
            "It does not establish that the portfolio would have existed in the same form during the historical event. "
            "Differences in constituents, sector allocations, listing history, currency exposure, corporate actions, "
            "market structure and liquidity may materially affect comparability."
        )

        return ReplayRunSummaryResponse(
            replay_id=replay_id,
            replay_code=replay_run.replay_code,
            portfolio_id=req.portfolio_id,
            scenario_event_id=req.event_id,
            replay_mode=req.replay_mode,
            base_currency=req.base_currency,
            replay_status=run_status,
            baseline_nav=agg["baseline_nav"],
            scenario_nav=agg["scenario_nav"],
            scenario_pnl=agg["scenario_pnl"],
            scenario_return=agg["scenario_return"],
            direct_coverage=agg["direct_coverage"],
            proxy_coverage=agg["proxy_coverage"],
            factor_coverage=agg["factor_coverage"],
            unmapped_coverage=agg["unmapped_coverage"],
            included_count=agg["included_count"],
            excluded_count=agg["excluded_count"],
            warnings=[
                ReplayWarningResponse(
                    warning_code=w.warning_code,
                    severity=w.severity,
                    warning_category=w.warning_category,
                    message=w.message,
                    details_json=w.details_json
                )
                for w in warning_models
            ],
            positions=[
                PositionReplayResponse(
                    instrument_id=p.instrument_id,
                    listing_id=p.listing_id,
                    signed_quantity=p.signed_quantity,
                    baseline_price=p.baseline_price,
                    baseline_market_value=p.baseline_market_value,
                    local_currency=p.local_currency,
                    local_return=p.local_return,
                    fx_return=p.fx_return,
                    base_currency_return=p.base_currency_return,
                    scenario_price=p.scenario_price,
                    scenario_market_value=p.scenario_market_value,
                    scenario_pnl=p.scenario_pnl,
                    portfolio_weight=p.portfolio_weight,
                    portfolio_contribution=p.portfolio_contribution,
                    mapping_method=p.mapping_method,
                    mapping_status=p.mapping_status,
                    quality_status=p.quality_status,
                    is_excluded=p.is_excluded,
                    exclusion_reason=p.exclusion_reason
                )
                for p in position_models
            ],
            daily_path=daily_path_points if req.include_daily_path else None,
            caveat_summary=caveat_text
        )

    async def get_historical_difference_report(
        self,
        replay_id: str
    ) -> HistoricalDifferenceReport:
        """
        Generates historical difference analysis between tested holdings and historical reference.
        """
        run = await self.repo.get_replay_run_by_id(replay_id)
        if not run:
            raise ValueError(f"Replay run {replay_id} not found")

        positions = await self.repo.get_replay_positions(replay_id)
        
        # In a real environment, historical holdings from M05.07 are compared.
        # Here we quantify the holdings and sector allocations of the tested portfolio.
        overlap_count = sum(1 for p in positions if p.mapping_method == "EXACT_DIRECT")
        new_holdings_count = sum(1 for p in positions if p.mapping_method != "EXACT_DIRECT")

        top_holding = "NONE"
        if positions:
            sorted_pos = sorted(positions, key=lambda p: abs(p.baseline_market_value), reverse=True)
            top_holding = sorted_pos[0].instrument_id

        return HistoricalDifferenceReport(
            holdings_overlap_count=overlap_count,
            new_holdings_count=new_holdings_count,
            delisted_or_missing_holdings_count=0,
            tested_top_holding=top_holding,
            historical_top_holding=None,
            sector_weight_differences={},
            mandatory_caveat=(
                "Differences in constituents, sector allocations, listing history, and liquidity "
                "materially distinguish this tested portfolio from the actual historical investable universe."
            )
        )
