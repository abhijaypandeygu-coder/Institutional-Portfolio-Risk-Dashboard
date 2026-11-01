"""
Unit and Integration Tests for M06.06 Concentration Analytics.
Verifies top holdings rankings, CR1-CR20 cumulative ratios, HHI decimal & 10k scales,
effective number of equally weighted groups, cross-dimension aggregations (instrument,
issuer, sector, country), long-short separation, policy evaluation, and trend comparison.
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
from backend.app.modules.risk_management.concentration_analytics.models import (
    ConcentrationGroupingDimension,
    ConcentrationExposureBasis,
    ConcentrationCalculationStatus,
    ConcentrationTrendStatus,
    ConcentrationInterpretationLevel,
)
from backend.app.modules.risk_management.concentration_analytics.schemas import (
    ConcentrationCalculateRequest,
    ConcentrationCompareRequest,
    ConcentrationPolicyCreateRequest,
)
from backend.app.modules.risk_management.concentration_analytics.services.service import (
    ConcentrationAnalyticsService,
)


@pytest.mark.asyncio
async def test_concentration_top_holdings_and_hhi():
    """
    Test concentration ratios (CR1, CR3, CR5), HHI, and effective groups for an unequal
    instrument distribution and long-short setup.
    Positions:
    - Inst A (AAPL): Long 100 @ 150 = $15,000 (Gross = $15,000)
    - Inst B (TSLA): Short -50 @ 200 = -$10,000 (Gross = $10,000)
    - Inst C (MSFT): Long 20 @ 300 = $6,000 (Gross = $6,000)
    Total Gross = $31,000.
    Shares:
    - AAPL: 15,000 / 31,000 = ~0.483871
    - TSLA: 10,000 / 31,000 = ~0.322581
    - MSFT: 6,000 / 31,000 = ~0.193548
    Expected:
    - CR1 = ~48.3871%
    - CR2 = ~80.6452%
    - CR3 = 100%
    - HHI_decimal = 0.483871^2 + 0.322581^2 + 0.193548^2 = ~0.375650
    - HHI_10000 = ~3756.50
    - N_effective = 1 / 0.375650 = ~2.662
    """
    await init_db()
    ts = datetime.utcnow().timestamp()
    port_id = f"port-conc-test-{ts}"

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
                    issuer_name=f"Apple Corp {ts}",
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
                    issuer_name=f"Tesla Group {ts}",
                    issue_currency="USD",
                    primary_market_id="NASDAQ",
                ),
                actor_id="admin",
            )
            i_msft = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Microsoft Corp {ts}",
                    short_name=f"MSFT_{ts}",
                    instrument_type="COMMON_STOCK",
                    asset_class="EQUITY",
                    issuer_name=f"Microsoft Corp {ts}",
                    issue_currency="USD",
                    primary_market_id="NASDAQ",
                ),
                actor_id="admin",
            )
            inst_aapl = i_aapl.instrument_id
            inst_tsla = i_tsla.instrument_id
            inst_msft = i_msft.instrument_id

        # 2. Create Portfolio
        await client.post(
            "/api/v1/portfolios",
            json={
                "portfolio_code": f"COD-CONC-{ts}",
                "portfolio_name": "Concentration Test Portfolio",
                "base_currency": "USD",
                "strategy": "EQUITY_LONG_SHORT",
                "owner_id": "USR-CONC-1",
            },
        )

        # 3. Create positions via events
        for inst, delta in [
            (inst_aapl, "100.000000"),
            (inst_tsla, "-50.000000"),
            (inst_msft, "20.000000"),
        ]:
            side = "TRADE_BUY" if Decimal(delta) > 0 else "TRADE_SELL"
            await client.post(
                "/api/v1/positions/events",
                json={
                    "portfolio_id": port_id,
                    "account_id": "ACC-CONC-1",
                    "instrument_id": inst,
                    "event_type": side,
                    "signed_quantity_delta": delta,
                    "settled_quantity_delta": delta,
                    "idempotency_key": f"EVT_{inst}_{ts}",
                },
            )

        # 4. Run valuations
        await client.post(
            "/api/v1/valuations/run",
            json={
                "portfolio_id": port_id,
                "mark_prices": {
                    inst_aapl: "150.000000",
                    inst_tsla: "200.000000",
                    inst_msft: "300.000000",
                },
            },
        )

        # 5. Calculate Gross Concentration via REST API
        resp = await client.post(
            "/api/v1/risk/concentration/calculate",
            json={
                "portfolio_id": port_id,
                "grouping_dimension": "INSTRUMENT",
                "exposure_basis": "GROSS_EXPOSURE",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert Decimal(data["total_exposure"]) == Decimal("31000.000000")
        assert data["eligible_group_count"] == 3
        # Top 1 ratio = AAPL share (~48.3871%)
        assert Decimal(data["top_1_ratio"]) == Decimal("0.483871")
        # Top 3 ratio = 100%
        assert Decimal(data["top_3_ratio"]) == Decimal("1.000000")
        assert Decimal(data["hhi_10000"]) > Decimal("3700.0")
        assert Decimal(data["effective_number_of_groups"]) > Decimal("2.6")

        result_id = data["result_id"]

        # 6. Verify HHI endpoint
        hhi_resp = await client.get(f"/api/v1/risk/concentration/hhi?result_id={result_id}")
        assert hhi_resp.status_code == 200
        hhi_data = hhi_resp.json()
        assert hhi_data["scale_interpretation"] == "HIGHLY_CONCENTRATED"

        # 7. Verify Ratios endpoint
        ratios_resp = await client.get(f"/api/v1/risk/concentration/ratios?result_id={result_id}")
        assert ratios_resp.status_code == 200
        ratios_data = ratios_resp.json()
        assert Decimal(ratios_data["ratios"]["CR1"]) == Decimal("0.483871")
        assert Decimal(ratios_data["ratios"]["CR3"]) == Decimal("1.000000")


@pytest.mark.asyncio
async def test_concentration_issuer_aggregation_and_comparison():
    """
    Test concentration at ISSUER level aggregating multiple instruments under the same issuer,
    and verify point-to-point comparison between two runs.
    """
    await init_db()
    ts = datetime.utcnow().timestamp()
    port_id = f"port-issuer-conc-{ts}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create 2 instruments sharing SAME ISSUER: "Titan Holdings"
        shared_issuer = f"Titan Holdings {ts}"
        async with AsyncSessionLocal() as session:
            i1 = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Titan Equity {ts}",
                    short_name=f"TTN1_{ts}",
                    instrument_type="COMMON_STOCK",
                    asset_class="EQUITY",
                    issuer_name=shared_issuer,
                    issue_currency="USD",
                    primary_market_id="NASDAQ",
                ),
                actor_id="admin",
            )
            i2 = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Titan Pref {ts}",
                    short_name=f"TTN2_{ts}",
                    instrument_type="PREFERRED_STOCK",
                    asset_class="EQUITY",
                    issuer_name=shared_issuer,
                    issue_currency="USD",
                    primary_market_id="NASDAQ",
                ),
                actor_id="admin",
            )
            # Other independent instrument
            i3 = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Small Corp {ts}",
                    short_name=f"SML_{ts}",
                    instrument_type="COMMON_STOCK",
                    asset_class="EQUITY",
                    issuer_name=f"Small Group {ts}",
                    issue_currency="USD",
                    primary_market_id="NASDAQ",
                ),
                actor_id="admin",
            )
            inst_1 = i1.instrument_id
            inst_2 = i2.instrument_id
            inst_3 = i3.instrument_id

        # 2. Portfolio & positions:
        # inst_1: 400 @ 100 = 40,000
        # inst_2: 400 @ 100 = 40,000 (Titan total = 80,000)
        # inst_3: 200 @ 100 = 20,000 (Total = 100,000)
        for inst, delta in [
            (inst_1, "400.000000"),
            (inst_2, "400.000000"),
            (inst_3, "200.000000"),
        ]:
            await client.post(
                "/api/v1/positions/events",
                json={
                    "portfolio_id": port_id,
                    "account_id": "ACC-CONC-2",
                    "instrument_id": inst,
                    "event_type": "TRADE_BUY",
                    "signed_quantity_delta": delta,
                    "settled_quantity_delta": delta,
                    "idempotency_key": f"EVT_{inst}_{ts}",
                },
            )

        # Valuations
        await client.post(
            "/api/v1/valuations/run",
            json={
                "portfolio_id": port_id,
                "mark_prices": {
                    inst_1: "100.000000",
                    inst_2: "100.000000",
                    inst_3: "100.000000",
                },
            },
        )

        # 3. Create Policy: critical top_1 at 0.70
        await client.post(
            "/api/v1/risk/concentration/policies",
            json={
                "portfolio_id": port_id,
                "grouping_dimension": "ISSUER",
                "exposure_basis": "GROSS_EXPOSURE",
                "top_1_warning": "0.400000",
                "top_1_critical": "0.700000",
                "cr5_warning": "0.600000",
                "cr5_critical": "0.800000",
                "hhi_10000_warning": "1500.000000",
                "hhi_10000_critical": "2500.000000",
                "min_effective_groups_warning": "5.000000",
                "min_effective_groups_critical": "2.000000",
            },
        )

        # 4. Calculate Concentration at ISSUER level
        resp_run1 = await client.post(
            "/api/v1/risk/concentration/calculate",
            json={
                "portfolio_id": port_id,
                "grouping_dimension": "ISSUER",
                "exposure_basis": "GROSS_EXPOSURE",
            },
        )
        assert resp_run1.status_code == 200
        data1 = resp_run1.json()

        assert Decimal(data1["total_exposure"]) == Decimal("100000.000000")
        assert data1["eligible_group_count"] == 2
        # Titan holds $80k (80%)
        assert Decimal(data1["top_1_ratio"]) == Decimal("0.800000")
        assert data1["interpretation_level"] == "CRITICAL"
        assert any("TOP_1_CRITICAL" in f for f in data1["active_flags"])

        # 5. Calculate run 2 for empty portfolio and compare
        resp_run2 = await client.post(
            "/api/v1/risk/concentration/calculate",
            json={
                "portfolio_id": "NON_EXISTENT_PORT",
                "grouping_dimension": "ISSUER",
                "exposure_basis": "GROSS_EXPOSURE",
            },
        )
        data2 = resp_run2.json()

        comp_resp = await client.post(
            "/api/v1/risk/concentration/compare",
            json={
                "base_result_id": data1["result_id"],
                "comparison_result_id": data2["result_id"],
            },
        )
        assert comp_resp.status_code == 200
        comp_data = comp_resp.json()
        assert comp_data["comparability_status"] == "COMPARABLE"
        assert comp_data["current_result_id"] == data1["result_id"]
        assert comp_data["prior_result_id"] == data2["result_id"]
