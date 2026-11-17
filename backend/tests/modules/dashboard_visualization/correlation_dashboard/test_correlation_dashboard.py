"""
Integration, statistical, and operational test suite for M13.05 — Correlation Dashboard.

Validates:
1. Universe Resolution: Resolving holdings from M05 position books and custom universe lists.
2. Correlation Matrix Presentation: M07.05 authoritative calculation consumption, PSD diagnostics, sorting.
3. Period Matrix Comparison: Difference matrix ΔC = C_curr - C_comp, largest changes.
4. Correlation Clustering: Hierarchical agglomerative clustering using d_ij = sqrt(2*(1 - rho)) and dendrogram tree.
5. Outlier & Change Detection: High positive (>0.70), negative (<-0.50), large change (>0.30) pairs.
6. Pair Detail & Scatter: Pair statistics, aligned price returns, least-squares slope.
7. Persistence: User preferences, saved universes, and investigation log.
8. REST API Endpoints:
   - POST /api/v1/dashboard/correlation/universe/resolve
   - POST /api/v1/dashboard/correlation/matrix
   - POST /api/v1/dashboard/correlation/compare
   - POST /api/v1/dashboard/correlation/clusters
   - POST /api/v1/dashboard/correlation/outliers
   - GET  /api/v1/dashboard/correlation/pair/{a}/{b}
   - GET/PUT /api/v1/dashboard/correlation/preferences
   - POST/GET/DELETE /api/v1/dashboard/correlation/universes
   - POST /api/v1/dashboard/correlation/investigations
"""

from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.main import app
from backend.app.modules.dashboard_visualization.correlation_dashboard.services.correlation_dashboard_service import (
    CorrelationDashboardService,
    CorrelationUniverseService,
    CorrelationMatrixPresentationService,
    CorrelationClusterPresentationService,
    CorrelationOutlierService,
    CorrelationPairDetailService,
    CorrelationPreferenceAndInvestigationService,
)
from backend.app.modules.dashboard_visualization.correlation_dashboard.schemas import (
    UniverseType,
    SamplingFrequency,
    CorrelationEstimatorType,
    MatrixSortOrder,
    ClusteringMethod,
    HierarchicalLinkage,
    OutlierDetectionReason,
    UniverseResolveRequest,
    CorrelationMatrixViewRequest,
    MatrixComparisonRequest,
    CorrelationClusteringRequest,
    CorrelationOutliersRequest,
    CorrelationDashboardPreferenceCreate,
    CorrelationSavedUniverseCreate,
    CorrelationInvestigationCreate,
)
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument
from backend.app.modules.instrument_reference_data.price_reference.models import (
    PriceReferenceObservation,
    PriceReferenceType,
)
from backend.app.modules.portfolio_management.portfolio_creation.models import (
    Portfolio,
    PortfolioLifecycleStatus,
    PortfolioTypeEnum,
)
from backend.app.modules.portfolio_management.position_management.models import (
    PositionBook,
    PositionStatus,
    PositionSide,
)


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_correlation_dashboard_services_and_analytics():
    ts = int(datetime.now().timestamp())
    inst_a_id = f"INST_CD_AAPL_{ts}"
    inst_b_id = f"INST_CD_MSFT_{ts}"
    inst_c_id = f"INST_CD_NVDA_{ts}"
    port_id = f"PORT_CD_{ts}"

    async with AsyncSessionLocal() as session:
        # 1. Seed 3 Instruments
        ia = Instrument(
            instrument_id=inst_a_id,
            canonical_name="Apple Inc Common Stock",
            short_name="AAPL",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            issue_currency="USD",
        )
        ib = Instrument(
            instrument_id=inst_b_id,
            canonical_name="Microsoft Corp Common Stock",
            short_name="MSFT",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            issue_currency="USD",
        )
        ic = Instrument(
            instrument_id=inst_c_id,
            canonical_name="Nvidia Corp Common Stock",
            short_name="NVDA",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            issue_currency="USD",
        )
        session.add_all([ia, ib, ic])
        await session.flush()

        # 2. Seed 45 daily observations for A, B, C
        base_date = date(2026, 1, 1)
        for i in range(45):
            d = base_date + timedelta(days=i)
            # A and B highly correlated, C uncorrelated
            px_a = Decimal(str(150 + i * 1.0))
            px_b = Decimal(str(250 + i * 1.5))
            px_c = Decimal(str(100 + (i % 5) * 4.0 - (i % 3) * 2.0))

            session.add(PriceReferenceObservation(
                price_reference_id=f"PR_A_{ts}_{i}",
                instrument_id=ia.instrument_id,
                exchange_code="NASDAQ",
                trading_date=d,
                reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                price_value=px_a,
                currency="USD",
            ))
            session.add(PriceReferenceObservation(
                price_reference_id=f"PR_B_{ts}_{i}",
                instrument_id=ib.instrument_id,
                exchange_code="NASDAQ",
                trading_date=d,
                reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                price_value=px_b,
                currency="USD",
            ))
            session.add(PriceReferenceObservation(
                price_reference_id=f"PR_C_{ts}_{i}",
                instrument_id=ic.instrument_id,
                exchange_code="NASDAQ",
                trading_date=d,
                reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                price_value=px_c,
                currency="USD",
            ))

        # 3. Seed Portfolio & Positions
        port = Portfolio(
            portfolio_id=port_id,
            portfolio_code=f"CODE_CD_{ts}",
            portfolio_name="Correlation Dashboard Quantitative Fund",
            short_name="CD_FUND",
            portfolio_type=PortfolioTypeEnum.PROPRIETARY,
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            base_currency="USD",
            created_by="QUANT_TEST",
        )
        session.add(port)
        await session.flush()

        session.add(PositionBook(
            position_id=f"POS_CD_1_{ts}",
            portfolio_id=port.portfolio_id,
            account_id="ACC_01",
            instrument_id=ia.instrument_id,
            position_side=PositionSide.LONG,
            position_status=PositionStatus.OPEN,
        ))
        session.add(PositionBook(
            position_id=f"POS_CD_2_{ts}",
            portfolio_id=port.portfolio_id,
            account_id="ACC_01",
            instrument_id=ib.instrument_id,
            position_side=PositionSide.LONG,
            position_status=PositionStatus.OPEN,
        ))
        session.add(PositionBook(
            position_id=f"POS_CD_3_{ts}",
            portfolio_id=port.portfolio_id,
            account_id="ACC_01",
            instrument_id=ic.instrument_id,
            position_side=PositionSide.LONG,
            position_status=PositionStatus.OPEN,
        ))
        await session.commit()

        # 4. Test Universe Resolution
        u_res = await CorrelationDashboardService.resolve_universe(
            session=session,
            req=UniverseResolveRequest(
                portfolio_id=port_id,
                universe_type=UniverseType.PORTFOLIO_HOLDINGS,
            ),
        )
        assert u_res.total_eligible == 3
        symbols = [inst.symbol for inst in u_res.instruments]
        assert "AAPL" in symbols and "MSFT" in symbols and "NVDA" in symbols

        # 5. Test Correlation Matrix Calculation & View
        mat_res = await CorrelationDashboardService.get_matrix_view(
            session=session,
            req=CorrelationMatrixViewRequest(
                portfolio_id=port_id,
                lookback_days=30,
                as_of=base_date + timedelta(days=40),
                estimator=CorrelationEstimatorType.PEARSON,
                sort_order=MatrixSortOrder.ALPHABETICAL,
            ),
        )
        assert mat_res.dimension == 3
        assert mat_res.asset_symbols == ["AAPL", "MSFT", "NVDA"] # Alphabetical
        assert pytest.approx(float(mat_res.matrix[0][0]), 1e-4) == 1.0 # Diagonal unit
        assert len(mat_res.pair_metadata) == 9

        # 6. Test Period Matrix Comparison
        comp_res = await CorrelationDashboardService.compare_matrices(
            session=session,
            req=MatrixComparisonRequest(
                portfolio_id=port_id,
                current_lookback_days=30,
                comparison_lookback_days=15,
                current_as_of=base_date + timedelta(days=40),
                comparison_as_of=base_date + timedelta(days=25),
                estimator=CorrelationEstimatorType.PEARSON,
            ),
        )
        assert comp_res.dimension == 3
        assert len(comp_res.difference_matrix) == 3
        assert comp_res.difference_matrix[0][0] == Decimal("0") # Diagonal diff is 0

        # 7. Test Hierarchical Clustering
        cluster_res = await CorrelationDashboardService.compute_clusters(
            session=session,
            req=CorrelationClusteringRequest(
                portfolio_id=port_id,
                lookback_days=30,
                as_of=base_date + timedelta(days=40),
                estimator=CorrelationEstimatorType.PEARSON,
                clustering_method=ClusteringMethod.HIERARCHICAL,
                linkage=HierarchicalLinkage.AVERAGE,
                target_clusters=2,
            ),
        )
        assert cluster_res.total_instruments == 3
        assert cluster_res.number_of_clusters == 2
        assert len(cluster_res.clusters) == 2
        assert len(cluster_res.dendrogram_leaves) == 3
        assert cluster_res.dendrogram_nodes is not None

        # 8. Test Outlier Detection
        outlier_res = await CorrelationDashboardService.detect_outliers(
            session=session,
            req=CorrelationOutliersRequest(
                portfolio_id=port_id,
                lookback_days=30,
                as_of=base_date + timedelta(days=40),
                estimator=CorrelationEstimatorType.PEARSON,
                high_positive_threshold=Decimal("0.70"),
                comparison_lookback_days=15,
            ),
        )
        assert outlier_res.total_outliers_flagged >= 1
        pos_symbols = [(p.instrument_a_symbol, p.instrument_b_symbol) for p in outlier_res.high_positive_pairs]
        # AAPL and MSFT should be highly positively correlated
        assert any(("AAPL" in pair and "MSFT" in pair) for pair in pos_symbols)

        # 9. Test Pair Detail & Scatter Points
        pair_detail = await CorrelationDashboardService.get_pair_detail(
            session=session,
            instrument_a_id=inst_a_id,
            instrument_b_id=inst_b_id,
            portfolio_id=port_id,
            lookback_days=30,
            as_of=base_date + timedelta(days=40),
        )
        assert pair_detail.sample_size >= 10
        assert pair_detail.correlation > Decimal("0.80")
        assert len(pair_detail.scatter_points) >= 10
        assert pair_detail.least_squares_slope is not None


@pytest.mark.asyncio
async def test_correlation_dashboard_persistence_and_api():
    await init_db()
    ts = int(datetime.now().timestamp())
    inst_a_id = f"INST_API_A_{ts}"
    inst_b_id = f"INST_API_B_{ts}"
    port_id = f"PORT_API_{ts}"

    async with AsyncSessionLocal() as session:
        ia = Instrument(
            instrument_id=inst_a_id,
            canonical_name="API Alpha Stock",
            short_name="ALPH",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            issue_currency="USD",
        )
        ib = Instrument(
            instrument_id=inst_b_id,
            canonical_name="API Beta Stock",
            short_name="BETA",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            issue_currency="USD",
        )
        session.add_all([ia, ib])
        await session.flush()

        base_date = date(2026, 1, 1)
        for i in range(35):
            d = base_date + timedelta(days=i)
            session.add(PriceReferenceObservation(
                price_reference_id=f"PR_API_A_{ts}_{i}",
                instrument_id=ia.instrument_id,
                exchange_code="NASDAQ",
                trading_date=d,
                reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                price_value=Decimal(str(100 + i * 0.5)),
                currency="USD",
            ))
            session.add(PriceReferenceObservation(
                price_reference_id=f"PR_API_B_{ts}_{i}",
                instrument_id=ib.instrument_id,
                exchange_code="NASDAQ",
                trading_date=d,
                reference_type=PriceReferenceType.OFFICIAL_CLOSE,
                price_value=Decimal(str(200 + i * 1.0)),
                currency="USD",
            ))

        port = Portfolio(
            portfolio_id=port_id,
            portfolio_code=f"CODE_API_{ts}",
            portfolio_name="Correlation API Test Portfolio",
            short_name="CORR_API",
            portfolio_type=PortfolioTypeEnum.PROPRIETARY,
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            base_currency="USD",
            created_by="API_TESTER",
        )
        session.add(port)
        await session.flush()

        session.add(PositionBook(
            position_id=f"POS_API_1_{ts}",
            portfolio_id=port.portfolio_id,
            account_id="ACC_01",
            instrument_id=ia.instrument_id,
            position_side=PositionSide.LONG,
            position_status=PositionStatus.OPEN,
        ))
        session.add(PositionBook(
            position_id=f"POS_API_2_{ts}",
            portfolio_id=port.portfolio_id,
            account_id="ACC_01",
            instrument_id=ib.instrument_id,
            position_side=PositionSide.LONG,
            position_status=PositionStatus.OPEN,
        ))
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. POST /api/v1/dashboard/correlation/universe/resolve
        u_res = await client.post(
            "/api/v1/dashboard/correlation/universe/resolve",
            json={"portfolio_id": port_id, "universe_type": "PORTFOLIO_HOLDINGS"},
        )
        assert u_res.status_code == 200, u_res.text
        assert u_res.json()["total_eligible"] == 2

        # 2. POST /api/v1/dashboard/correlation/matrix
        m_res = await client.post(
            "/api/v1/dashboard/correlation/matrix",
            json={
                "portfolio_id": port_id,
                "lookback_days": 25,
                "as_of": "2026-02-04",
                "estimator": "PEARSON",
                "sort_order": "ALPHABETICAL",
            },
        )
        assert m_res.status_code == 200, m_res.text
        m_data = m_res.json()
        assert m_data["dimension"] == 2
        assert len(m_data["matrix"]) == 2

        # 3. POST /api/v1/dashboard/correlation/compare
        c_res = await client.post(
            "/api/v1/dashboard/correlation/compare",
            json={
                "portfolio_id": port_id,
                "current_lookback_days": 25,
                "comparison_lookback_days": 15,
                "current_as_of": "2026-02-04",
                "estimator": "PEARSON",
            },
        )
        assert c_res.status_code == 200, c_res.text
        assert len(c_res.json()["difference_matrix"]) == 2

        # 4. POST /api/v1/dashboard/correlation/clusters
        cl_res = await client.post(
            "/api/v1/dashboard/correlation/clusters",
            json={
                "portfolio_id": port_id,
                "lookback_days": 25,
                "as_of": "2026-02-04",
                "estimator": "PEARSON",
                "clustering_method": "HIERARCHICAL",
                "target_clusters": 2,
            },
        )
        assert cl_res.status_code == 200, cl_res.text
        assert cl_res.json()["number_of_clusters"] == 2

        # 5. POST /api/v1/dashboard/correlation/outliers
        out_res = await client.post(
            "/api/v1/dashboard/correlation/outliers",
            json={
                "portfolio_id": port_id,
                "lookback_days": 25,
                "as_of": "2026-02-04",
                "high_positive_threshold": "0.70",
            },
        )
        assert out_res.status_code == 200, out_res.text

        # 6. GET /api/v1/dashboard/correlation/pair/{a}/{b}
        pair_res = await client.get(
            f"/api/v1/dashboard/correlation/pair/{inst_a_id}/{inst_b_id}?lookback_days=25&as_of=2026-02-04"
        )
        assert pair_res.status_code == 200, pair_res.text
        assert pair_res.json()["sample_size"] >= 10

        # 7. Preferences GET and PUT
        user_rand_id = f"analyst_{uuid.uuid4().hex[:6]}"
        p_get = await client.get("/api/v1/dashboard/correlation/preferences", headers={"X-User-ID": user_rand_id})
        assert p_get.status_code == 200
        assert p_get.json()["default_lookback_days"] == 60

        p_put = await client.put(
            "/api/v1/dashboard/correlation/preferences",
            headers={"X-User-ID": user_rand_id},
            json={
                "dashboard_name": "Quant Desk Preferred",
                "default_lookback_days": 90,
                "sampling_frequency": "DAILY",
                "correlation_method": "PEARSON",
                "return_definition": "LOGARITHMIC",
                "min_observations": 25,
            },
        )
        assert p_put.status_code == 200
        assert p_put.json()["default_lookback_days"] == 90

        # 8. Saved Universes POST, GET, DELETE
        u_create = await client.post(
            "/api/v1/dashboard/correlation/universes",
            headers={"X-User-ID": user_rand_id},
            json={
                "universe_name": f"Mega Cap Tech Watchlist {user_rand_id}",
                "description": "Tech watchlist for correlation monitoring",
                "universe_type": "CUSTOM_SECURITIES",
                "instrument_ids": [inst_a_id, inst_b_id],
            },
        )
        assert u_create.status_code == 200
        u_id = u_create.json()["id"]

        u_list = await client.get("/api/v1/dashboard/correlation/universes", headers={"X-User-ID": user_rand_id})
        assert u_list.status_code == 200
        assert len(u_list.json()) >= 1

        u_del = await client.delete(f"/api/v1/dashboard/correlation/universes/{u_id}", headers={"X-User-ID": user_rand_id})
        assert u_del.status_code == 200

        # 9. Investigation Log POST
        inv_res = await client.post(
            "/api/v1/dashboard/correlation/investigations",
            headers={"X-User-ID": user_rand_id},
            json={
                "portfolio_id": port_id,
                "instrument_a_id": inst_a_id,
                "instrument_b_id": inst_b_id,
                "correlation_value": "0.9250",
                "lookback_days": 25,
                "sampling_frequency": "DAILY",
                "observation_count": 25,
                "detection_reason": "HIGH_POSITIVE_CORRELATION",
                "user_notes": "Identified high co-movement post semiconductor earnings release.",
            },
        )
        assert inv_res.status_code == 200
        assert inv_res.json()["status"] == "OPEN"
