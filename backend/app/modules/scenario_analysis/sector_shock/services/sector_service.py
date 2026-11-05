"""
Sector Shock Orchestration Service (M10.04).
Coordinates end-to-end execution pipeline:
1. Scenario creation & immutable versioning
2. Group shock definition & conflict resolution (sector vs industry precedence)
3. Spillover transmission matrix (sector-to-sector and sector-to-factor)
4. Instrument response composition (Direct + Spillover + Factor-mediated + Manual)
5. Multi-currency FX conversion & signed position revaluation
6. Portfolio NAV, PnL, and positive loss aggregation
7. Group (Sector & Industry) and Channel Attribution (Direct, Spillover, Factor, Manual)
8. Coverage diagnostics & audit caveats
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..calculations.sector_math import (
    calculate_direct_sector_response,
    calculate_spillover_effects,
    calculate_factor_mediated_spillover,
    compose_sector_returns,
    convert_to_base_currency,
    revalue_sector_position,
    compute_portfolio_sector_revaluation,
    compute_sector_coverage_metrics,
    decompose_sector_impacts
)
from ..models.sector_models import (
    SectorShockScenario,
    SectorShockScenarioVersion,
    SectorShockGroupDefinition,
    SectorShockMembershipSnapshot,
    SectorSpilloverRelationship,
    SectorSpilloverRelationshipVersion,
    SectorShockMappingResult,
    SectorShockSimulationRun,
    SectorShockPositionResult,
    SectorShockGroupResult,
    SectorShockAttributionResult,
    SectorShockWarning,
    SectorShockAuditLog
)
from ..schemas.sector_schemas import (
    SectorShockGroupConfig,
    SpilloverRelationshipConfig,
    SectorShockScenarioCreate,
    SectorShockScenarioResponse,
    SectorPositionInput,
    SectorSimulationExecutionRequest,
    SectorSimulationSummaryResponse,
    SectorPositionResultResponse,
    SectorGroupResultResponse,
    SectorAttributionResultResponse,
    SectorWarningResponse
)
from ..repositories.sector_repository import SectorShockRepository


class SectorShockService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SectorShockRepository(db)

    # -------------------------------------------------------------------------
    # Scenario Creation & Versioning
    # -------------------------------------------------------------------------
    async def create_scenario(self, req: SectorShockScenarioCreate) -> SectorShockScenarioResponse:
        scenario_id = f"sec_sc_{uuid.uuid4().hex[:12]}"
        version_id = f"sec_ver_{uuid.uuid4().hex[:12]}"

        config_dict = req.model_dump(mode="json")
        config_str = json.dumps(config_dict, sort_keys=True)
        config_hash = hashlib.sha256(config_str.encode("utf-8")).hexdigest()

        scenario = SectorShockScenario(
            id=scenario_id,
            scenario_code=req.scenario_code,
            scenario_name=req.scenario_name,
            description=req.description,
            category=req.category,
            portfolio_id=req.portfolio_id,
            visibility=req.visibility,
            author_id=req.author_id,
            owner_id=req.owner_id,
            current_version=1,
            status="ACTIVE"
        )
        await self.repo.create_scenario(scenario)

        version = SectorShockScenarioVersion(
            id=version_id,
            scenario_id=scenario_id,
            version=1,
            configuration_json=config_dict,
            configuration_hash=config_hash,
            change_reason="Initial creation",
            created_by=req.author_id
        )
        await self.repo.create_scenario_version(version)

        # Persist Group Shocks
        for g_shock in req.group_shocks:
            g_model = SectorShockGroupDefinition(
                id=f"sec_grp_{uuid.uuid4().hex[:12]}",
                scenario_version_id=version_id,
                classification_system=g_shock.classification_system,
                classification_version=g_shock.classification_version,
                group_type=g_shock.group_type,
                group_identifier=g_shock.group_identifier,
                shock_method=g_shock.shock_method,
                shock_value=g_shock.shock_value,
                shock_unit=g_shock.shock_unit,
                baseline_index_reference=g_shock.baseline_index_reference,
                shock_priority=g_shock.shock_priority,
                application_method=g_shock.application_method,
                configuration_json=g_shock.model_dump(mode="json")
            )
            self.db.add(g_model)

        # Persist Spillover Relationships if provided
        if req.spillover_relationships:
            for s_rel in req.spillover_relationships:
                rel_id = f"sec_rel_{uuid.uuid4().hex[:12]}"
                rel_model = SectorSpilloverRelationship(
                    id=rel_id,
                    relationship_code=s_rel.relationship_code,
                    source_type=s_rel.source_type,
                    source_identifier=s_rel.source_identifier,
                    target_type=s_rel.target_type,
                    target_identifier=s_rel.target_identifier,
                    relationship_method=s_rel.relationship_method,
                    spillover_coefficient=s_rel.spillover_coefficient,
                    direction=s_rel.direction,
                    calibration_source=s_rel.calibration_source,
                    version=1,
                    approval_status="APPROVED",
                    author_id=req.author_id
                )
                self.db.add(rel_model)

        await self.db.commit()

        saved = await self.repo.get_scenario(scenario_id)
        resp = SectorShockScenarioResponse.model_validate(saved)
        resp.group_shocks = req.group_shocks
        resp.spillover_relationships = req.spillover_relationships
        return resp

    # -------------------------------------------------------------------------
    # Simulation Execution
    # -------------------------------------------------------------------------
    async def execute_simulation(self, req: SectorSimulationExecutionRequest) -> SectorSimulationSummaryResponse:
        run_id = f"sec_run_{uuid.uuid4().hex[:12]}"
        sim_code = f"SECSIM_{uuid.uuid4().hex[:8].upper()}"

        warnings: List[SectorShockWarning] = []
        snapshots: List[SectorShockMembershipSnapshot] = []
        mappings: List[SectorShockMappingResult] = []
        position_models: List[SectorShockPositionResult] = []
        positions_reval: List[Dict[str, Decimal]] = []
        positions_coverage_data: List[Dict[str, Any]] = []

        # 1. Build Direct Shock Map (Sectors & Industries)
        sector_direct_shocks: Dict[str, Decimal] = {}
        industry_direct_shocks: Dict[str, Decimal] = {}
        for g in req.group_shocks:
            ident = g.group_identifier.upper()
            if g.group_type.upper() == "INDUSTRY":
                industry_direct_shocks[ident] = g.shock_value
            else:
                sector_direct_shocks[ident] = g.shock_value

        # 2. Build Spillover Matrices (Sector-to-Sector & Sector-to-Factor)
        sec_to_sec_matrix: Dict[str, Dict[str, Decimal]] = {}
        sec_to_fac_matrix: Dict[str, Dict[str, Decimal]] = {}

        if req.spillover_relationships:
            for rel in req.spillover_relationships:
                src = rel.source_identifier.upper()
                tgt = rel.target_identifier.upper()
                coeff = rel.spillover_coefficient
                if rel.target_type.upper() == "FACTOR":
                    if tgt not in sec_to_fac_matrix:
                        sec_to_fac_matrix[tgt] = {}
                    sec_to_fac_matrix[tgt][src] = coeff
                else:
                    if tgt not in sec_to_sec_matrix:
                        sec_to_sec_matrix[tgt] = {}
                    sec_to_sec_matrix[tgt][src] = coeff

        # 3. Calculate Indirect Sector Spillovers
        # Combine direct shocks for spillover calculation
        all_direct_shocks = {**sector_direct_shocks, **industry_direct_shocks}
        indirect_spillovers = calculate_spillover_effects(all_direct_shocks, sec_to_sec_matrix)

        # 4. Process Positions
        for pos in req.positions:
            is_classified = bool(pos.sector or pos.industry)
            is_directly_shocked = False
            is_spillover_affected = False
            is_sens_valid = pos.sector_sensitivity is not None

            pos_sec = (pos.sector or "UNCLASSIFIED").upper()
            pos_ind = (pos.industry or "UNCLASSIFIED").upper()

            # A. Resolve Direct Shock
            # Policy: MOST_SPECIFIC_WINS (Industry shock overrides Sector shock if present)
            dir_r = Decimal("0")
            ind_r = Decimal("0")
            applied_direct = Decimal("0")
            mapping_status = "UNMAPPED"
            mapping_rationale = "No matching sector shock"

            if pos_ind in industry_direct_shocks:
                is_directly_shocked = True
                ind_r = industry_direct_shocks[pos_ind]
                applied_direct = calculate_direct_sector_response(ind_r, pos.sector_sensitivity)
                mapping_status = "MAPPED_INDUSTRY"
                mapping_rationale = f"Matched direct industry shock {ind_r}"
            elif pos_sec in sector_direct_shocks:
                is_directly_shocked = True
                dir_r = sector_direct_shocks[pos_sec]
                applied_direct = calculate_direct_sector_response(dir_r, pos.sector_sensitivity)
                mapping_status = "MAPPED_SECTOR"
                mapping_rationale = f"Matched direct sector shock {dir_r}"

            # B. Resolve Spillover Shock
            spill_r = Decimal("0")
            if pos_sec in indirect_spillovers:
                spill_r = indirect_spillovers[pos_sec]
                if spill_r != Decimal("0"):
                    is_spillover_affected = True
                    if mapping_status == "UNMAPPED":
                        mapping_status = "SPILLOVER_ONLY"
                        mapping_rationale = f"Subject to indirect sector spillover {spill_r}"

            # C. Resolve Factor-Mediated Spillover
            fac_r = Decimal("0")
            if sec_to_fac_matrix and pos.factor_betas:
                _, fac_r = calculate_factor_mediated_spillover(
                    direct_shocks=all_direct_shocks,
                    sector_to_factor_matrix=sec_to_fac_matrix,
                    instrument_factor_betas=pos.factor_betas
                )

            # D. Manual Adjustment
            man_adj = pos.manual_adjustment or Decimal("0")

            # E. Compose Final Modeled Return
            composed = compose_sector_returns(
                direct_return=applied_direct,
                spillover_return=spill_r,
                factor_return=fac_r,
                manual_adjustment=man_adj,
                composition_policy=req.composition_policy
            )

            # Currency Conversion
            final_base_r = convert_to_base_currency(composed["final_scenario_return"], pos.fx_return)

            # Revalue Position
            reval = revalue_sector_position(
                signed_quantity=pos.signed_quantity,
                baseline_price=pos.baseline_price,
                final_return=final_base_r,
                baseline_nav=req.baseline_nav
            )

            positions_reval.append(reval)
            positions_coverage_data.append({
                "baseline_market_value": reval["baseline_market_value"],
                "is_classified": is_classified,
                "is_directly_shocked": is_directly_shocked,
                "is_spillover_affected": is_spillover_affected,
                "is_sensitivity_valid": is_sens_valid
            })

            # Membership Snapshot
            snapshots.append(SectorShockMembershipSnapshot(
                id=f"sec_snp_{uuid.uuid4().hex[:12]}",
                simulation_run_id=run_id,
                classification_system="GICS",
                group_identifier=pos_sec,
                instrument_id=pos.instrument_id,
                listing_id=pos.listing_id
            ))

            # Mapping Result
            mappings.append(SectorShockMappingResult(
                id=f"sec_map_{uuid.uuid4().hex[:12]}",
                simulation_run_id=run_id,
                instrument_id=pos.instrument_id,
                listing_id=pos.listing_id,
                sector_id=pos_sec,
                industry_id=pos_ind,
                mapping_method="DIRECT_OR_SPILLOVER",
                mapping_status=mapping_status,
                mapping_rationale=mapping_rationale
            ))

            # Position Result
            pos_model = SectorShockPositionResult(
                id=f"sec_pos_{uuid.uuid4().hex[:12]}",
                simulation_run_id=run_id,
                instrument_id=pos.instrument_id,
                listing_id=pos.listing_id,
                sector=pos_sec,
                industry=pos_ind,
                currency=pos.currency,
                signed_quantity=pos.signed_quantity,
                baseline_price=pos.baseline_price,
                scenario_price=reval["scenario_price"],
                baseline_market_value=reval["baseline_market_value"],
                scenario_market_value=reval["scenario_market_value"],
                direct_sector_return=dir_r,
                industry_return=ind_r,
                sensitivity_adjustment=applied_direct - (ind_r if ind_r != Decimal("0") else dir_r),
                spillover_adjustment=spill_r,
                factor_adjustment=fac_r,
                manual_adjustment=man_adj,
                final_scenario_return=final_base_r,
                scenario_pnl=reval["scenario_pnl"],
                scenario_loss=reval["scenario_loss"],
                portfolio_contribution=reval["portfolio_contribution"],
                mapping_status=mapping_status,
                classification_status="CLASSIFIED" if is_classified else "UNCLASSIFIED"
            )
            position_models.append(pos_model)

            if not is_classified:
                warnings.append(SectorShockWarning(
                    id=f"sec_wrn_{uuid.uuid4().hex[:12]}",
                    simulation_run_id=run_id,
                    instrument_id=pos.instrument_id,
                    warning_code="UNCLASSIFIED_HOLDING",
                    severity="HIGH",
                    category="CLASSIFICATION",
                    message=f"Instrument {pos.instrument_id} has no authoritative sector classification"
                ))

        # 5. Aggregate Portfolio Revaluation
        port_reval = compute_portfolio_sector_revaluation(req.baseline_nav, positions_reval)
        cov_metrics = compute_sector_coverage_metrics(positions_coverage_data)

        # 6. Sector and Industry Group Aggregations
        group_models: List[SectorShockGroupResult] = []
        sec_groups: Dict[str, Dict[str, Any]] = {}
        ind_groups: Dict[str, Dict[str, Any]] = {}

        for p in position_models:
            # Sector
            s = p.sector or "UNCLASSIFIED"
            if s not in sec_groups:
                sec_groups[s] = {"exp": Decimal("0"), "pnl": Decimal("0"), "loss": Decimal("0"), "count": 0, "dir": p.direct_sector_return, "spill": p.spillover_adjustment}
            sec_groups[s]["exp"] += abs(p.baseline_market_value)
            sec_groups[s]["pnl"] += p.scenario_pnl
            sec_groups[s]["loss"] += p.scenario_loss
            sec_groups[s]["count"] += 1

            # Industry
            ind = p.industry or "UNCLASSIFIED"
            if ind not in ind_groups:
                ind_groups[ind] = {"exp": Decimal("0"), "pnl": Decimal("0"), "loss": Decimal("0"), "count": 0, "dir": p.industry_return, "spill": p.spillover_adjustment}
            ind_groups[ind]["exp"] += abs(p.baseline_market_value)
            ind_groups[ind]["pnl"] += p.scenario_pnl
            ind_groups[ind]["loss"] += p.scenario_loss
            ind_groups[ind]["count"] += 1

        for s_id, s_data in sec_groups.items():
            s_ret = (s_data["pnl"] / s_data["exp"]) if s_data["exp"] > Decimal("0") else Decimal("0")
            s_contrib = (s_data["pnl"] / req.baseline_nav) if req.baseline_nav > Decimal("0") else Decimal("0")
            group_models.append(SectorShockGroupResult(
                id=f"sec_grp_res_{uuid.uuid4().hex[:12]}",
                simulation_run_id=run_id,
                group_type="SECTOR",
                group_identifier=s_id,
                baseline_exposure=s_data["exp"],
                direct_shock=s_data["dir"],
                spillover_shock=s_data["spill"],
                total_scenario_return=s_ret.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
                scenario_pnl=s_data["pnl"],
                scenario_loss=s_data["loss"],
                portfolio_contribution=s_contrib.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
                position_count=s_data["count"]
            ))

        for ind_id, ind_data in ind_groups.items():
            ind_ret = (ind_data["pnl"] / ind_data["exp"]) if ind_data["exp"] > Decimal("0") else Decimal("0")
            ind_contrib = (ind_data["pnl"] / req.baseline_nav) if req.baseline_nav > Decimal("0") else Decimal("0")
            group_models.append(SectorShockGroupResult(
                id=f"sec_grp_res_{uuid.uuid4().hex[:12]}",
                simulation_run_id=run_id,
                group_type="INDUSTRY",
                group_identifier=ind_id,
                baseline_exposure=ind_data["exp"],
                direct_shock=ind_data["dir"],
                spillover_shock=ind_data["spill"],
                total_scenario_return=ind_ret.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
                scenario_pnl=ind_data["pnl"],
                scenario_loss=ind_data["loss"],
                portfolio_contribution=ind_contrib.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP),
                position_count=ind_data["count"]
            ))

        # 7. Impact Channel Attribution Breakdown
        attribution_models: List[SectorShockAttributionResult] = []
        tot_direct = Decimal("0")
        tot_spill = Decimal("0")
        tot_factor = Decimal("0")
        tot_manual = Decimal("0")

        for p in position_models:
            decomp = decompose_sector_impacts(
                baseline_market_value=p.baseline_market_value,
                direct_return=p.direct_sector_return if p.direct_sector_return != Decimal("0") else p.industry_return,
                spillover_return=p.spillover_adjustment,
                factor_return=p.factor_adjustment,
                manual_adjustment=p.manual_adjustment
            )
            tot_direct += decomp["direct_impact"]
            tot_spill += decomp["spillover_impact"]
            tot_factor += decomp["factor_impact"]
            tot_manual += decomp["manual_impact"]

        channels = [
            ("DIRECT_SECTOR_SHOCK", tot_direct),
            ("INDIRECT_SPILLOVER", tot_spill),
            ("FACTOR_MEDIATED", tot_factor),
            ("MANUAL_ADJUSTMENT", tot_manual)
        ]

        for chan_name, chan_pnl in channels:
            chan_contrib = (chan_pnl / req.baseline_nav) if req.baseline_nav > Decimal("0") else Decimal("0")
            attribution_models.append(SectorShockAttributionResult(
                id=f"sec_att_{uuid.uuid4().hex[:12]}",
                simulation_run_id=run_id,
                attribution_type="IMPACT_CHANNEL",
                attribution_identifier=chan_name,
                direct_impact=chan_pnl if "DIRECT" in chan_name else Decimal("0"),
                spillover_impact=chan_pnl if "SPILLOVER" in chan_name else Decimal("0"),
                factor_impact=chan_pnl if "FACTOR" in chan_name else Decimal("0"),
                manual_impact=chan_pnl if "MANUAL" in chan_name else Decimal("0"),
                total_impact=chan_pnl,
                contribution_percentage=chan_contrib.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
                reconciliation_residual=Decimal("0")
            ))

        # 8. Master Run Record
        now = datetime.now(timezone.utc)
        run_record = SectorShockSimulationRun(
            id=run_id,
            simulation_code=sim_code,
            scenario_id=req.scenario_id,
            portfolio_id=req.portfolio_id,
            portfolio_snapshot_id=req.portfolio_snapshot_id,
            base_currency=req.base_currency,
            calculation_version="1.0.0",
            conflict_resolution_policy=req.conflict_resolution_policy,
            missing_data_policy=req.missing_data_policy,
            composition_policy=req.composition_policy,
            run_status="COMPLETED" if not warnings else "COMPLETED_WITH_WARNINGS",
            baseline_nav=port_reval["baseline_nav"],
            scenario_nav=port_reval["scenario_nav"],
            scenario_pnl=port_reval["scenario_pnl"],
            scenario_loss=port_reval["scenario_loss"],
            scenario_return=port_reval["scenario_return"],
            direct_exposure_coverage=cov_metrics["direct_coverage"],
            spillover_exposure_coverage=cov_metrics["spillover_coverage"],
            classification_coverage=cov_metrics["classification_coverage"],
            sensitivity_coverage=cov_metrics["sensitivity_coverage"],
            started_at=now,
            completed_at=now
        )
        await self.repo.create_simulation_run(run_record)

        audit_log = SectorShockAuditLog(
            id=f"sec_aud_{uuid.uuid4().hex[:12]}",
            scenario_id=req.scenario_id,
            simulation_run_id=run_id,
            action_type="EXECUTE_SECTOR_SHOCK",
            reason=f"Executed sector shock under {req.composition_policy} composition"
        )

        await self.repo.save_run_details(
            snapshots=snapshots,
            mappings=mappings,
            positions=position_models,
            groups=group_models,
            attributions=attribution_models,
            warnings=warnings,
            audit_log=audit_log
        )

        return SectorSimulationSummaryResponse(
            simulation_id=run_id,
            simulation_code=sim_code,
            scenario_id=req.scenario_id,
            portfolio_id=req.portfolio_id,
            base_currency=req.base_currency,
            run_status=run_record.run_status,
            baseline_nav=port_reval["baseline_nav"],
            scenario_nav=port_reval["scenario_nav"],
            scenario_pnl=port_reval["scenario_pnl"],
            scenario_loss=port_reval["scenario_loss"],
            scenario_return=port_reval["scenario_return"],
            gross_exposure=port_reval["gross_exposure"],
            net_exposure=port_reval["net_exposure"],
            direct_exposure_coverage=cov_metrics["direct_coverage"],
            spillover_exposure_coverage=cov_metrics["spillover_coverage"],
            classification_coverage=cov_metrics["classification_coverage"],
            sensitivity_coverage=cov_metrics["sensitivity_coverage"],
            affected_positions=len(position_models),
            started_at=now,
            completed_at=now,
            position_results=[SectorPositionResultResponse.model_validate(p) for p in position_models],
            group_results=[SectorGroupResultResponse.model_validate(g) for g in group_models],
            attribution_results=[SectorAttributionResultResponse.model_validate(a) for a in attribution_models],
            warnings=[SectorWarningResponse.model_validate(w) for w in warnings]
        )
