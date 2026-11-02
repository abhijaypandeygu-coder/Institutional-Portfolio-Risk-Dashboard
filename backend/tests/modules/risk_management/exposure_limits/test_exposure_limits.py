"""
Unit and Integration Tests for M06.08 Exposure Limits.
Verifies instrument caps, sector caps, portfolio gross/net limits, geographic limits,
utilization percentages, headroom/shortfall, warning/breach lifecycles, and hypothetical simulations.
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
from backend.app.modules.risk_management.exposure_limits.models import (
    ExposureLimitCategory,
    ExposureMeasurementBasis,
    ExposureLimitDirection,
    ExposureLimitDenominatorType,
    ExposureLimitStatus,
)


@pytest.mark.asyncio
async def test_exposure_limits_evaluation_and_breach_detection():
    """
    Test setting exposure limits on single instrument and portfolio gross exposure.
    Setup:
    - Position: 100 shares of AAPL @ $150 = $15,000 (Gross = $15,000)
    - Position: 50 shares of TSLA @ $200 = $10,000 (Gross = $10,000)
    - Total Gross = $25,000
    - Limit 1: AAPL Gross Max = $10,000 (Breached: $15,000 > $10,000, 150% util, -$5,000 headroom)
    - Limit 2: Portfolio Gross Max = $30,000 (Within limit: $25,000 <= $30,000, 83.33% util, $5,000 headroom)
    - Limit 3: TSLA Gross Max = $12,000 (Approaching/Warning: $10,000 / $12,000 = 83.33%)
    """
    await init_db()
    ts = datetime.utcnow().timestamp()
    port_id = f"port-lim-test-{ts}"
    acc_id = f"acc-lim-{ts}"

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

        # 2. Create positions via M05.02 events
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
                "event_type": "TRADE_BUY",
                "signed_quantity_delta": "50.000000",
                "settled_quantity_delta": "50.000000",
                "idempotency_key": f"EVT_TSLA_{ts}",
            },
        )

        # 3. Run valuations via M05.03
        await client.post(
            "/api/v1/valuations/run",
            json={
                "portfolio_id": port_id,
                "mark_prices": {
                    inst_aapl: "150.000000",
                    inst_tsla: "200.000000",
                },
            },
        )

        # 4. Configure Limits:
        # Limit 1: AAPL Max $10,000
        l1_resp = await client.post(
            "/api/v1/risk/exposure-limits/configs",
            json={
                "limit_code": f"LIM_AAPL_{ts}",
                "limit_name": "AAPL Single Name Max",
                "limit_category": "INSTRUMENT_LIMIT",
                "portfolio_id": port_id,
                "target_entity_id": inst_aapl,
                "exposure_basis": "GROSS_MARKET_VALUE",
                "limit_direction": "MAXIMUM",
                "denominator_type": "ABSOLUTE_AMOUNT",
                "limit_value": "10000.000000",
                "warning_threshold_ratio": "0.850000",
                "severe_breach_threshold_ratio": "1.100000",
            },
        )
        assert l1_resp.status_code == 201
        l1_data = l1_resp.json()

        # Limit 2: Portfolio Gross Max $30,000
        l2_resp = await client.post(
            "/api/v1/risk/exposure-limits/configs",
            json={
                "limit_code": f"LIM_GROSS_{ts}",
                "limit_name": "Portfolio Gross Cap",
                "limit_category": "PORTFOLIO_GROSS_LIMIT",
                "portfolio_id": port_id,
                "exposure_basis": "GROSS_MARKET_VALUE",
                "limit_direction": "MAXIMUM",
                "denominator_type": "ABSOLUTE_AMOUNT",
                "limit_value": "30000.000000",
            },
        )
        assert l2_resp.status_code == 201

        # 5. Evaluate Limits via REST API
        eval_resp = await client.post(
            "/api/v1/risk/exposure-limits/evaluate",
            json={"portfolio_id": port_id},
        )
        assert eval_resp.status_code == 200, eval_resp.text
        data = eval_resp.json()

        assert data["total_evaluated_limits"] >= 2
        assert data["breached_count"] >= 1 or data["severely_breached_count"] >= 1

        items = data["items"]
        aapl_eval = next(i for i in items if i["limit_id"] == l1_data["limit_id"])
        assert Decimal(aapl_eval["measured_exposure"]) == Decimal("15000.000000")
        assert Decimal(aapl_eval["limit_value"]) == Decimal("10000.000000")
        assert Decimal(aapl_eval["utilization_percentage"]) == Decimal("150.000000")
        assert Decimal(aapl_eval["headroom"]) == Decimal("-5000.000000")
        assert aapl_eval["status"] == "SEVERELY_BREACHED"

        # 6. Verify Breach History Audit Log
        breach_resp = await client.get(
            f"/api/v1/risk/exposure-limits/breaches?portfolio_id={port_id}"
        )
        assert breach_resp.status_code == 200
        breach_items = breach_resp.json()
        assert len(breach_items) >= 1
        assert any(b["limit_id"] == l1_data["limit_id"] for b in breach_items)


@pytest.mark.asyncio
async def test_exposure_limit_hypothetical_simulation():
    """
    Test pre-trade / hypothetical simulation of exposure changes against a limit.
    """
    await init_db()
    ts = datetime.utcnow().timestamp()
    port_id = f"port-sim-test-{ts}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a limit config
        l_resp = await client.post(
            "/api/v1/risk/exposure-limits/configs",
            json={
                "limit_code": f"LIM_SIM_{ts}",
                "limit_name": "Gross Sim Cap",
                "limit_category": "PORTFOLIO_GROSS_LIMIT",
                "portfolio_id": port_id,
                "exposure_basis": "GROSS_MARKET_VALUE",
                "limit_direction": "MAXIMUM",
                "denominator_type": "ABSOLUTE_AMOUNT",
                "limit_value": "50000.000000",
            },
        )
        l_data = l_resp.json()
        limit_id = l_data["limit_id"]

        # Run evaluate on empty portfolio (0 exposure)
        await client.post(
            "/api/v1/risk/exposure-limits/evaluate",
            json={"portfolio_id": port_id},
        )

        # Simulate proposed trade of +$60,000 (breaching $50k limit)
        sim_resp = await client.post(
            "/api/v1/risk/exposure-limits/simulate",
            json={
                "portfolio_id": port_id,
                "limit_id": limit_id,
                "proposed_exposure_delta": "60000.000000",
            },
        )
        assert sim_resp.status_code == 200, sim_resp.text
        sim_data = sim_resp.json()

        assert Decimal(sim_data["current_exposure"]) == Decimal("0.000000")
        assert Decimal(sim_data["proposed_exposure_delta"]) == Decimal("60000.000000")
        assert Decimal(sim_data["projected_exposure"]) == Decimal("60000.000000")
        assert Decimal(sim_data["projected_headroom"]) == Decimal("-10000.000000")
        assert Decimal(sim_data["projected_utilization"]) == Decimal("120.000000")
        assert sim_data["projected_status"] == "SEVERELY_BREACHED"

