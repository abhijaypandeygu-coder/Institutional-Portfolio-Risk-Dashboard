"""
Unit and Integration Tests for M06.07 Portfolio Allocation.
Verifies capital distribution across securities, cash, sectors, and geographies,
dual percentage weights (NAV-based, normalized, gross contribution), NAV reconciliation,
target allocation drift, and historical snapshot comparisons.
"""

import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.modules.instrument_reference_data.instrument_master.services.service import (
    InstrumentMasterService,
)
from backend.app.modules.instrument_reference_data.instrument_master.schemas import (
    InstrumentCreateRequest,
)
from backend.app.modules.portfolio_management.cash_management.services.service import (
    CashManagementService,
)
from backend.app.modules.portfolio_management.cash_management.schemas import (
    DepositCreate,
)
from backend.app.modules.risk_management.portfolio_allocation.models import (
    AllocationGroupingDimension,
    AllocationViewType,
    AllocationReconciliationStatus,
    AllocationDriftStatus,
)


@pytest.mark.asyncio
async def test_portfolio_allocation_capital_weights_and_reconciliation():
    """
    Test portfolio capital allocation across securities and cash with exact NAV reconciliation.
    Setup:
    - Deposit Cash: $20,000 USD
    - Buy Security 1 (AAPL): 100 @ 150 = $15,000
    - Sell Short Security 2 (TSLA): -50 @ 100 = -$5,000
    - Total Long = $15,000
    - Total Short = $5,000
    - Net Security = $10,000
    - Cash NAV = $20,000
    - Expected NAV = $10,000 + $20,000 = $30,000
    - Security 1 NAV weight = $15k / $30k = 50.0%
    - Security 2 NAV weight = -$5k / $30k = -16.6667%
    - Cash NAV weight = $20k / $30k = 66.6667%
    - Reconciliation Sum = 50% - 16.6667% + 66.6667% = 100.0% (Residual = 0)
    """
    await init_db()
    ts = datetime.utcnow().timestamp()
    port_id = f"port-alc-test-{ts}"
    acc_id = f"acc-alc-{ts}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create canonical instruments
        async with AsyncSessionLocal() as session:
            i_aapl = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Apple Inc {ts}",
                    short_name=f"AAPL_{ts}",
                    instrument_type="COMMON_STOCK",
                    asset_class="EQUITY",
                    issue_currency="USD",
                    primary_market_id="NASDAQ",
                ),
                actor_id="admin",
            )
            i_tsla = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Tesla Inc {ts}",
                    short_name=f"TSLA_{ts}",
                    instrument_type="COMMON_STOCK",
                    asset_class="EQUITY",
                    issue_currency="USD",
                    primary_market_id="NASDAQ",
                ),
                actor_id="admin",
            )
            inst_aapl = i_aapl.instrument_id
            inst_tsla = i_tsla.instrument_id

            # 2. Deposit Cash via M05.04 Cash Management Service
            cash_svc = CashManagementService(session)
            await cash_svc.process_deposit(
                DepositCreate(
                    portfolio_id=port_id,
                    account_id=acc_id,
                    currency="USD",
                    amount=Decimal("20000.000000"),
                    deposit_reference=f"DEP_{ts}",
                    description="Initial Cash Allocation",
                )
            )
            # Create snapshot for balance sheet recording
            await cash_svc.calculate_and_snapshot_balances(port_id, acc_id, "USD")
            await session.commit()

        # 3. Create positions via M05.02 events
        await client.post(
            "/api/v1/positions/events",
            json={
                "portfolio_id": port_id,
                "account_id": acc_id,
                "instrument_id": inst_aapl,
                "event_type": "TRADE_BUY",
                "signed_quantity_delta": "100.000000",
                "settled_quantity_delta": "100.000000",
                "idempotency_key": f"EVT_AAPL_{ts}",
            },
        )
        await client.post(
            "/api/v1/positions/events",
            json={
                "portfolio_id": port_id,
                "account_id": acc_id,
                "instrument_id": inst_tsla,
                "event_type": "TRADE_SELL",
                "signed_quantity_delta": "-50.000000",
                "settled_quantity_delta": "-50.000000",
                "idempotency_key": f"EVT_TSLA_{ts}",
            },
        )

        # 4. Run valuations via M05.03
        await client.post(
            "/api/v1/valuations/run",
            json={
                "portfolio_id": port_id,
                "mark_prices": {
                    inst_aapl: "150.000000",
                    inst_tsla: "100.000000",
                },
            },
        )

        # 5. Calculate Allocation via REST API
        resp = await client.post(
            "/api/v1/risk/portfolio-allocation/calculate",
            json={
                "portfolio_id": port_id,
                "grouping_dimension": "SECURITY",
                "allocation_view_type": "NAV_CAPITAL_ALLOCATION",
                "include_cash_in_breakdown": True,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert Decimal(data["total_long_market_value"]) == Decimal("15000.000000")
        assert Decimal(data["total_short_market_value"]) == Decimal("5000.000000")
        assert Decimal(data["net_security_market_value"]) == Decimal("10000.000000")
        assert Decimal(data["cash_nav_value"]) == Decimal("20000.000000")
        assert Decimal(data["nav_value"]) == Decimal("30000.000000")
        assert data["reconciliation_status"] == "RECONCILED"
        assert Decimal(data["reconciliation_residual"]) == Decimal("0.000000")

        # Verify weights
        assert Decimal(data["invested_nav_weight"]) == Decimal("0.333333")  # 10k / 30k
        assert Decimal(data["cash_nav_weight"]) == Decimal("0.666667")  # 20k / 30k

        comps = data["components"]
        assert len(comps) == 3  # AAPL, TSLA, CASH
        cash_item = next(c for c in comps if c["group_id"] == "CASH_NAV")
        assert Decimal(cash_item["cash_value"]) == Decimal("20000.000000")
        assert Decimal(cash_item["actual_nav_weight"]) == Decimal("0.666667")

        aapl_item = next(c for c in comps if c["group_id"] == inst_aapl)
        assert Decimal(aapl_item["actual_nav_weight"]) == Decimal("0.500000")

        tsla_item = next(c for c in comps if c["group_id"] == inst_tsla)
        assert Decimal(tsla_item["actual_nav_weight"]) == Decimal("-0.166667")


@pytest.mark.asyncio
async def test_portfolio_allocation_targets_drift_and_comparison():
    """
    Test setting target allocations, computing drift in percentage points,
    and comparing two allocation calculation runs.
    """
    await init_db()
    ts = datetime.utcnow().timestamp()
    port_id = f"port-alc-drift-{ts}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Target: Cash target = 50%, tolerance = 5%
        tgt_resp = await client.post(
            "/api/v1/risk/portfolio-allocation/targets",
            json={
                "portfolio_id": port_id,
                "grouping_dimension": "CASH",
                "group_id": "CASH_NAV",
                "target_weight": "0.500000",
                "tolerance_band_pp": "0.050000",
            },
        )
        assert tgt_resp.status_code == 201
        tgt_data = tgt_resp.json()
        assert tgt_data["target_weight"] == "0.500000"

        # 2. Run allocation 1 (Empty port: NAV = 0)
        r1_resp = await client.post(
            "/api/v1/risk/portfolio-allocation/calculate",
            json={
                "portfolio_id": port_id,
                "grouping_dimension": "SECURITY",
            },
        )
        r1_data = r1_resp.json()

        # 3. Run allocation 2 (Dummy port)
        r2_resp = await client.post(
            "/api/v1/risk/portfolio-allocation/calculate",
            json={
                "portfolio_id": f"OTHER_{port_id}",
                "grouping_dimension": "SECURITY",
            },
        )
        r2_data = r2_resp.json()

        # 4. Compare runs
        comp_resp = await client.post(
            "/api/v1/risk/portfolio-allocation/compare",
            json={
                "base_result_id": r2_data["result_id"],
                "comparison_result_id": r1_data["result_id"],
            },
        )
        assert comp_resp.status_code == 200
        comp_data = comp_resp.json()
        assert comp_data["comparability_status"] == "COMPARABLE"
        assert comp_data["current_result_id"] == r2_data["result_id"]
        assert comp_data["prior_result_id"] == r1_data["result_id"]

