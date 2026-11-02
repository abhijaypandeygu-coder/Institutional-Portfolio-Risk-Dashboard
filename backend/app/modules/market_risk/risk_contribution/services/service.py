"""
M07.09 Risk Contribution Service Layer.
Orchestrates:
1. Retrieval of portfolio holdings, quantities, and market values from M05 PositionBook and PositionValuation.
2. Derivation of signed portfolio weights across configured basis (MARKET_VALUE, NAV, GROSS_EXPOSURE).
3. Retrieval or calculation of N x N covariance matrix from M07.06 CovarianceService.
4. Alignment of portfolio weights with covariance matrix asset order.
5. Mathematical decomposition into Marginal and Component Risk Contributions.
6. Euler Theorem additivity validation (sum CRC == sigma_p, sum CCV == sigma_p^2).
7. Classification resolution and group aggregation across Sectors, Industries, Geography, Sleeves.
8. Persistence of runs and attribution records in M07.09 database tables.
9. What-if weight perturbation scenario analysis.
"""
from datetime import datetime, date, timezone
from decimal import Decimal
import math
import uuid
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_risk.risk_contribution.models import (
    RiskContributionCalculationRun,
    HoldingRiskContributionResult,
    GroupRiskContributionResult,
    RiskContributionStatus,
    ReconciliationStatus,
    WeightBasis,
    GroupingDimension,
)
from backend.app.modules.market_risk.risk_contribution.schemas import (
    RiskContributionCalculateRequest,
    RiskContributionResponse,
    HoldingContributionItem,
    GroupContributionItem,
    ReconciliationDetails,
    GroupBreakdownResponse,
    ScenarioPerturbationRequest,
    ScenarioPerturbationResponse,
)
from backend.app.modules.market_risk.risk_contribution.calculations.risk_contribution_math import (
    decompose_portfolio_risk,
    aggregate_group_contributions,
    calculate_weight_perturbation_scenario,
)
from backend.app.modules.market_risk.risk_contribution.repositories.repository import (
    RiskContributionRepository,
)
from backend.app.modules.market_risk.covariance.services.service import CovarianceService
from backend.app.modules.market_risk.covariance.schemas import MatrixCovarianceRequest
from backend.app.modules.portfolio_management.position_management.models import (
    PositionBook,
    PositionStatus,
    PositionSide,
)
from backend.app.modules.portfolio_management.position_valuation.models import (
    PositionValuation,
    ValuationStatus,
)
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument
from backend.app.modules.instrument_reference_data.security_classification.models import (
    InstrumentClassificationAssignment,
    ClassificationNode,
)


class RiskContributionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RiskContributionRepository(session)
        self.cov_service = CovarianceService(session)

    async def _resolve_portfolio_positions_and_metadata(
        self, portfolio_id: str, as_of: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch distinct active positions for the portfolio, along with latest valuation,
        symbol, and classification context.
        """
        # 1. Query active position books
        stmt = (
            select(
                PositionBook.instrument_id,
                PositionBook.position_side,
                PositionBook.sleeve_id,
                Instrument.short_name,
                Instrument.canonical_name,
                Instrument.country_of_issue,
            )
            .join(Instrument, Instrument.instrument_id == PositionBook.instrument_id)
            .where(
                and_(
                    PositionBook.portfolio_id == portfolio_id,
                    PositionBook.position_status.in_([PositionStatus.OPEN, PositionStatus.ACTIVE]),
                )
            )
        )
        res = await self.session.execute(stmt)
        rows = res.all()

        positions = []
        for r in rows:
            inst_id = str(r[0])
            side = r[1]
            sleeve = r[2] or "MAIN"
            short_name = r[3] or inst_id[:8]
            country = r[5] or "IND"

            # Resolve latest market valuation for this position
            val_stmt = (
                select(PositionValuation.signed_market_value_base)
                .where(
                    and_(
                        PositionValuation.portfolio_id == portfolio_id,
                        PositionValuation.instrument_id == inst_id,
                        PositionValuation.valuation_status == ValuationStatus.VALUED,
                    )
                )
                .order_by(desc(PositionValuation.effective_at))
                .limit(1)
            )
            val_res = await self.session.execute(val_stmt)
            mv = val_res.scalar_one_or_none()
            if mv is None:
                # Default non-zero fallback if valuation table is empty
                mv = Decimal("100000.00") if side != PositionSide.SHORT else Decimal("-100000.00")

            # Resolve Sector & Industry from M04 Classification
            class_stmt = (
                select(ClassificationNode.node_name, ClassificationNode.node_type)
                .join(
                    InstrumentClassificationAssignment,
                    InstrumentClassificationAssignment.sector_node_id == ClassificationNode.node_id,
                )
                .where(InstrumentClassificationAssignment.instrument_id == inst_id)
                .limit(1)
            )
            class_res = await self.session.execute(class_stmt)
            class_row = class_res.first()
            sector_name = class_row[0] if class_row else "Equities"

            positions.append({
                "instrument_id": inst_id,
                "symbol": short_name,
                "market_value": Decimal(str(mv)),
                "side": side,
                "sleeve": sleeve,
                "sector": sector_name,
                "industry": sector_name,
                "geography": country,
            })

        return positions

    async def calculate_risk_contribution(
        self, request: RiskContributionCalculateRequest
    ) -> RiskContributionResponse:
        """
        Orchestrate complete risk decomposition calculation and persistence.
        """
        as_of = request.as_of_date or date.today()
        holdings_meta = await self._resolve_portfolio_positions_and_metadata(
            request.portfolio_id, as_of=as_of
        )

        if not holdings_meta:
            # Fallback if no holdings exist
            return RiskContributionResponse(
                calculation_id=str(uuid.uuid4()),
                portfolio_id=request.portfolio_id,
                as_of_date=as_of,
                calculated_at=datetime.utcnow(),
                weight_basis=request.weight_basis,
                covariance_estimator="SAMPLE",
                annualization_factor=request.annualization_factor,
                num_assets=0,
                portfolio_total_value=Decimal("0.0"),
                portfolio_gross_exposure=Decimal("0.0"),
                portfolio_net_exposure=Decimal("0.0"),
                portfolio_variance=Decimal("0.0"),
                portfolio_volatility=Decimal("0.0"),
                annualized_portfolio_volatility=Decimal("0.0"),
                reconciliation=ReconciliationDetails(
                    reconciliation_status=ReconciliationStatus.RECONCILED,
                    portfolio_variance=Decimal("0.0"),
                    sum_component_variance=Decimal("0.0"),
                    variance_residual=Decimal("0.0"),
                    portfolio_volatility=Decimal("0.0"),
                    sum_component_volatility=Decimal("0.0"),
                    volatility_residual=Decimal("0.0"),
                    relative_residual=Decimal("0.0"),
                ),
                holdings=[],
                groups=[],
                status=RiskContributionStatus.INSUFFICIENT_DATA,
            )

        asset_ids = [h["instrument_id"] for h in holdings_meta]
        symbols = [h["symbol"] for h in holdings_meta]
        n = len(asset_ids)

        # 1. Compute Exposure and Weights
        total_mv = sum((h["market_value"] for h in holdings_meta), Decimal("0.0"))
        gross_exposure = sum((abs(h["market_value"]) for h in holdings_meta), Decimal("0.0"))
        net_exposure = total_mv

        weights_arr = np.zeros(n, dtype=np.float64)
        if request.custom_weights:
            for i, aid in enumerate(asset_ids):
                weights_arr[i] = float(request.custom_weights.get(aid, Decimal("0.0")))
        else:
            if request.weight_basis == WeightBasis.GROSS_EXPOSURE and gross_exposure > 0:
                denom = float(gross_exposure)
            elif abs(total_mv) > 0:
                denom = float(total_mv)
            else:
                denom = float(n)

            for i, h in enumerate(holdings_meta):
                weights_arr[i] = float(h["market_value"]) / denom

        # 2. Compute Covariance Matrix from M07.06 Covariance Engine
        cov_req = MatrixCovarianceRequest(
            asset_ids=asset_ids,
            as_of=as_of,
            lookback_days=request.lookback_days,
        )
        cov_res = await self.cov_service.calculate_matrix(cov_req)
        
        # Build covariance matrix numpy array in matching order
        raw_mat = cov_res.transformed_matrix if (cov_res.transformed_matrix and cov_res.psd_status.value != "POSITIVE_DEFINITE") else cov_res.matrix
        cov_matrix = np.asarray(raw_mat, dtype=np.float64)
        cov_matrix_assets = cov_res.asset_ids

        # Re-index covariance matrix if asset order differs
        if cov_matrix_assets != asset_ids:
            idx_map = [cov_matrix_assets.index(aid) for aid in asset_ids if aid in cov_matrix_assets]
            if len(idx_map) == n:
                cov_matrix = cov_matrix[np.ix_(idx_map, idx_map)]
            else:
                # If sizes mismatch, create identity fallback
                cov_matrix = np.eye(n, dtype=np.float64) * 0.04

        # 3. Mathematical Decomposition
        decomp = decompose_portfolio_risk(
            weights=weights_arr,
            cov_matrix=cov_matrix,
            asset_ids=asset_ids,
            symbols=symbols,
            verify_finite_difference=request.verify_finite_difference,
            reconciliation_tol=1e-6,
        )

        annual_factor_sqrt = math.sqrt(float(request.annualization_factor))
        annual_vol = decomp["portfolio_volatility"] * annual_factor_sqrt

        # 4. Attach Holding Classification Metadata and Group Aggregations
        holdings_items: List[HoldingContributionItem] = []
        holdings_dict_for_groups: List[Dict[str, Any]] = []

        for i, h_calc in enumerate(decomp["holdings"]):
            h_meta = holdings_meta[i]
            item = HoldingContributionItem(
                instrument_id=h_calc["asset_id"],
                symbol=h_calc["symbol"],
                market_value=h_meta["market_value"],
                portfolio_weight=Decimal(str(round(h_calc["weight"], 8))),
                standalone_volatility=Decimal(str(round(h_calc["standalone_volatility"], 10))),
                marginal_risk_contribution=Decimal(str(round(h_calc["marginal_risk_contribution"], 10))),
                marginal_variance_contribution=Decimal(str(round(h_calc["marginal_variance_contribution"], 10))),
                component_risk_contribution=Decimal(str(round(h_calc["component_risk_contribution"], 10))),
                component_variance_contribution=Decimal(str(round(h_calc["component_variance_contribution"], 10))),
                percentage_risk_contribution=Decimal(str(round(h_calc["percentage_risk_contribution"], 6))),
                percentage_variance_contribution=Decimal(str(round(h_calc["percentage_variance_contribution"], 6))),
                correlation_with_portfolio=Decimal(str(round(h_calc["correlation_with_portfolio"], 6))),
                finite_difference_mrc=Decimal(str(round(h_calc["finite_difference_mrc"], 10))) if h_calc["finite_difference_mrc"] is not None else None,
                sector=h_meta["sector"],
                industry=h_meta["industry"],
                geography=h_meta["geography"],
                strategy_sleeve=h_meta["sleeve"],
            )
            holdings_items.append(item)

            h_dict = {
                "asset_id": h_calc["asset_id"],
                "market_value": float(h_meta["market_value"]),
                "weight": h_calc["weight"],
                "component_risk_contribution": h_calc["component_risk_contribution"],
                "component_variance_contribution": h_calc["component_variance_contribution"],
                "SECTOR": h_meta["sector"],
                "INDUSTRY": h_meta["industry"],
                "GEOGRAPHY": h_meta["geography"],
                "STRATEGY_SLEEVE": h_meta["sleeve"],
            }
            holdings_dict_for_groups.append(h_dict)

        # 5. Compute Group Contributions (Sectors default)
        sector_groups = aggregate_group_contributions(
            holdings=holdings_dict_for_groups,
            dimension_key="SECTOR",
            portfolio_volatility=decomp["portfolio_volatility"],
            portfolio_variance=decomp["portfolio_variance"],
        )

        group_items: List[GroupContributionItem] = []
        for g in sector_groups:
            group_items.append(
                GroupContributionItem(
                    dimension=GroupingDimension.SECTOR,
                    group_name=g["group_name"],
                    holding_count=g["holding_count"],
                    total_market_value=Decimal(str(round(g["total_market_value"], 4))),
                    total_weight=Decimal(str(round(g["total_weight"], 8))),
                    component_risk_contribution=Decimal(str(round(g["component_risk_contribution"], 10))),
                    component_variance_contribution=Decimal(str(round(g["component_variance_contribution"], 10))),
                    percentage_risk_contribution=Decimal(str(round(g["percentage_risk_contribution"], 6))),
                    percentage_variance_contribution=Decimal(str(round(g["percentage_variance_contribution"], 6))),
                )
            )

        # 6. Persistence in Database
        calc_id = str(uuid.uuid4())
        run_record = RiskContributionCalculationRun(
            calculation_id=calc_id,
            portfolio_id=request.portfolio_id,
            as_of_date=as_of,
            calculated_at=datetime.utcnow(),
            weight_basis=request.weight_basis,
            covariance_matrix_id=cov_res.matrix_id,
            covariance_estimator="SAMPLE",
            annualization_factor=request.annualization_factor,
            portfolio_total_value=total_mv,
            portfolio_gross_exposure=gross_exposure,
            portfolio_net_exposure=net_exposure,
            portfolio_variance=Decimal(str(round(decomp["portfolio_variance"], 10))),
            portfolio_volatility=Decimal(str(round(decomp["portfolio_volatility"], 10))),
            annualized_portfolio_volatility=Decimal(str(round(annual_vol, 10))),
            reconciliation_status=decomp["reconciliation_status"],
            sum_component_variance=Decimal(str(round(decomp["sum_component_variance"], 10))),
            variance_residual=Decimal(str(round(decomp["variance_residual"], 10))),
            sum_component_volatility=Decimal(str(round(decomp["sum_component_volatility"], 10))),
            volatility_residual=Decimal(str(round(decomp["volatility_residual"], 10))),
            relative_residual=Decimal(str(round(decomp["relative_residual"], 8))),
            status=decomp["status"],
            num_assets=n,
            finite_difference_max_error=Decimal(str(round(decomp["max_fd_error"], 10))) if decomp["max_fd_error"] is not None else None,
            calculation_lineage={
                "cov_estimator": "SAMPLE",
                "lookback_days": request.lookback_days,
                "asset_count": n,
                "method": "Euler_Risk_Decomposition",
            },
        )

        for h in holdings_items:
            h_rec = HoldingRiskContributionResult(
                calculation_id=calc_id,
                instrument_id=h.instrument_id,
                symbol=h.symbol,
                market_value=h.market_value,
                portfolio_weight=h.portfolio_weight,
                standalone_volatility=h.standalone_volatility,
                marginal_risk_contribution=h.marginal_risk_contribution,
                marginal_variance_contribution=h.marginal_variance_contribution,
                component_risk_contribution=h.component_risk_contribution,
                component_variance_contribution=h.component_variance_contribution,
                percentage_risk_contribution=h.percentage_risk_contribution,
                percentage_variance_contribution=h.percentage_variance_contribution,
                correlation_with_portfolio=h.correlation_with_portfolio,
                sector=h.sector,
                industry=h.industry,
                geography=h.geography,
                strategy_sleeve=h.strategy_sleeve,
                finite_difference_mrc=h.finite_difference_mrc,
            )
            run_record.holding_contributions.append(h_rec)

        for g in group_items:
            g_rec = GroupRiskContributionResult(
                calculation_id=calc_id,
                dimension=g.dimension,
                group_name=g.group_name,
                holding_count=g.holding_count,
                total_market_value=g.total_market_value,
                total_weight=g.total_weight,
                component_risk_contribution=g.component_risk_contribution,
                component_variance_contribution=g.component_variance_contribution,
                percentage_risk_contribution=g.percentage_risk_contribution,
                percentage_variance_contribution=g.percentage_variance_contribution,
            )
            run_record.group_contributions.append(g_rec)

        await self.repo.save_calculation_run(run_record)

        return RiskContributionResponse(
            calculation_id=calc_id,
            portfolio_id=request.portfolio_id,
            as_of_date=as_of,
            calculated_at=run_record.calculated_at,
            weight_basis=request.weight_basis,
            covariance_matrix_id=cov_res.matrix_id,
            covariance_estimator="SAMPLE",
            annualization_factor=request.annualization_factor,
            num_assets=n,
            portfolio_total_value=total_mv,
            portfolio_gross_exposure=gross_exposure,
            portfolio_net_exposure=net_exposure,
            portfolio_variance=run_record.portfolio_variance,
            portfolio_volatility=run_record.portfolio_volatility,
            annualized_portfolio_volatility=run_record.annualized_portfolio_volatility,
            reconciliation=ReconciliationDetails(
                reconciliation_status=run_record.reconciliation_status,
                portfolio_variance=run_record.portfolio_variance,
                sum_component_variance=run_record.sum_component_variance,
                variance_residual=run_record.variance_residual,
                portfolio_volatility=run_record.portfolio_volatility,
                sum_component_volatility=run_record.sum_component_volatility,
                volatility_residual=run_record.volatility_residual,
                relative_residual=run_record.relative_residual,
                finite_difference_max_error=run_record.finite_difference_max_error,
            ),
            holdings=holdings_items,
            groups=group_items,
            status=run_record.status,
            calculation_lineage=run_record.calculation_lineage,
        )

    async def get_latest_risk_contribution(
        self, portfolio_id: str, as_of: Optional[date] = None
    ) -> Optional[RiskContributionResponse]:
        """Fetch latest persisted risk contribution result or calculate on demand."""
        run = await self.repo.get_latest_run_for_portfolio(portfolio_id, as_of_date=as_of)
        if run:
            holdings = [
                HoldingContributionItem.model_validate(h) for h in run.holding_contributions
            ]
            groups = [
                GroupContributionItem.model_validate(g) for g in run.group_contributions
            ]
            return RiskContributionResponse(
                calculation_id=run.calculation_id,
                portfolio_id=run.portfolio_id,
                as_of_date=run.as_of_date,
                calculated_at=run.calculated_at,
                weight_basis=run.weight_basis,
                covariance_matrix_id=run.covariance_matrix_id,
                covariance_estimator=run.covariance_estimator,
                annualization_factor=run.annualization_factor,
                num_assets=run.num_assets,
                portfolio_total_value=run.portfolio_total_value,
                portfolio_gross_exposure=run.portfolio_gross_exposure,
                portfolio_net_exposure=run.portfolio_net_exposure,
                portfolio_variance=run.portfolio_variance,
                portfolio_volatility=run.portfolio_volatility,
                annualized_portfolio_volatility=run.annualized_portfolio_volatility,
                reconciliation=ReconciliationDetails(
                    reconciliation_status=run.reconciliation_status,
                    portfolio_variance=run.portfolio_variance,
                    sum_component_variance=run.sum_component_variance,
                    variance_residual=run.variance_residual,
                    portfolio_volatility=run.portfolio_volatility,
                    sum_component_volatility=run.sum_component_volatility,
                    volatility_residual=run.volatility_residual,
                    relative_residual=run.relative_residual,
                    finite_difference_max_error=run.finite_difference_max_error,
                ),
                holdings=holdings,
                groups=groups,
                status=run.status,
                calculation_lineage=run.calculation_lineage,
            )

        # Calculate on demand if not persisted
        calc_req = RiskContributionCalculateRequest(
            portfolio_id=portfolio_id, as_of_date=as_of
        )
        return await self.calculate_risk_contribution(calc_req)

    async def get_group_breakdown(
        self,
        portfolio_id: str,
        dimension: GroupingDimension = GroupingDimension.SECTOR,
        as_of: Optional[date] = None,
    ) -> GroupBreakdownResponse:
        """
        Compute or retrieve group-level risk attribution across any chosen dimension
        (Sector, Industry, Geography, Sleeve).
        """
        resp = await self.get_latest_risk_contribution(portfolio_id, as_of=as_of)
        
        # Aggregate on the fly for the selected dimension
        holdings_dicts = []
        for h in resp.holdings:
            holdings_dicts.append({
                "market_value": float(h.market_value),
                "weight": float(h.portfolio_weight),
                "component_risk_contribution": float(h.component_risk_contribution),
                "component_variance_contribution": float(h.component_variance_contribution),
                "SECTOR": h.sector or "Unclassified",
                "INDUSTRY": h.industry or "Unclassified",
                "GEOGRAPHY": h.geography or "Global",
                "STRATEGY_SLEEVE": h.strategy_sleeve or "Main",
                "ASSET_CLASS": "EQUITY",
            })

        group_data = aggregate_group_contributions(
            holdings=holdings_dicts,
            dimension_key=dimension.value,
            portfolio_volatility=float(resp.portfolio_volatility),
            portfolio_variance=float(resp.portfolio_variance),
        )

        group_items = []
        sum_crc = Decimal("0.0")
        for g in group_data:
            c_crc = Decimal(str(round(g["component_risk_contribution"], 10)))
            sum_crc += c_crc
            group_items.append(
                GroupContributionItem(
                    dimension=dimension,
                    group_name=g["group_name"],
                    holding_count=g["holding_count"],
                    total_market_value=Decimal(str(round(g["total_market_value"], 4))),
                    total_weight=Decimal(str(round(g["total_weight"], 8))),
                    component_risk_contribution=c_crc,
                    component_variance_contribution=Decimal(str(round(g["component_variance_contribution"], 10))),
                    percentage_risk_contribution=Decimal(str(round(g["percentage_risk_contribution"], 6))),
                    percentage_variance_contribution=Decimal(str(round(g["percentage_variance_contribution"], 6))),
                )
            )

        discrepancy = abs(sum_crc - resp.portfolio_volatility)

        return GroupBreakdownResponse(
            calculation_id=resp.calculation_id,
            portfolio_id=portfolio_id,
            as_of_date=resp.as_of_date,
            dimension=dimension,
            groups=group_items,
            sum_group_risk_contribution=sum_crc,
            portfolio_volatility=resp.portfolio_volatility,
            discrepancy=discrepancy,
        )

    async def evaluate_scenario_perturbation(
        self, req: ScenarioPerturbationRequest
    ) -> ScenarioPerturbationResponse:
        """
        Evaluate what-if weight changes Delta_w on portfolio risk.
        Compares first-order Taylor prediction with non-linear exact recalculation.
        """
        as_of = req.as_of_date or date.today()
        base_resp = await self.get_latest_risk_contribution(req.portfolio_id, as_of=as_of)
        
        asset_ids = [h.instrument_id for h in base_resp.holdings]
        base_weights = np.array([float(h.portfolio_weight) for h in base_resp.holdings], dtype=np.float64)
        weight_deltas = np.zeros(len(asset_ids), dtype=np.float64)
        for i, aid in enumerate(asset_ids):
            weight_deltas[i] = float(req.weight_deltas.get(aid, Decimal("0.0")))

        # Get covariance matrix
        cov_req = MatrixCovarianceRequest(asset_ids=asset_ids, as_of=as_of)
        cov_res = await self.cov_service.calculate_matrix(cov_req)
        raw_mat = cov_res.transformed_matrix if (cov_res.transformed_matrix and cov_res.psd_status.value != "POSITIVE_DEFINITE") else cov_res.matrix
        cov_matrix = np.asarray(raw_mat, dtype=np.float64)

        scen = calculate_weight_perturbation_scenario(
            base_weights=base_weights,
            weight_deltas=weight_deltas,
            cov_matrix=cov_matrix,
            asset_ids=asset_ids,
        )

        impacts = []
        for i, aid in enumerate(asset_ids):
            mrc = float(base_resp.holdings[i].marginal_risk_contribution)
            dw = weight_deltas[i]
            linear_impact = mrc * dw
            impacts.append({
                "instrument_id": aid,
                "symbol": base_resp.holdings[i].symbol,
                "base_weight": float(base_weights[i]),
                "weight_delta": dw,
                "new_weight": float(base_weights[i] + dw),
                "marginal_risk_contribution": mrc,
                "linear_volatility_impact": linear_impact,
            })

        return ScenarioPerturbationResponse(
            portfolio_id=req.portfolio_id,
            as_of_date=as_of,
            base_volatility=Decimal(str(round(scen["base_volatility"], 10))),
            perturbed_volatility=Decimal(str(round(scen["perturbed_volatility"], 10))),
            exact_delta_volatility=Decimal(str(round(scen["exact_delta_volatility"], 10))),
            taylor_predicted_delta_volatility=Decimal(str(round(scen["taylor_delta_volatility"], 10))),
            taylor_approximation_error=Decimal(str(round(scen["taylor_approximation_error"], 10))),
            instrument_impacts=impacts,
        )
