"""
Services for M13.05 — Correlation Dashboard.

Implements presentation orchestration:
1. CorrelationUniverseService: Resolves holdings from M05 or custom instrument lists, enriched with M04 classifications.
2. CorrelationMatrixPresentationService: Consumes M07.05 authoritative matrix calculations and organizes display matrix, sorting, and comparison.
3. CorrelationClusterPresentationService: Computes agglomerative hierarchical clustering using d_ij = sqrt(2*(1 - rho)) without altering upstream matrix.
4. CorrelationOutlierService: Scans for high positive/negative threshold crossings, large period changes, and sign reversals.
5. CorrelationPairDetailService: Fetches pair-level statistics, scatter points, and rolling trend series.
6. CorrelationPreferenceAndInvestigationService: Persists saved universes, dashboard preferences, and investigation notes.
7. CorrelationDashboardCoordinator: Consolidated coordinator.
"""

from datetime import datetime, date, timezone
from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Optional, List, Dict, Any, Tuple
import logging
import numpy as np
import scipy.spatial.distance as ssd
import scipy.cluster.hierarchy as sch

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete

from backend.app.modules.dashboard_visualization.correlation_dashboard.schemas import (
    UniverseType,
    SamplingFrequency,
    CorrelationEstimatorType,
    ReturnDefinitionType,
    ClusteringMethod,
    HierarchicalLinkage,
    MatrixSortOrder,
    OutlierDetectionReason,
    UniverseInstrumentItem,
    UniverseResolveRequest,
    UniverseResolveResponse,
    MatrixCellMetadata,
    CorrelationMatrixViewRequest,
    CorrelationMatrixViewResponse,
    MatrixComparisonRequest,
    MatrixComparisonResponse,
    ClusterSummaryNode,
    DendrogramNode,
    CorrelationClusteringRequest,
    CorrelationClusteringResponse,
    CorrelationOutlierItem,
    CorrelationOutliersRequest,
    CorrelationOutliersResponse,
    ReturnObservationPair,
    CorrelationPairDetailResponse,
    CorrelationDashboardPreferenceCreate,
    CorrelationDashboardPreferenceResponse,
    CorrelationSavedUniverseCreate,
    CorrelationSavedUniverseResponse,
    CorrelationInvestigationCreate,
    CorrelationInvestigationResponse,
)
from backend.app.modules.dashboard_visualization.correlation_dashboard.models import (
    CorrelationDashboardPreference,
    CorrelationSavedUniverse,
    CorrelationSavedUniverseMember,
    CorrelationInvestigation,
)

# Upstream Authoritative M07.05 Services & M04 / M05 Models
from backend.app.modules.market_risk.correlation.services.service import CorrelationService
from backend.app.modules.market_risk.correlation.schemas import (
    MatrixCorrelationRequest,
    PairwiseCorrelationRequest,
    RollingCorrelationRequest,
)
from backend.app.modules.market_risk.correlation.models import CorrelationEstimator
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument
from backend.app.modules.instrument_reference_data.security_classification.models import (
    ClassificationNode,
    InstrumentClassificationAssignment,
)
from backend.app.modules.portfolio_management.position_management.models import (
    PositionBook,
    PositionStatus,
)
from backend.app.modules.instrument_reference_data.price_reference.models import PriceReferenceObservation

logger = logging.getLogger("correlation_dashboard_service")


# ---------------------------------------------------------------------------
# Color Map Helper (Institutional Blue-White-Red)
# ---------------------------------------------------------------------------

def _get_correlation_cell_hex(val: Optional[Decimal]) -> Optional[str]:
    if val is None:
        return "#334155" # Slate neutral for missing
    v = float(val)
    if v > 0.8:
        return "#14532d" # Deep emerald
    elif v > 0.5:
        return "#16a34a" # Green
    elif v > 0.2:
        return "#86efac" # Light green
    elif v >= -0.2:
        return "#f1f5f9" # Light gray neutral
    elif v >= -0.5:
        return "#fca5a5" # Light red
    elif v >= -0.8:
        return "#dc2626" # Red
    else:
        return "#7f1d1d" # Deep dark red


# ---------------------------------------------------------------------------
# 1. Universe Resolution Service
# ---------------------------------------------------------------------------

class CorrelationUniverseService:
    """Resolves eligible securities and factor mappings for correlation analysis."""

    @classmethod
    async def resolve_universe(
        cls,
        session: AsyncSession,
        req: UniverseResolveRequest,
    ) -> UniverseResolveResponse:
        resolved_ids: List[str] = []
        warnings: List[str] = []

        if req.universe_type == UniverseType.PORTFOLIO_HOLDINGS:
            if not req.portfolio_id:
                raise ValueError("portfolio_id is required when universe_type is PORTFOLIO_HOLDINGS")
            
            stmt = (
                select(PositionBook.instrument_id)
                .where(
                    and_(
                        PositionBook.portfolio_id == req.portfolio_id,
                        PositionBook.position_status == PositionStatus.OPEN,
                    )
                )
                .distinct()
            )
            rows = (await session.execute(stmt)).scalars().all()
            resolved_ids = list(rows)
            if not resolved_ids:
                warnings.append(f"No open positions found in portfolio '{req.portfolio_id}'.")

        elif req.universe_type == UniverseType.CUSTOM_SECURITIES:
            resolved_ids = req.instrument_ids or []
            if not resolved_ids:
                warnings.append("No instrument IDs provided for CUSTOM_SECURITIES universe.")

        elif req.universe_type == UniverseType.SECTOR_GROUP:
            if not req.sector_name:
                raise ValueError("sector_name is required when universe_type is SECTOR_GROUP")
            
            stmt = (
                select(InstrumentClassificationAssignment.instrument_id)
                .join(ClassificationNode, ClassificationNode.node_id == InstrumentClassificationAssignment.sector_node_id)
                .where(ClassificationNode.node_name.ilike(f"%{req.sector_name}%"))
                .distinct()
            )
            resolved_ids = list((await session.execute(stmt)).scalars().all())

        if not resolved_ids:
            return UniverseResolveResponse(
                universe_type=req.universe_type,
                portfolio_id=req.portfolio_id,
                total_eligible=0,
                total_excluded=0,
                instruments=[],
                warnings=warnings,
            )

        # Query Instruments Master & Classifications
        stmt = (
            select(
                Instrument.instrument_id,
                Instrument.short_name,
                Instrument.canonical_name,
                Instrument.issue_currency,
                Instrument.instrument_type,
                ClassificationNode.node_name.label("sector_name"),
            )
            .outerjoin(
                InstrumentClassificationAssignment,
                Instrument.instrument_id == InstrumentClassificationAssignment.instrument_id,
            )
            .outerjoin(
                ClassificationNode,
                ClassificationNode.node_id == InstrumentClassificationAssignment.sector_node_id,
            )
            .where(Instrument.instrument_id.in_(resolved_ids))
        )
        res_rows = (await session.execute(stmt)).all()

        instruments_out: List[UniverseInstrumentItem] = []
        for r in res_rows:
            market_loc = "US" if r.issue_currency == "USD" else "INDIA"
            exchange_loc = "NASDAQ" if r.issue_currency == "USD" else "NSE"
            item = UniverseInstrumentItem(
                instrument_id=r.instrument_id,
                symbol=r.short_name or r.instrument_id,
                instrument_name=r.canonical_name or r.short_name or r.instrument_id,
                exchange_code=exchange_loc,
                market=market_loc,
                asset_class="EQUITY",
                currency=r.issue_currency or "USD",
                sector_name=r.sector_name or "Unclassified",
                industry_name="General",
                is_eligible=True,
                data_quality_status="FRESH",
                observation_count=60,
            )
            instruments_out.append(item)

        return UniverseResolveResponse(
            universe_type=req.universe_type,
            portfolio_id=req.portfolio_id,
            total_eligible=len(instruments_out),
            total_excluded=0,
            instruments=instruments_out,
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# 2. Correlation Matrix Presentation Service
# ---------------------------------------------------------------------------

class CorrelationMatrixPresentationService:
    """Orchestrates authoritative matrix retrieval from M07.05 and supports comparison and sorting."""

    @classmethod
    async def get_matrix_view(
        cls,
        session: AsyncSession,
        req: CorrelationMatrixViewRequest,
    ) -> CorrelationMatrixViewResponse:
        corr_service = CorrelationService(session)
        estimator_m07 = CorrelationEstimator[req.estimator.value]

        m07_req = MatrixCorrelationRequest(
            portfolio_id=req.portfolio_id,
            asset_ids=req.instrument_ids,
            lookback_days=req.lookback_days,
            as_of=req.as_of,
            estimator=estimator_m07,
            repair_psd=req.repair_psd,
        )
        m07_res = await corr_service.calculate_matrix(m07_req)

        dim = m07_res.dimension
        raw_symbols = m07_res.asset_symbols
        raw_ids = m07_res.asset_ids
        matrix_data = m07_res.matrix

        # Matrix sorting and reordering
        order_indices = list(range(dim))
        warnings = []

        if req.sort_order == MatrixSortOrder.ALPHABETICAL:
            order_indices = sorted(range(dim), key=lambda idx: raw_symbols[idx].upper())
        elif req.sort_order == MatrixSortOrder.AVERAGE_CORRELATION:
            # Sort by average correlation with all other assets
            avg_corrs = []
            for i in range(dim):
                row_vals = [float(matrix_data[i][j]) for j in range(dim) if i != j]
                avg_corrs.append(np.mean(row_vals) if row_vals else 0.0)
            order_indices = sorted(range(dim), key=lambda idx: avg_corrs[idx], reverse=True)

        reordered_symbols = [raw_symbols[i] for i in order_indices]
        reordered_ids = [raw_ids[i] for i in order_indices]

        # Reordered 2D matrix
        reordered_matrix: List[List[Optional[Decimal]]] = []
        pair_metadata: List[MatrixCellMetadata] = []

        for i in order_indices:
            row: List[Optional[Decimal]] = []
            for j in order_indices:
                val = matrix_data[i][j]
                row.append(val)
                pair_metadata.append(
                    MatrixCellMetadata(
                        instrument_a_id=raw_ids[i],
                        instrument_b_id=raw_ids[j],
                        instrument_a_symbol=raw_symbols[i],
                        instrument_b_symbol=raw_symbols[j],
                        correlation=val,
                        observation_count=req.lookback_days,
                        data_quality_status="VALID" if val is not None else "INSUFFICIENT_OBSERVATIONS",
                        is_statistically_valid=val is not None,
                        color_hex=_get_correlation_cell_hex(val),
                    )
                )
            reordered_matrix.append(row)

        return CorrelationMatrixViewResponse(
            matrix_id=m07_res.matrix_id,
            portfolio_id=req.portfolio_id,
            as_of_date=m07_res.as_of_date,
            lookback_days=m07_res.lookback_days,
            frequency=req.frequency,
            estimator=req.estimator,
            return_type=req.return_type,
            dimension=dim,
            asset_ids=reordered_ids,
            asset_symbols=reordered_symbols,
            matrix=reordered_matrix,
            psd_status=m07_res.psd_status.value if hasattr(m07_res.psd_status, "value") else str(m07_res.psd_status),
            min_eigenvalue=m07_res.min_eigenvalue,
            max_eigenvalue=m07_res.max_eigenvalue,
            condition_number=m07_res.condition_number,
            average_correlation=m07_res.average_correlation,
            median_correlation=m07_res.median_correlation,
            completeness_ratio=m07_res.completeness_ratio,
            sort_order=req.sort_order,
            reordered_symbols=reordered_symbols,
            pair_metadata=pair_metadata,
            warnings=warnings,
        )

    @classmethod
    async def compare_matrices(
        cls,
        session: AsyncSession,
        req: MatrixComparisonRequest,
    ) -> MatrixComparisonResponse:
        corr_service = CorrelationService(session)
        estimator_m07 = CorrelationEstimator[req.estimator.value]

        # 1. Current Matrix
        req_curr = MatrixCorrelationRequest(
            portfolio_id=req.portfolio_id,
            asset_ids=req.instrument_ids,
            lookback_days=req.current_lookback_days,
            as_of=req.current_as_of,
            estimator=estimator_m07,
        )
        res_curr = await corr_service.calculate_matrix(req_curr)

        # 2. Comparison Matrix
        req_comp = MatrixCorrelationRequest(
            portfolio_id=req.portfolio_id,
            asset_ids=res_curr.asset_ids, # Match universe
            lookback_days=req.comparison_lookback_days,
            as_of=req.comparison_as_of,
            estimator=estimator_m07,
        )
        res_comp = await corr_service.calculate_matrix(req_comp)

        dim = res_curr.dimension
        diff_matrix: List[List[Optional[Decimal]]] = []
        abs_changes: List[Decimal] = []
        largest_pos = Decimal("0")
        largest_neg = Decimal("0")

        for i in range(dim):
            diff_row: List[Optional[Decimal]] = []
            for j in range(dim):
                c_val = res_curr.matrix[i][j]
                p_val = res_comp.matrix[i][j]
                if c_val is not None and p_val is not None:
                    d_val = c_val - p_val
                    diff_row.append(d_val)
                    if i != j:
                        abs_changes.append(abs(d_val))
                        if d_val > largest_pos:
                            largest_pos = d_val
                        if d_val < largest_neg:
                            largest_neg = d_val
                else:
                    diff_row.append(None)
            diff_matrix.append(diff_row)

        avg_abs = (sum(abs_changes) / Decimal(str(len(abs_changes)))) if abs_changes else Decimal("0")

        return MatrixComparisonResponse(
            portfolio_id=req.portfolio_id,
            dimension=dim,
            asset_ids=res_curr.asset_ids,
            asset_symbols=res_curr.asset_symbols,
            current_matrix=res_curr.matrix,
            comparison_matrix=res_comp.matrix,
            difference_matrix=diff_matrix,
            average_absolute_change=avg_abs.quantize(Decimal("0.0001")),
            largest_positive_change=largest_pos.quantize(Decimal("0.0001")),
            largest_negative_change=largest_neg.quantize(Decimal("0.0001")),
            warnings=[],
        )


# ---------------------------------------------------------------------------
# 3. Correlation Clustering Service
# ---------------------------------------------------------------------------

class CorrelationClusterPresentationService:
    """Computes hierarchical agglomerative clustering from correlation distance d = sqrt(2*(1 - rho))."""

    @classmethod
    async def compute_clusters(
        cls,
        session: AsyncSession,
        req: CorrelationClusteringRequest,
    ) -> CorrelationClusteringResponse:
        corr_service = CorrelationService(session)
        estimator_m07 = CorrelationEstimator[req.estimator.value]

        m07_req = MatrixCorrelationRequest(
            portfolio_id=req.portfolio_id,
            asset_ids=req.instrument_ids,
            lookback_days=req.lookback_days,
            as_of=req.as_of,
            estimator=estimator_m07,
            repair_psd=False,
        )
        m07_res = await corr_service.calculate_matrix(m07_req)

        dim = m07_res.dimension
        if dim < 2:
            raise ValueError("At least 2 instruments are required for correlation clustering.")

        # Convert to numpy correlation matrix
        corr_arr = np.zeros((dim, dim), dtype=np.float64)
        for i in range(dim):
            for j in range(dim):
                corr_arr[i, j] = float(m07_res.matrix[i][j])

        # Distance transformation: d_ij = sqrt(2 * (1 - rho_ij))
        dist_mat = np.sqrt(np.clip(2.0 * (1.0 - corr_arr), 0.0, 4.0))
        np.fill_diagonal(dist_mat, 0.0)

        # Linkage
        linkage_method = req.linkage.value.lower()
        condensed_dist = ssd.squareform(dist_mat, checks=False)
        Z = sch.linkage(condensed_dist, method=linkage_method)

        # Dendrogram ordering
        dendro = sch.dendrogram(Z, no_plot=True)
        leaves_order = dendro["leaves"]
        reordered_symbols = [m07_res.asset_symbols[i] for i in leaves_order]

        # Determine number of clusters
        num_clusters = req.target_clusters or max(2, min(dim, 4))
        cluster_assignments = sch.fcluster(Z, t=num_clusters, criterion="maxclust")

        # Build ClusterSummaryNode list
        clusters_map: Dict[int, List[int]] = {}
        for idx, c_id in enumerate(cluster_assignments):
            if c_id not in clusters_map:
                clusters_map[c_id] = []
            clusters_map[c_id].append(idx)

        cluster_nodes: List[ClusterSummaryNode] = []
        for c_id, member_indices in clusters_map.items():
            syms = [m07_res.asset_symbols[idx] for idx in member_indices]
            ids = [m07_res.asset_ids[idx] for idx in member_indices]
            
            # Compute average within-cluster correlation
            within_corrs = []
            for i_idx in member_indices:
                for j_idx in member_indices:
                    if i_idx < j_idx:
                        within_corrs.append(corr_arr[i_idx, j_idx])
            
            avg_w = Decimal(str(np.mean(within_corrs))) if within_corrs else Decimal("1.0")
            min_w = Decimal(str(np.min(within_corrs))) if within_corrs else Decimal("1.0")
            max_w = Decimal(str(np.max(within_corrs))) if within_corrs else Decimal("1.0")

            cluster_nodes.append(
                ClusterSummaryNode(
                    cluster_id=int(c_id),
                    cluster_name=f"Cluster {c_id} ({len(syms)} assets)",
                    member_instrument_ids=ids,
                    member_symbols=syms,
                    dominant_sector=None,
                    average_within_correlation=avg_w.quantize(Decimal("0.0001")),
                    min_within_correlation=min_w.quantize(Decimal("0.0001")),
                    max_within_correlation=max_w.quantize(Decimal("0.0001")),
                    member_count=len(syms),
                )
            )

        # Build DendrogramNodes for tree rendering
        tree_nodes: List[DendrogramNode] = []
        for i, row in enumerate(Z):
            tree_nodes.append(
                DendrogramNode(
                    node_id=dim + i,
                    left_child=int(row[0]),
                    right_child=int(row[1]),
                    distance=Decimal(str(row[2])).quantize(Decimal("0.0001")),
                    count=int(row[3]),
                )
            )

        return CorrelationClusteringResponse(
            portfolio_id=req.portfolio_id,
            as_of_date=m07_res.as_of_date,
            clustering_method=req.clustering_method,
            linkage=req.linkage,
            distance_formula=req.distance_formula,
            total_instruments=dim,
            number_of_clusters=len(cluster_nodes),
            clusters=sorted(cluster_nodes, key=lambda c: c.cluster_id),
            reordered_symbols=reordered_symbols,
            dendrogram_leaves=leaves_order,
            dendrogram_nodes=tree_nodes,
            silhouette_score=None,
            warnings=[],
        )


# ---------------------------------------------------------------------------
# 4. Correlation Outlier Inspection Service
# ---------------------------------------------------------------------------

class CorrelationOutlierService:
    """Scans pairwise correlations for extreme positive/negative relationships and material regime changes."""

    @classmethod
    async def detect_outliers(
        cls,
        session: AsyncSession,
        req: CorrelationOutliersRequest,
    ) -> CorrelationOutliersResponse:
        corr_service = CorrelationService(session)
        estimator_m07 = CorrelationEstimator[req.estimator.value]

        # 1. Fetch Current Matrix
        m07_req = MatrixCorrelationRequest(
            portfolio_id=req.portfolio_id,
            asset_ids=req.instrument_ids,
            lookback_days=req.lookback_days,
            as_of=req.as_of,
            estimator=estimator_m07,
        )
        res_curr = await corr_service.calculate_matrix(m07_req)

        # 2. Fetch Comparison Matrix for Change Detection
        comp_req = MatrixCorrelationRequest(
            portfolio_id=req.portfolio_id,
            asset_ids=res_curr.asset_ids,
            lookback_days=req.comparison_lookback_days,
            as_of=req.as_of,
            estimator=estimator_m07,
        )
        res_comp = await corr_service.calculate_matrix(comp_req)

        dim = res_curr.dimension
        high_pos_pairs: List[CorrelationOutlierItem] = []
        strong_neg_pairs: List[CorrelationOutlierItem] = []
        large_changes: List[CorrelationOutlierItem] = []
        sign_reversals: List[CorrelationOutlierItem] = []

        for i in range(dim):
            for j in range(i + 1, dim):
                c_val = res_curr.matrix[i][j]
                p_val = res_comp.matrix[i][j]
                sym_a = res_curr.asset_symbols[i]
                sym_b = res_curr.asset_symbols[j]
                id_a = res_curr.asset_ids[i]
                id_b = res_curr.asset_ids[j]

                if c_val is None:
                    continue

                # 1. High Positive Check
                if c_val >= req.high_positive_threshold:
                    high_pos_pairs.append(
                        CorrelationOutlierItem(
                            instrument_a_id=id_a,
                            instrument_b_id=id_b,
                            instrument_a_symbol=sym_a,
                            instrument_b_symbol=sym_b,
                            current_correlation=c_val,
                            reference_correlation=p_val,
                            delta_correlation=(c_val - p_val) if p_val is not None else None,
                            detection_reason=OutlierDetectionReason.HIGH_POSITIVE_CORRELATION,
                            threshold_crossed=req.high_positive_threshold,
                            observation_count=req.lookback_days,
                            quality_status="VALID",
                        )
                    )

                # 2. Strong Negative Check
                if c_val <= req.strong_negative_threshold:
                    strong_neg_pairs.append(
                        CorrelationOutlierItem(
                            instrument_a_id=id_a,
                            instrument_b_id=id_b,
                            instrument_a_symbol=sym_a,
                            instrument_b_symbol=sym_b,
                            current_correlation=c_val,
                            reference_correlation=p_val,
                            delta_correlation=(c_val - p_val) if p_val is not None else None,
                            detection_reason=OutlierDetectionReason.STRONG_NEGATIVE_CORRELATION,
                            threshold_crossed=req.strong_negative_threshold,
                            observation_count=req.lookback_days,
                            quality_status="VALID",
                        )
                    )

                # 3. Change Detection
                if p_val is not None:
                    delta = c_val - p_val
                    if abs(delta) >= req.large_change_threshold:
                        large_changes.append(
                            CorrelationOutlierItem(
                                instrument_a_id=id_a,
                                instrument_b_id=id_b,
                                instrument_a_symbol=sym_a,
                                instrument_b_symbol=sym_b,
                                current_correlation=c_val,
                                reference_correlation=p_val,
                                delta_correlation=delta,
                                detection_reason=OutlierDetectionReason.LARGE_CORRELATION_CHANGE,
                                threshold_crossed=req.large_change_threshold,
                                observation_count=req.lookback_days,
                                quality_status="VALID",
                            )
                        )

                    # 4. Sign Reversal
                    if (c_val > Decimal("0.20") and p_val < Decimal("-0.20")) or (c_val < Decimal("-0.20") and p_val > Decimal("0.20")):
                        sign_reversals.append(
                            CorrelationOutlierItem(
                                instrument_a_id=id_a,
                                instrument_b_id=id_b,
                                instrument_a_symbol=sym_a,
                                instrument_b_symbol=sym_b,
                                current_correlation=c_val,
                                reference_correlation=p_val,
                                delta_correlation=delta,
                                detection_reason=OutlierDetectionReason.SIGN_REVERSAL,
                                observation_count=req.lookback_days,
                                quality_status="VALID",
                            )
                        )

        total_flagged = len(high_pos_pairs) + len(strong_neg_pairs) + len(large_changes) + len(sign_reversals)

        return CorrelationOutliersResponse(
            portfolio_id=req.portfolio_id,
            as_of_date=res_curr.as_of_date,
            high_positive_pairs=sorted(high_pos_pairs, key=lambda x: x.current_correlation, reverse=True)[:25],
            strong_negative_pairs=sorted(strong_neg_pairs, key=lambda x: x.current_correlation)[:25],
            large_change_pairs=sorted(large_changes, key=lambda x: abs(x.delta_correlation or 0), reverse=True)[:25],
            sign_reversal_pairs=sign_reversals[:25],
            total_outliers_flagged=total_flagged,
        )


# ---------------------------------------------------------------------------
# 5. Correlation Pair Detail & Scatter Service
# ---------------------------------------------------------------------------

class CorrelationPairDetailService:
    """Assembles pair-level details, statistics, scatter points, and rolling trends."""

    @classmethod
    async def get_pair_detail(
        cls,
        session: AsyncSession,
        instrument_a_id: str,
        instrument_b_id: str,
        portfolio_id: Optional[str] = None,
        lookback_days: int = 60,
        estimator: CorrelationEstimatorType = CorrelationEstimatorType.PEARSON,
        as_of: Optional[date] = None,
    ) -> CorrelationPairDetailResponse:
        corr_service = CorrelationService(session)
        estimator_m07 = CorrelationEstimator[estimator.value]

        # 1. Authoritative Pairwise Calculation
        pair_req = PairwiseCorrelationRequest(
            asset_a_id=instrument_a_id,
            asset_b_id=instrument_b_id,
            lookback_days=lookback_days,
            as_of=as_of,
            estimator=estimator_m07,
            portfolio_id=portfolio_id,
        )
        pair_res = await corr_service.calculate_pairwise(pair_req)

        # 2. Rolling History
        rolling_points = []
        try:
            roll_req = RollingCorrelationRequest(
                asset_a_id=instrument_a_id,
                asset_b_id=instrument_b_id,
                window_days=min(30, max(10, lookback_days // 2)),
                history_lookback_days=max(90, lookback_days * 2),
                as_of=as_of,
                estimator=estimator_m07,
            )
            roll_res = await corr_service.calculate_rolling(roll_req)
            rolling_points = [p.model_dump() for p in roll_res.series]
        except Exception as e:
            logger.warning(f"Failed to calculate rolling series for {instrument_a_id}/{instrument_b_id}: {e}")

        # 3. Pull aligned price observations for scatter plot
        # Query last 60 observations from PriceReferenceObservation
        cutoff_date = (as_of or datetime.now(timezone.utc).date())
        obs_stmt = (
            select(
                PriceReferenceObservation.trading_date,
                PriceReferenceObservation.instrument_id,
                PriceReferenceObservation.price_value,
            )
            .where(
                and_(
                    PriceReferenceObservation.instrument_id.in_([instrument_a_id, instrument_b_id]),
                    PriceReferenceObservation.trading_date <= cutoff_date,
                )
            )
            .order_by(PriceReferenceObservation.trading_date.desc())
        )
        p_rows = (await session.execute(obs_stmt)).all()

        # Build date to price map
        a_prices: Dict[date, float] = {}
        b_prices: Dict[date, float] = {}
        for r in p_rows:
            if r.instrument_id == instrument_a_id and r.trading_date not in a_prices:
                a_prices[r.trading_date] = float(r.price_value)
            elif r.instrument_id == instrument_b_id and r.trading_date not in b_prices:
                b_prices[r.trading_date] = float(r.price_value)

        common_dates = sorted(list(set(a_prices.keys()).intersection(b_prices.keys())))
        
        # Calculate returns
        scatter_points: List[ReturnObservationPair] = []
        x_vals, y_vals = [], []
        for i in range(1, len(common_dates)):
            d_curr = common_dates[i]
            d_prev = common_dates[i - 1]
            ret_a = (a_prices[d_curr] / a_prices[d_prev]) - 1.0
            ret_b = (b_prices[d_curr] / b_prices[d_prev]) - 1.0
            x_vals.append(ret_a)
            y_vals.append(ret_b)
            scatter_points.append(
                ReturnObservationPair(
                    observation_date=d_curr,
                    return_a=Decimal(str(ret_a)).quantize(Decimal("0.0001")),
                    return_b=Decimal(str(ret_b)).quantize(Decimal("0.0001")),
                )
            )

        # Compute least-squares line slope & intercept if sufficient points
        slope, intercept = None, None
        if len(x_vals) >= 5 and np.var(x_vals) > 1e-8:
            fit = np.polyfit(x_vals, y_vals, 1)
            slope = Decimal(str(fit[0])).quantize(Decimal("0.0001"))
            intercept = Decimal(str(fit[1])).quantize(Decimal("0.0001"))

        return CorrelationPairDetailResponse(
            instrument_a_id=instrument_a_id,
            instrument_b_id=instrument_b_id,
            instrument_a_symbol=pair_res.asset_a_symbol,
            instrument_b_symbol=pair_res.asset_b_symbol,
            instrument_a_name=pair_res.asset_a_symbol,
            instrument_b_name=pair_res.asset_b_symbol,
            instrument_a_sector=None,
            instrument_b_sector=None,
            correlation=pair_res.correlation_coefficient,
            estimator=estimator,
            lookback_days=lookback_days,
            frequency=SamplingFrequency.DAILY,
            sample_size=pair_res.sample_size,
            p_value=pair_res.p_value,
            t_statistic=pair_res.t_statistic,
            std_error=pair_res.std_error,
            ci_lower_95=pair_res.ci_lower_95,
            ci_upper_95=pair_res.ci_upper_95,
            covariance=pair_res.covariance,
            volatility_a=pair_res.volatility_a,
            volatility_b=pair_res.volatility_b,
            scatter_points=scatter_points[-60:],
            least_squares_slope=slope,
            least_squares_intercept=intercept,
            rolling_points=rolling_points,
            data_quality_status="FRESH",
            provenance_module="M07.05 — Correlation Analysis",
        )


# ---------------------------------------------------------------------------
# 6. Preferences, Saved Universes & Investigation Service
# ---------------------------------------------------------------------------

class CorrelationPreferenceAndInvestigationService:
    """Manages dashboard persistence: saved universes, user preferences, and operational investigations."""

    @classmethod
    async def get_preferences(
        cls,
        session: AsyncSession,
        user_id: str,
    ) -> CorrelationDashboardPreferenceResponse:
        stmt = select(CorrelationDashboardPreference).where(CorrelationDashboardPreference.user_id == user_id)
        pref = (await session.execute(stmt)).scalar_one_or_none()
        if not pref:
            # Create default
            pref = CorrelationDashboardPreference(user_id=user_id)
            session.add(pref)
            await session.commit()
            await session.refresh(pref)

        return CorrelationDashboardPreferenceResponse.model_validate(pref)

    @classmethod
    async def save_preferences(
        cls,
        session: AsyncSession,
        user_id: str,
        data: CorrelationDashboardPreferenceCreate,
    ) -> CorrelationDashboardPreferenceResponse:
        stmt = select(CorrelationDashboardPreference).where(CorrelationDashboardPreference.user_id == user_id)
        pref = (await session.execute(stmt)).scalar_one_or_none()
        if not pref:
            pref = CorrelationDashboardPreference(user_id=user_id)
            session.add(pref)

        pref.dashboard_name = data.dashboard_name
        pref.default_portfolio_id = data.default_portfolio_id
        pref.default_universe_type = data.default_universe_type.value
        pref.default_lookback_days = data.default_lookback_days
        pref.sampling_frequency = data.sampling_frequency.value
        pref.correlation_method = data.correlation_method.value
        pref.return_definition = data.return_definition.value
        pref.min_observations = data.min_observations
        pref.display_configuration = data.display_configuration

        await session.commit()
        await session.refresh(pref)
        return CorrelationDashboardPreferenceResponse.model_validate(pref)

    @classmethod
    async def save_universe(
        cls,
        session: AsyncSession,
        user_id: str,
        data: CorrelationSavedUniverseCreate,
    ) -> CorrelationSavedUniverseResponse:
        univ = CorrelationSavedUniverse(
            user_id=user_id,
            universe_name=data.universe_name,
            description=data.description,
            universe_type=data.universe_type.value,
            portfolio_id=data.portfolio_id,
        )
        session.add(univ)
        await session.flush()

        for inst_id in set(data.instrument_ids):
            mem = CorrelationSavedUniverseMember(
                universe_id=univ.id,
                instrument_id=inst_id,
                member_type="SECURITY",
            )
            session.add(mem)

        await session.commit()
        await session.refresh(univ)

        member_ids = [m.instrument_id for m in univ.members]
        return CorrelationSavedUniverseResponse(
            id=univ.id,
            user_id=univ.user_id,
            universe_name=univ.universe_name,
            description=univ.description,
            universe_type=UniverseType(univ.universe_type),
            portfolio_id=univ.portfolio_id,
            member_instrument_ids=member_ids,
            member_count=len(member_ids),
            created_at=univ.created_at,
            updated_at=univ.updated_at,
        )

    @classmethod
    async def list_universes(
        cls,
        session: AsyncSession,
        user_id: str,
    ) -> List[CorrelationSavedUniverseResponse]:
        stmt = (
            select(CorrelationSavedUniverse)
            .where(CorrelationSavedUniverse.user_id == user_id)
            .order_by(CorrelationSavedUniverse.updated_at.desc())
        )
        universes = (await session.execute(stmt)).scalars().all()
        out = []
        for u in universes:
            m_ids = [m.instrument_id for m in u.members]
            out.append(
                CorrelationSavedUniverseResponse(
                    id=u.id,
                    user_id=u.user_id,
                    universe_name=u.universe_name,
                    description=u.description,
                    universe_type=UniverseType(u.universe_type),
                    portfolio_id=u.portfolio_id,
                    member_instrument_ids=m_ids,
                    member_count=len(m_ids),
                    created_at=u.created_at,
                    updated_at=u.updated_at,
                )
            )
        return out

    @classmethod
    async def delete_universe(
        cls,
        session: AsyncSession,
        universe_id: str,
        user_id: str,
    ) -> bool:
        stmt = (
            delete(CorrelationSavedUniverse)
            .where(
                and_(
                    CorrelationSavedUniverse.id == universe_id,
                    CorrelationSavedUniverse.user_id == user_id,
                )
            )
        )
        res = await session.execute(stmt)
        await session.commit()
        return res.rowcount > 0

    @classmethod
    async def record_investigation(
        cls,
        session: AsyncSession,
        user_id: str,
        data: CorrelationInvestigationCreate,
    ) -> CorrelationInvestigationResponse:
        inv = CorrelationInvestigation(
            user_id=user_id,
            portfolio_id=data.portfolio_id,
            instrument_a_id=data.instrument_a_id,
            instrument_b_id=data.instrument_b_id,
            correlation_value=data.correlation_value,
            previous_correlation=data.previous_correlation,
            correlation_method=data.correlation_method.value,
            lookback_days=data.lookback_days,
            sampling_frequency=data.sampling_frequency.value,
            observation_count=data.observation_count,
            detection_reason=data.detection_reason.value,
            source_result_reference=data.source_result_reference,
            user_notes=data.user_notes,
            status="OPEN",
        )
        session.add(inv)
        await session.commit()
        await session.refresh(inv)
        return CorrelationInvestigationResponse.model_validate(inv)


# ---------------------------------------------------------------------------
# 7. Consolidated Coordinator
# ---------------------------------------------------------------------------

class CorrelationDashboardService:
    """Unified service coordinator for M13.05 — Correlation Dashboard."""

    @classmethod
    async def resolve_universe(
        cls, session: AsyncSession, req: UniverseResolveRequest
    ) -> UniverseResolveResponse:
        return await CorrelationUniverseService.resolve_universe(session, req)

    @classmethod
    async def get_matrix_view(
        cls, session: AsyncSession, req: CorrelationMatrixViewRequest
    ) -> CorrelationMatrixViewResponse:
        return await CorrelationMatrixPresentationService.get_matrix_view(session, req)

    @classmethod
    async def compare_matrices(
        cls, session: AsyncSession, req: MatrixComparisonRequest
    ) -> MatrixComparisonResponse:
        return await CorrelationMatrixPresentationService.compare_matrices(session, req)

    @classmethod
    async def compute_clusters(
        cls, session: AsyncSession, req: CorrelationClusteringRequest
    ) -> CorrelationClusteringResponse:
        return await CorrelationClusterPresentationService.compute_clusters(session, req)

    @classmethod
    async def detect_outliers(
        cls, session: AsyncSession, req: CorrelationOutliersRequest
    ) -> CorrelationOutliersResponse:
        return await CorrelationOutlierService.detect_outliers(session, req)

    @classmethod
    async def get_pair_detail(
        cls,
        session: AsyncSession,
        instrument_a_id: str,
        instrument_b_id: str,
        portfolio_id: Optional[str] = None,
        lookback_days: int = 60,
        estimator: CorrelationEstimatorType = CorrelationEstimatorType.PEARSON,
        as_of: Optional[date] = None,
    ) -> CorrelationPairDetailResponse:
        return await CorrelationPairDetailService.get_pair_detail(
            session=session,
            instrument_a_id=instrument_a_id,
            instrument_b_id=instrument_b_id,
            portfolio_id=portfolio_id,
            lookback_days=lookback_days,
            estimator=estimator,
            as_of=as_of,
        )

    @classmethod
    async def get_preferences(cls, session: AsyncSession, user_id: str):
        return await CorrelationPreferenceAndInvestigationService.get_preferences(session, user_id)

    @classmethod
    async def save_preferences(cls, session: AsyncSession, user_id: str, data: CorrelationDashboardPreferenceCreate):
        return await CorrelationPreferenceAndInvestigationService.save_preferences(session, user_id, data)

    @classmethod
    async def save_universe(cls, session: AsyncSession, user_id: str, data: CorrelationSavedUniverseCreate):
        return await CorrelationPreferenceAndInvestigationService.save_universe(session, user_id, data)

    @classmethod
    async def list_universes(cls, session: AsyncSession, user_id: str):
        return await CorrelationPreferenceAndInvestigationService.list_universes(session, user_id)

    @classmethod
    async def delete_universe(cls, session: AsyncSession, universe_id: str, user_id: str):
        return await CorrelationPreferenceAndInvestigationService.delete_universe(session, universe_id, user_id)

    @classmethod
    async def record_investigation(cls, session: AsyncSession, user_id: str, data: CorrelationInvestigationCreate):
        return await CorrelationPreferenceAndInvestigationService.record_investigation(session, user_id, data)
