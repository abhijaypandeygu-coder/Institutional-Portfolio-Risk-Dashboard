"""Comprehensive test suite for M05.01 - Portfolio Creation."""
import uuid
from datetime import date
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.modules.portfolio_management.portfolio_creation.models import (
    PortfolioLifecycleStatus,
    PortfolioTypeEnum,
    MarketScopeEnum,
    HierarchyTypeEnum,
    BenchmarkTypeEnum,
    OwnershipTypeEnum,
    ValuationFrequencyEnum,
    AccountingBasisEnum,
    CostBasisMethodEnum,
    DividendAccrualMethodEnum,
    LimitCategoryEnum,
    LimitScopeEnum,
    LimitThresholdTypeEnum,
)
from backend.app.modules.portfolio_management.portfolio_creation.state_machine.transitions import validate_lifecycle_transition


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_lifecycle_state_machine():
    """Verify lifecycle transitions."""
    assert validate_lifecycle_transition(PortfolioLifecycleStatus.DRAFT, PortfolioLifecycleStatus.PENDING_APPROVAL) is True
    assert validate_lifecycle_transition(PortfolioLifecycleStatus.PENDING_APPROVAL, PortfolioLifecycleStatus.APPROVED) is True
    assert validate_lifecycle_transition(PortfolioLifecycleStatus.APPROVED, PortfolioLifecycleStatus.ACTIVE) is True
    assert validate_lifecycle_transition(PortfolioLifecycleStatus.ACTIVE, PortfolioLifecycleStatus.SUSPENDED) is True
    assert validate_lifecycle_transition(PortfolioLifecycleStatus.SUSPENDED, PortfolioLifecycleStatus.ACTIVE) is True
    assert validate_lifecycle_transition(PortfolioLifecycleStatus.ACTIVE, PortfolioLifecycleStatus.CLOSING) is True
    assert validate_lifecycle_transition(PortfolioLifecycleStatus.CLOSING, PortfolioLifecycleStatus.CLOSED) is True
    assert validate_lifecycle_transition(PortfolioLifecycleStatus.CLOSED, PortfolioLifecycleStatus.ARCHIVED) is True

    # Invalid transitions
    assert validate_lifecycle_transition(PortfolioLifecycleStatus.DRAFT, PortfolioLifecycleStatus.ACTIVE) is False
    assert validate_lifecycle_transition(PortfolioLifecycleStatus.CLOSED, PortfolioLifecycleStatus.ACTIVE) is False
    assert validate_lifecycle_transition(PortfolioLifecycleStatus.ARCHIVED, PortfolioLifecycleStatus.DRAFT) is False


@pytest.mark.asyncio
async def test_portfolio_registration_and_duplicate_prevention():
    """Verify registration, uniqueness, and retrieval."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rand_id = uuid.uuid4().hex[:6].upper()
        code = f"PF_CODE_{rand_id}"

        payload = {
            "portfolio_code": code,
            "portfolio_name": f"Alpha Quant Portfolio {rand_id}",
            "short_name": f"AQ_{rand_id}",
            "description": "Multi-market quantitative long-short equity",
            "portfolio_type": "PROPRIETARY",
            "creation_source": "MANUAL_ADMINISTRATION",
            "base_currency": "USD",
            "market_scope": "INDIA_AND_US",
            "asset_class_scope": "EQUITIES",
        }

        # 1. Register portfolio
        res = await client.post("/api/v1/portfolios/", json=payload)
        assert res.status_code == 201
        data = res.json()
        portfolio_id = data["portfolio_id"]
        assert data["portfolio_code"] == code
        assert data["lifecycle_status"] == "DRAFT"
        assert data["base_currency"] == "USD"
        assert data["current_configuration_version"] == 1

        # 2. Duplicate registration attempt with same code
        res_dup = await client.post("/api/v1/portfolios/", json=payload)
        assert res_dup.status_code == 400
        assert "already exists" in res_dup.json()["detail"]

        # 3. Retrieve portfolio
        res_get = await client.get(f"/api/v1/portfolios/{portfolio_id}")
        assert res_get.status_code == 200
        assert res_get.json()["portfolio_id"] == portfolio_id


@pytest.mark.asyncio
async def test_base_currency_change_workflow():
    """Verify controlled base currency changes and version increment."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rand_id = uuid.uuid4().hex[:6].upper()
        code = f"PF_FX_{rand_id}"

        # 1. Create portfolio with USD
        res = await client.post("/api/v1/portfolios/", json={
            "portfolio_code": code,
            "portfolio_name": f"FX Test Portfolio {rand_id}",
            "short_name": f"FX_{rand_id}",
            "base_currency": "USD",
        })
        assert res.status_code == 201
        portfolio_id = res.json()["portfolio_id"]

        # 2. Change base currency to INR
        res_change = await client.post(
            f"/api/v1/portfolios/{portfolio_id}/change-base-currency",
            json={
                "new_base_currency": "INR",
                "effective_date": "2026-04-01",
                "change_reason": "Fund restructuring to INR onshore reporting",
                "fx_policy_reference": "RBI_REFERENCE_RATE",
            }
        )
        assert res_change.status_code == 200
        updated = res_change.json()
        assert updated["base_currency"] == "INR"
        assert updated["current_configuration_version"] == 2


@pytest.mark.asyncio
async def test_strategy_and_mandate_configuration():
    """Verify strategy creation, assignment, and mandate governance."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rand_id = uuid.uuid4().hex[:6].upper()
        code = f"PF_STRAT_{rand_id}"

        res_pf = await client.post("/api/v1/portfolios/", json={
            "portfolio_code": code,
            "portfolio_name": f"Strat Portfolio {rand_id}",
            "short_name": f"ST_{rand_id}",
            "base_currency": "INR",
        })
        portfolio_id = res_pf.json()["portfolio_id"]

        # 1. Create Strategy catalog entry
        strat_code = f"STAT_ARB_{rand_id}"
        res_strat = await client.post("/api/v1/portfolios/strategies", json={
            "strategy_code": strat_code,
            "strategy_name": "Statistical Arbitrage Equity",
            "strategy_family": "QUANTITATIVE",
            "supported_asset_classes": "EQUITIES",
            "supported_markets": "INDIA_AND_US",
        })
        assert res_strat.status_code == 201

        # 2. Assign Strategy
        res_assign = await client.post(f"/api/v1/portfolios/{portfolio_id}/strategies", json={
            "strategy_code": strat_code,
            "is_primary": True,
            "assignment_reason": "Core multi-market mean reversion sleeve",
        })
        assert res_assign.status_code == 201

        # 3. Create Mandate
        mandate_code = f"MANDATE_{rand_id}"
        res_mand = await client.post("/api/v1/portfolios/mandates", json={
            "mandate_code": mandate_code,
            "mandate_name": "Liquid US & India Equities Mandate",
            "mandate_type": "MARKET_NEUTRAL_EQUITY",
            "investment_objective": "Generate market-neutral returns with strict sector caps",
            "short_selling_permitted": True,
            "leverage_permitted": True,
        })
        assert res_mand.status_code == 201

        # 4. Assign Mandate
        res_mand_assign = await client.post(f"/api/v1/portfolios/{portfolio_id}/mandates", json={
            "mandate_code": mandate_code,
        })
        assert res_mand_assign.status_code == 201


@pytest.mark.asyncio
async def test_benchmarks_and_ownership():
    """Verify benchmark associations and ownership tracking."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rand_id = uuid.uuid4().hex[:6].upper()
        code = f"PF_BM_{rand_id}"

        res_pf = await client.post("/api/v1/portfolios/", json={
            "portfolio_code": code,
            "portfolio_name": f"Benchmark Test Portfolio {rand_id}",
            "short_name": f"BM_{rand_id}",
            "base_currency": "USD",
        })
        portfolio_id = res_pf.json()["portfolio_id"]

        # 1. Assign Primary Benchmark (S&P 500)
        res_bm1 = await client.post(f"/api/v1/portfolios/{portfolio_id}/benchmarks", json={
            "benchmark_reference_id": "SP500",
            "benchmark_name": "S&P 500 Index",
            "benchmark_type": "PRIMARY_BENCHMARK",
            "benchmark_currency": "USD",
            "is_primary": True,
            "benchmark_weight": 0.70,
        })
        assert res_bm1.status_code == 201

        # 2. Assign Secondary Benchmark (NIFTY 50)
        res_bm2 = await client.post(f"/api/v1/portfolios/{portfolio_id}/benchmarks", json={
            "benchmark_reference_id": "NIFTY50",
            "benchmark_name": "NIFTY 50 Index",
            "benchmark_type": "SECONDARY_BENCHMARK",
            "benchmark_currency": "INR",
            "is_primary": False,
            "benchmark_weight": 0.30,
        })
        assert res_bm2.status_code == 201

        # 3. Assign Ownership (Portfolio Manager & Desk)
        res_own = await client.post(f"/api/v1/portfolios/{portfolio_id}/ownership", json={
            "ownership_type": "INDIVIDUAL",
            "owner_entity_id": "USER_JOHN_DOE",
            "owner_name": "John Doe",
            "ownership_role": "HEAD_PORTFOLIO_MANAGER",
            "is_primary_owner": True,
        })
        assert res_own.status_code == 201


@pytest.mark.asyncio
async def test_hierarchy_and_cycle_rejection():
    """Verify parent-child sleeves and circular reference prevention."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rand_id = uuid.uuid4().hex[:6].upper()

        # Create Parent
        res_p = await client.post("/api/v1/portfolios/", json={
            "portfolio_code": f"PARENT_{rand_id}",
            "portfolio_name": f"Master Umbrella Fund {rand_id}",
            "short_name": f"P_{rand_id}",
            "base_currency": "USD",
        })
        parent_id = res_p.json()["portfolio_id"]

        # Create Child 1
        res_c1 = await client.post("/api/v1/portfolios/", json={
            "portfolio_code": f"SLEEVE_US_{rand_id}",
            "portfolio_name": f"US Equity Sleeve {rand_id}",
            "short_name": f"US_{rand_id}",
            "base_currency": "USD",
        })
        child1_id = res_c1.json()["portfolio_id"]

        # Create Child 2
        res_c2 = await client.post("/api/v1/portfolios/", json={
            "portfolio_code": f"SLEEVE_IN_{rand_id}",
            "portfolio_name": f"India Equity Sleeve {rand_id}",
            "short_name": f"IN_{rand_id}",
            "base_currency": "INR",
        })
        child2_id = res_c2.json()["portfolio_id"]

        # 1. Link sleeves to parent
        res_h1 = await client.post(f"/api/v1/portfolios/{parent_id}/hierarchy", json={
            "child_portfolio_id": child1_id,
            "relationship_type": "SLEEVE",
            "allocation_weight": 0.60,
        })
        assert res_h1.status_code == 201

        res_h2 = await client.post(f"/api/v1/portfolios/{parent_id}/hierarchy", json={
            "child_portfolio_id": child2_id,
            "relationship_type": "SLEEVE",
            "allocation_weight": 0.40,
        })
        assert res_h2.status_code == 201

        # 2. Self-parenting attempt should be rejected
        res_self = await client.post(f"/api/v1/portfolios/{parent_id}/hierarchy", json={
            "child_portfolio_id": parent_id,
            "relationship_type": "SLEEVE",
        })
        assert res_self.status_code == 400
        assert "cannot be its own parent" in res_self.json()["detail"]

        # 3. Cycle attempt (making Parent a child of Child 1) should be rejected
        res_cycle = await client.post(f"/api/v1/portfolios/{child1_id}/hierarchy", json={
            "child_portfolio_id": parent_id,
            "relationship_type": "PARENT_PORTFOLIO",
        })
        assert res_cycle.status_code == 400
        assert "Circular hierarchy detected" in res_cycle.json()["detail"]


@pytest.mark.asyncio
async def test_valuation_accounting_and_limits():
    """Verify valuation settings, accounting conventions, and limit definitions."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rand_id = uuid.uuid4().hex[:6].upper()

        res_pf = await client.post("/api/v1/portfolios/", json={
            "portfolio_code": f"PF_SETT_{rand_id}",
            "portfolio_name": f"Settings Portfolio {rand_id}",
            "short_name": f"SETT_{rand_id}",
            "base_currency": "USD",
        })
        portfolio_id = res_pf.json()["portfolio_id"]

        # 1. Update Valuation Settings
        res_val = await client.post(f"/api/v1/portfolios/{portfolio_id}/valuation-settings", json={
            "valuation_calendar_id": "CAL_NYSE_XNAS",
            "valuation_frequency": "DAILY",
            "cutoff_time": "16:00:00",
            "cutoff_timezone": "America/New_York",
            "price_selection_policy_id": "OFFICIAL_CLOSE_PRIMARY",
            "currency_conversion_policy_id": "DAILY_OFFICIAL_FX",
        })
        assert res_val.status_code == 200
        assert res_val.json()["cutoff_timezone"] == "America/New_York"

        # 2. Update Accounting Settings
        res_acc = await client.post(f"/api/v1/portfolios/{portfolio_id}/accounting-settings", json={
            "trade_accounting_basis": "TRADE_DATE",
            "cost_basis_method": "WEIGHTED_AVERAGE",
            "dividend_accrual_method": "ACCRUAL_ON_ENTITLEMENT",
            "corporate_action_policy_id": "STANDARD_ADJUSTMENT_FACTOR",
            "rounding_precision_places": 4,
        })
        assert res_acc.status_code == 200
        assert res_acc.json()["cost_basis_method"] == "WEIGHTED_AVERAGE"

        # 3. Create Limits
        res_lim1 = await client.post(f"/api/v1/portfolios/{portfolio_id}/limits", json={
            "limit_code": "MAX_SECTOR_FIN",
            "limit_name": "Maximum Financials Sector Exposure",
            "limit_category": "MAX_SECTOR_EXPOSURE",
            "limit_scope": "SECTOR_LEVEL",
            "scope_reference": "FINANCIALS",
            "comparison_operator": "<=",
            "threshold_value": 0.25,
            "threshold_unit": "PERCENTAGE",
            "warning_threshold": 0.20,
            "hard_threshold": 0.25,
        })
        assert res_lim1.status_code == 201

        res_lim2 = await client.post(f"/api/v1/portfolios/{portfolio_id}/limits", json={
            "limit_code": "MAX_LEVERAGE_RATIO",
            "limit_name": "Gross Portfolio Leverage Limit",
            "limit_category": "MAX_LEVERAGE",
            "limit_scope": "PORTFOLIO_LEVEL",
            "comparison_operator": "<=",
            "threshold_value": 2.00,
            "threshold_unit": "RATIO",
            "hard_threshold": 2.00,
        })
        assert res_lim2.status_code == 201


@pytest.mark.asyncio
async def test_full_lifecycle_and_point_in_time_snapshot():
    """Verify submit -> approve -> activate -> suspend -> resume -> close, and point-in-time configuration."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rand_id = uuid.uuid4().hex[:6].upper()

        res_pf = await client.post("/api/v1/portfolios/", json={
            "portfolio_code": f"PF_LC_{rand_id}",
            "portfolio_name": f"Lifecycle Portfolio {rand_id}",
            "short_name": f"LC_{rand_id}",
            "base_currency": "USD",
        })
        portfolio_id = res_pf.json()["portfolio_id"]

        # Submit for approval
        res_sub = await client.post(f"/api/v1/portfolios/{portfolio_id}/submit", json={"reason": "Ready for investment committee"})
        assert res_sub.status_code == 200
        assert res_sub.json()["lifecycle_status"] == "PENDING_APPROVAL"

        # Approve
        res_app = await client.post(f"/api/v1/portfolios/{portfolio_id}/approve", json={"reason": "Approved by Risk Officer"})
        assert res_app.status_code == 200
        assert res_app.json()["lifecycle_status"] == "APPROVED"

        # Activate
        res_act = await client.post(f"/api/v1/portfolios/{portfolio_id}/activate", json={"reason": "Fund launch"})
        assert res_act.status_code == 200
        assert res_act.json()["lifecycle_status"] == "ACTIVE"

        # Suspend
        res_susp = await client.post(f"/api/v1/portfolios/{portfolio_id}/suspend", json={"reason": "Audit review"})
        assert res_susp.status_code == 200
        assert res_susp.json()["lifecycle_status"] == "SUSPENDED"

        # Resume
        res_res = await client.post(f"/api/v1/portfolios/{portfolio_id}/resume", json={"reason": "Audit review cleared"})
        assert res_res.status_code == 200
        assert res_res.json()["lifecycle_status"] == "ACTIVE"

        # Close
        res_close = await client.post(f"/api/v1/portfolios/{portfolio_id}/close", json={"reason": "Portfolio wound down"})
        assert res_close.status_code == 200
        assert res_close.json()["lifecycle_status"] == "CLOSED"

        # Verify lifecycle history
        res_hist = await client.get(f"/api/v1/portfolios/{portfolio_id}/lifecycle-history")
        assert res_hist.status_code == 200
        events = res_hist.json()
        assert len(events) >= 6

        # Point-in-time configuration snapshot retrieval
        today_str = date.today().isoformat()
        res_snap = await client.get(f"/api/v1/portfolios/{portfolio_id}/configuration/as-of?as_of_date={today_str}")
        assert res_snap.status_code == 200
        snap_data = res_snap.json()
        assert snap_data["portfolio_id"] == portfolio_id
        assert "snapshot" in snap_data
        assert snap_data["snapshot"]["base_currency"] == "USD"

        # Operational metrics endpoint
        res_metrics = await client.get("/api/v1/portfolios/metrics/operational")
        assert res_metrics.status_code == 200
        metrics = res_metrics.json()
        assert metrics["total_portfolios"] >= 1

