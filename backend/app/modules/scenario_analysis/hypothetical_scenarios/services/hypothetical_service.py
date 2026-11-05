"""
Hypothetical Scenarios Service (M10.02).
Orchestrates templates, shock building, target resolution, direct valuation repricing,
risk assumption transformation, and liquidity overlays.
"""

import uuid
import json
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from decimal import Decimal
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.hypothetical_models import (
    HypotheticalScenarioTemplate,
    HypotheticalScenarioTemplateVersion,
    HypotheticalScenarioRun,
    HypotheticalScenarioPositionResult,
    HypotheticalScenarioRiskResult,
    HypotheticalScenarioLiquidityResult,
    HypotheticalScenarioWarning,
    HypotheticalScenarioAuditLog
)
from ..schemas.hypothetical_schemas import (
    ScenarioTemplateCreate,
    ScenarioTemplateResponse,
    ScenarioExecutionRequest,
    PositionResultResponse,
    RiskResultResponse,
    LiquidityResultResponse,
    WarningResponse,
    ScenarioRunSummaryResponse
)
from ..repositories.hypothetical_repository import HypotheticalScenariosRepository
from ..calculations.hypothetical_math import (
    to_decimal,
    apply_price_shock,
    apply_factor_shock,
    apply_volatility_shock,
    validate_and_repair_correlation_matrix,
    reconstruct_covariance_matrix,
    compute_stressed_risk_metrics,
    revalue_hypothetical_position,
    apply_liquidity_overlay
)


class HypotheticalScenariosService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = HypotheticalScenariosRepository(db)

    async def create_template(self, req: ScenarioTemplateCreate) -> ScenarioTemplateResponse:
        existing = await self.repo.get_template_by_code(req.template_code)
        if existing:
            return ScenarioTemplateResponse.model_validate(existing)

        tmpl_id = f"htpl_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc)

        template = HypotheticalScenarioTemplate(
            id=tmpl_id,
            template_code=req.template_code,
            template_name=req.template_name,
            description=req.description,
            category=req.category,
            tags=req.tags,
            author_id=req.author_id,
            owner_id=req.owner_id,
            visibility=req.visibility,
            current_version="1.0.0",
            status="PUBLISHED",
            created_at=now_utc,
            updated_at=now_utc,
            published_at=now_utc
        )
        saved = await self.repo.create_template(template)

        # Store version 1.0.0 configuration
        config_data = {
            "price_shocks": [s.model_dump(mode="json") for s in (req.price_shocks or [])],
            "factor_shocks": [s.model_dump(mode="json") for s in (req.factor_shocks or [])],
            "volatility_shocks": [s.model_dump(mode="json") for s in (req.volatility_shocks or [])],
            "correlation_shocks": [s.model_dump(mode="json") for s in (req.correlation_shocks or [])],
            "liquidity_shocks": [s.model_dump(mode="json") for s in (req.liquidity_shocks or [])]
        }
        ver_model = HypotheticalScenarioTemplateVersion(
            id=f"hver_{uuid.uuid4().hex[:12]}",
            template_id=tmpl_id,
            version="1.0.0",
            configuration_json=json.dumps(config_data),
            created_by=req.author_id,
            created_at=now_utc,
            published_at=now_utc
        )
        await self.repo.save_template_version(ver_model)

        return ScenarioTemplateResponse.model_validate(saved)

    async def execute_scenario(self, req: ScenarioExecutionRequest) -> ScenarioRunSummaryResponse:
        run_id = f"hrun_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc)
        scenario_code = f"HYP_{now_utc.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"

        warnings: List[HypotheticalScenarioWarning] = []
        fx_shocks = req.fx_shocks or {}

        # ----------------------------------------------------
        # Channel A: Direct Valuation Repricing (Price & Factor)
        # ----------------------------------------------------
        position_models: List[HypotheticalScenarioPositionResult] = []
        pos_results_pnl = Decimal("0")
        
        # Build direct price shock map
        price_shock_inst_map: Dict[str, Any] = {}
        price_shock_sector_map: Dict[str, Any] = {}
        portfolio_price_shock: Optional[Any] = None

        for p_shock in (req.price_shocks or []):
            if p_shock.target_type == "INSTRUMENT":
                price_shock_inst_map[p_shock.target_identifier] = p_shock
            elif p_shock.target_type == "SECTOR":
                price_shock_sector_map[p_shock.target_identifier] = p_shock
            elif p_shock.target_type in ["PORTFOLIO", "MARKET"]:
                portfolio_price_shock = p_shock

        factor_shocks_map = {f.factor_name: f.shock_value for f in (req.factor_shocks or [])}

        for pos in req.positions:
            chosen_price_shock = Decimal("0")
            shock_method = "PERCENTAGE"
            
            # Determine applicable price shock with precedence
            if pos.instrument_id in price_shock_inst_map:
                p_def = price_shock_inst_map[pos.instrument_id]
                shock_method = p_def.shock_method
                chosen_price_shock = p_def.shock_value
            elif pos.sector and pos.sector in price_shock_sector_map:
                p_def = price_shock_sector_map[pos.sector]
                shock_method = p_def.shock_method
                chosen_price_shock = p_def.shock_value
            elif portfolio_price_shock:
                shock_method = portfolio_price_shock.shock_method
                chosen_price_shock = portfolio_price_shock.shock_value

            # Price revaluation
            scenario_price, p_ret = apply_price_shock(
                baseline_price=pos.baseline_price,
                shock_method=shock_method,
                shock_value=chosen_price_shock
            )

            # Factor shock calculation (if sensitivities supplied)
            factor_ret = Decimal("0")
            if pos.factor_sensitivities and factor_shocks_map:
                factor_ret = apply_factor_shock(pos.factor_sensitivities, factor_shocks_map)
                # If both price shock and factor shock exist, prevent silent double counting:
                # Add factor return as incremental return overlay:
                p_ret = p_ret + factor_ret
                scenario_price = (pos.baseline_price * (Decimal("1.0") + p_ret)).quantize(Decimal("0.00000001"))

            # Cross-currency conversion
            fx_ret = fx_shocks.get(pos.currency, Decimal("0"))
            base_ret = (Decimal("1.0") + p_ret) * (Decimal("1.0") + fx_ret) - Decimal("1.0")

            reval = revalue_hypothetical_position(
                signed_quantity=pos.signed_quantity,
                baseline_price=pos.baseline_price,
                scenario_price=scenario_price,
                baseline_nav=req.baseline_nav
            )

            pos_results_pnl += reval["scenario_pnl"]

            pos_model = HypotheticalScenarioPositionResult(
                id=f"hpos_{uuid.uuid4().hex[:12]}",
                scenario_run_id=run_id,
                instrument_id=pos.instrument_id,
                listing_id=pos.listing_id,
                signed_quantity=pos.signed_quantity,
                baseline_price=pos.baseline_price,
                scenario_price=scenario_price,
                price_shock=p_ret,
                factor_return=factor_ret if factor_ret != Decimal("0") else None,
                baseline_market_value=reval["baseline_market_value"],
                scenario_market_value=reval["scenario_market_value"],
                scenario_pnl=reval["scenario_pnl"],
                baseline_weight=reval["portfolio_weight"],
                scenario_contribution=reval["portfolio_contribution"],
                local_currency=pos.currency,
                base_currency_return=base_ret,
                created_at=now_utc
            )
            position_models.append(pos_model)

        scenario_nav = req.baseline_nav + pos_results_pnl
        scenario_ret = (pos_results_pnl / req.baseline_nav).quantize(Decimal("0.00000001"))

        # ----------------------------------------------------
        # Channel B: Risk-Model Assumption Shocks
        # ----------------------------------------------------
        risk_models: List[HypotheticalScenarioRiskResult] = []
        vol_shocks = req.volatility_shocks or []
        corr_shocks = req.correlation_shocks or []

        if vol_shocks or corr_shocks:
            N = len(req.positions)
            weights = np.array([float(p.baseline_weight) for p in position_models])
            
            # Baseline volatilities
            base_vols = np.array([float(p.baseline_volatility or Decimal("0.20")) for p in req.positions])
            stressed_vols = base_vols.copy()

            # Apply volatility shock
            if vol_shocks:
                v_def = vol_shocks[0]
                for i in range(N):
                    stressed_vols[i] = float(apply_volatility_shock(
                        baseline_volatility=Decimal(str(base_vols[i])),
                        shock_method=v_def.shock_method,
                        shock_value=v_def.shock_value
                    ))

            # Baseline correlation matrix (identity or equicorrelation baseline)
            corr_matrix = np.full((N, N), 0.3)
            np.fill_diagonal(corr_matrix, 1.0)

            # Apply correlation overrides
            inst_idx_map = {p.instrument_id: idx for idx, p in enumerate(req.positions)}
            for c_def in corr_shocks:
                if c_def.instrument_a in inst_idx_map and c_def.instrument_b in inst_idx_map:
                    idx_a = inst_idx_map[c_def.instrument_a]
                    idx_b = inst_idx_map[c_def.instrument_b]
                    corr_matrix[idx_a, idx_b] = float(c_def.target_correlation)
                    corr_matrix[idx_b, idx_a] = float(c_def.target_correlation)

            # Validate & Repair Correlation Matrix
            valid_corr, is_valid, diag = validate_and_repair_correlation_matrix(
                corr_matrix=corr_matrix,
                repair_policy=req.correlation_validation_policy
            )

            if diag.get("repaired"):
                warnings.append(HypotheticalScenarioWarning(
                    id=f"hwrn_{uuid.uuid4().hex[:12]}",
                    scenario_run_id=run_id,
                    warning_code="CORRELATION_REPAIRED",
                    severity="WARNING",
                    category="CORRELATION_REPAIR",
                    message=f"Non-PSD correlation matrix repaired (Frobenius norm repair: {diag['repair_magnitude']:.4f})"
                ))

            # Reconstruct Covariance Matrix & Compute Stressed Risk
            base_cov = reconstruct_covariance_matrix(base_vols, corr_matrix)
            stressed_cov = reconstruct_covariance_matrix(stressed_vols, valid_corr)

            base_risk = compute_stressed_risk_metrics(weights, req.baseline_nav, base_cov)
            stressed_risk = compute_stressed_risk_metrics(weights, req.baseline_nav, stressed_cov)

            metric_map = {
                "PORTFOLIO_VOLATILITY": "portfolio_volatility",
                "PARAMETRIC_VAR_95": "parametric_var",
                "PARAMETRIC_ES_95": "parametric_es"
            }
            for m_code, math_key in metric_map.items():
                b_val = base_risk[math_key]
                s_val = stressed_risk[math_key]
                diff_val = s_val - b_val
                risk_models.append(HypotheticalScenarioRiskResult(
                    id=f"hrsk_{uuid.uuid4().hex[:12]}",
                    scenario_run_id=run_id,
                    metric_code=m_code,
                    baseline_value=b_val,
                    scenario_value=s_val,
                    difference_value=diff_val,
                    unit="USD" if "VAR" in m_code or "ES" in m_code else "RATIO",
                    horizon="1D",
                    confidence_level=Decimal("0.95") if "95" in m_code else None,
                    methodology="PARAMETRIC_COVARIANCE",
                    created_at=now_utc
                ))

        # ----------------------------------------------------
        # Channel C: Liquidity & Execution Overlays
        # ----------------------------------------------------
        liquidity_models: List[HypotheticalScenarioLiquidityResult] = []
        if req.liquidity_shocks:
            liq_def = req.liquidity_shocks[0]
            for pos in req.positions:
                liq_overlay = apply_liquidity_overlay(
                    baseline_spread=pos.baseline_spread or Decimal("0.05"),
                    baseline_bid_depth=pos.baseline_bid_depth or Decimal("10000"),
                    baseline_ask_depth=pos.baseline_ask_depth or Decimal("10000"),
                    baseline_volume=pos.baseline_volume or Decimal("500000"),
                    spread_shock_pct=liq_def.spread_shock_pct,
                    depth_shock_pct=liq_def.depth_shock_pct,
                    volume_shock_pct=liq_def.volume_shock_pct
                )
                liquidity_models.append(HypotheticalScenarioLiquidityResult(
                    id=f"hliq_{uuid.uuid4().hex[:12]}",
                    scenario_run_id=run_id,
                    instrument_id=pos.instrument_id,
                    baseline_spread=pos.baseline_spread or Decimal("0.05"),
                    scenario_spread=liq_overlay["scenario_spread"],
                    baseline_bid_depth=pos.baseline_bid_depth or Decimal("10000"),
                    scenario_bid_depth=liq_overlay["scenario_bid_depth"],
                    baseline_ask_depth=pos.baseline_ask_depth or Decimal("10000"),
                    scenario_ask_depth=liq_overlay["scenario_ask_depth"],
                    baseline_volume=pos.baseline_volume or Decimal("500000"),
                    scenario_volume=liq_overlay["scenario_volume"],
                    created_at=now_utc
                ))

        run_status = "COMPLETED"
        if warnings:
            run_status = "COMPLETED_WITH_WARNINGS"

        run_model = HypotheticalScenarioRun(
            id=run_id,
            scenario_code=scenario_code,
            scenario_name=req.scenario_name,
            template_id=req.template_id,
            portfolio_id=req.portfolio_id,
            base_currency=req.base_currency,
            missing_data_policy=req.missing_data_policy,
            conflict_policy=req.conflict_policy,
            correlation_validation_policy=req.correlation_validation_policy,
            run_status=run_status,
            baseline_nav=req.baseline_nav,
            scenario_nav=scenario_nav,
            scenario_pnl=pos_results_pnl,
            scenario_return=scenario_ret,
            direct_coverage=Decimal("1.0"),
            unmapped_coverage=Decimal("0.0"),
            started_at=now_utc,
            completed_at=now_utc,
            created_by="QUANT_ANALYST"
        )

        await self.repo.save_run(run_model)
        await self.repo.save_positions(position_models)
        if risk_models:
            await self.repo.save_risk_results(risk_models)
        if liquidity_models:
            await self.repo.save_liquidity_results(liquidity_models)
        if warnings:
            await self.repo.save_warnings(warnings)

        caveat_text = (
            "Hypothetical scenarios represent user-configured synthetic shock assumptions rather than observed market facts. "
            "Volatility and correlation shocks modify risk-model inputs and do not create direct portfolio P&L. "
            "Stressed liquidity metrics represent execution overlays and do not mutate baseline market-data records."
        )

        return ScenarioRunSummaryResponse(
            run_id=run_id,
            scenario_code=scenario_code,
            scenario_name=req.scenario_name,
            portfolio_id=req.portfolio_id,
            base_currency=req.base_currency,
            run_status=run_status,
            baseline_nav=req.baseline_nav,
            scenario_nav=scenario_nav,
            scenario_pnl=pos_results_pnl,
            scenario_return=scenario_ret,
            direct_coverage=Decimal("1.0"),
            positions=[PositionResultResponse.model_validate(p) for p in position_models],
            risk_results=[RiskResultResponse.model_validate(r) for r in risk_models],
            liquidity_results=[LiquidityResultResponse.model_validate(l) for l in liquidity_models],
            warnings=[
                WarningResponse(
                    warning_code=w.warning_code,
                    severity=w.severity,
                    category=w.category,
                    message=w.message
                )
                for w in warnings
            ],
            caveat_summary=caveat_text
        )
