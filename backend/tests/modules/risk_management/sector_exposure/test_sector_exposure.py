"""
M06.03 Sector Exposure Tests.
Integration and unit tests verifying:
1. Sector Aggregation (Long, Short, Gross, Net).
2. Industry Aggregation and parent-sector reconciliation.
3. NAV-based weights and Invested-Equity allocation weights.
4. Unclassified and missing classification reporting and coverage metrics.
5. Benchmark-relative sector exposure and active overweight/underweight classification.
6. Consolidated multi-portfolio group sector aggregation.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.modules.instrument_reference_data.security_classification.services.service import (
    SecurityClassificationService,
)
from backend.app.modules.instrument_reference_data.security_classification.schemas import (
    ClassificationSchemeCreate,
    ClassificationNodeCreate,
    ClassificationAssignRequest,
)


@pytest.mark.asyncio
async def test_sector_exposure_and_benchmark_comparison():
    await init_db()
    ts = datetime.utcnow().timestamp()
    portfolio_id = f"PORT-SEC-1-{ts}"
    scheme_code = f"GICS_{int(ts)}"

    # 1. Setup Classification Nodes in M04.02 via service directly
    async with AsyncSessionLocal() as session:
        # Create instruments in Instrument Master first
        from backend.app.modules.instrument_reference_data.instrument_master.services.service import (
            InstrumentMasterService,
        )
        from backend.app.modules.instrument_reference_data.instrument_master.schemas import (
            InstrumentCreateRequest,
        )

        inst_aapl_obj = await InstrumentMasterService.create_instrument(
            session,
            InstrumentCreateRequest(canonical_name=f"Apple Inc {ts}", short_name=f"AAPL_{ts}"),
            actor_id="admin",
        )
        inst_msft_obj = await InstrumentMasterService.create_instrument(
            session,
            InstrumentCreateRequest(canonical_name=f"Microsoft Corp {ts}", short_name=f"MSFT_{ts}"),
            actor_id="admin",
        )
        inst_jpm_obj = await InstrumentMasterService.create_instrument(
            session,
            InstrumentCreateRequest(canonical_name=f"JPMorgan Chase {ts}", short_name=f"JPM_{ts}"),
            actor_id="admin",
        )
        inst_unclass_obj = await InstrumentMasterService.create_instrument(
            session,
            InstrumentCreateRequest(canonical_name=f"Unclassified Inc {ts}", short_name=f"UNCL_{ts}"),
            actor_id="admin",
        )

        inst_aapl = inst_aapl_obj.instrument_id
        inst_msft = inst_msft_obj.instrument_id
        inst_jpm = inst_jpm_obj.instrument_id
        inst_unclass = inst_unclass_obj.instrument_id

        await SecurityClassificationService.create_scheme(
            session,
            ClassificationSchemeCreate(
                scheme_code=scheme_code,
                scheme_name="Global Industry Classification Standard",
                description="Standard Taxonomy",
                provider="MSCI/S&P",
            ),
            actor_id="admin",
        )
        sec_tech = await SecurityClassificationService.create_node(
            session,
            scheme_code,
            "1.0.0",
            ClassificationNodeCreate(
                node_code="45",
                node_name="Information Technology",
                node_description="Tech Sector",
                node_type="SECTOR",
                hierarchy_level=1,
            ),
            actor_id="admin",
        )
        await SecurityClassificationService.create_node(
            session,
            scheme_code,
            "1.0.0",
            ClassificationNodeCreate(
                node_code="4510",
                node_name="Software",
                node_description="Software & Services",
                node_type="INDUSTRY",
                parent_node_id=sec_tech.node_id,
                hierarchy_level=2,
            ),
            actor_id="admin",
        )
        await SecurityClassificationService.create_node(
            session,
            scheme_code,
            "1.0.0",
            ClassificationNodeCreate(
                node_code="40",
                node_name="Financials",
                node_description="Financial Sector",
                node_type="SECTOR",
                hierarchy_level=1,
            ),
            actor_id="admin",
        )

        # Assign AAPL and MSFT to Tech/Software
        await SecurityClassificationService.assign_classification(
            session,
            inst_aapl,
            ClassificationAssignRequest(
                scheme_code=scheme_code,
                sector_code="45",
                industry_code="4510",
                assignment_reason="Tech Classification",
            ),
            actor_id="admin",
        )
        await SecurityClassificationService.assign_classification(
            session,
            inst_msft,
            ClassificationAssignRequest(
                scheme_code=scheme_code,
                sector_code="45",
                industry_code="4510",
                assignment_reason="Tech Classification",
            ),
            actor_id="admin",
        )
        # Assign JPM to Financials (without industry)
        await SecurityClassificationService.assign_classification(
            session,
            inst_jpm,
            ClassificationAssignRequest(
                scheme_code=scheme_code,
                sector_code="40",
                assignment_reason="Fin Classification",
            ),
            actor_id="admin",
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 2. Create Portfolio and Positions:
        # Long 500 AAPL @ $100 = $50,000 (Tech / Software)
        # Short 200 MSFT @ $100 = -$20,000 (Tech / Software)
        # Long 300 JPM @ $100 = $30,000 (Financials)
        # Long 100 UNCL @ $100 = $10,000 (Unclassified holding)
        await client.post(
            "/api/v1/portfolios",
            json={
                "portfolio_code": f"COD-SEC-{ts}",
                "portfolio_name": "Sector Exposure Test Portfolio",
                "base_currency": "USD",
                "strategy": "SECTOR_BALANCED",
                "owner_id": "USR-SEC-1",
            },
        )

        for inst, delta in [
            (inst_aapl, "500.000000"),
            (inst_msft, "-200.000000"),
            (inst_jpm, "300.000000"),
            (inst_unclass, "100.000000"),
        ]:
            side = "TRADE_BUY" if Decimal(delta) > 0 else "TRADE_SELL"
            await client.post(
                "/api/v1/positions/events",
                json={
                    "portfolio_id": portfolio_id,
                    "account_id": "ACC-SEC-1",
                    "instrument_id": inst,
                    "event_type": side,
                    "signed_quantity_delta": delta,
                    "settled_quantity_delta": delta,
                    "idempotency_key": f"EVT_{inst}_{ts}",
                },
            )

        # Run valuation ($100 mark for all)
        await client.post(
            "/api/v1/valuations/run",
            json={
                "portfolio_id": portfolio_id,
                "mark_prices": {
                    inst_aapl: "100.000000",
                    inst_msft: "100.000000",
                    inst_jpm: "100.000000",
                    inst_unclass: "100.000000",
                },
            },
        )

        # 3. Create Benchmark Sector Composition:
        bm_id = f"BM-SP500-{ts}"
        await client.post(
            f"/api/v1/benchmarks/{bm_id}/sectors",
            json={
                "benchmark_id": bm_id,
                "benchmark_name": "S&P 500 Sector Weights",
                "sector_id": "45",
                "sector_name": "Information Technology",
                "classification_scheme_code": scheme_code,
                "benchmark_weight": "30.000000",
            },
        )
        await client.post(
            f"/api/v1/benchmarks/{bm_id}/sectors",
            json={
                "benchmark_id": bm_id,
                "benchmark_name": "S&P 500 Sector Weights",
                "sector_id": "40",
                "sector_name": "Financials",
                "classification_scheme_code": scheme_code,
                "benchmark_weight": "40.000000",
            },
        )

        # 4. Execute Sector Exposure Calculation with NAV = $100,000
        res = await client.post(
            f"/api/v1/portfolios/{portfolio_id}/risk/sector-exposure/calculate",
            json={
                "classification_scheme_code": scheme_code,
                "reporting_currency": "USD",
                "weight_basis": "NAV",
                "custom_denominator_value": "100000.000000",
                "benchmark_id": bm_id,
            },
        )
        assert res.status_code == 201
        data = res.json()

        assert Decimal(str(data["total_long_exposure"])) == Decimal("90000.000000") # 50k + 30k + 10k
        assert Decimal(str(data["total_absolute_short_exposure"])) == Decimal("20000.000000")
        assert Decimal(str(data["total_gross_exposure"])) == Decimal("110000.000000")
        assert Decimal(str(data["total_net_exposure"])) == Decimal("70000.000000")

        # Verify Sector Level
        sec_tech = next(s for s in data["sectors"] if s["sector_id"] == "45")
        assert Decimal(str(sec_tech["long_exposure"])) == Decimal("50000.000000")
        assert Decimal(str(sec_tech["absolute_short_exposure"])) == Decimal("20000.000000")
        assert Decimal(str(sec_tech["gross_exposure"])) == Decimal("70000.000000")
        assert Decimal(str(sec_tech["net_exposure"])) == Decimal("30000.000000")
        assert Decimal(str(sec_tech["long_weight"])) == Decimal("50.000000")

        sec_fin = next(s for s in data["sectors"] if s["sector_id"] == "40")
        assert Decimal(str(sec_fin["long_exposure"])) == Decimal("30000.000000")
        assert Decimal(str(sec_fin["long_weight"])) == Decimal("30.000000")

        # Verify Industry Level (Software under Tech)
        ind_soft = next(i for i in data["industries"] if i["industry_id"] == "4510")
        assert Decimal(str(ind_soft["gross_exposure"])) == Decimal("70000.000000")

        # Verify Unclassified Holding
        assert len(data["unclassified"]) == 1
        unclass = data["unclassified"][0]
        assert Decimal(str(unclass["long_exposure"])) == Decimal("10000.000000")
        assert unclass["classification_status"] == "MISSING_CLASSIFICATION"

        # Verify Classification Coverage
        cov = data["coverage"]
        assert cov["total_positions"] == 4
        assert cov["classified_positions"] == 3
        assert cov["unclassified_positions"] == 1
        assert cov["coverage_status"] == "PARTIAL"

        # Verify Benchmark Active Weights
        assert len(data["relative_exposures"]) >= 2
        rel_tech = next(r for r in data["relative_exposures"] if r["sector_id"] == "45")
        assert Decimal(str(rel_tech["active_sector_weight"])) == Decimal("20.000000") # 50% - 30%
        assert rel_tech["active_weight_status"] == "OVERWEIGHT"

        rel_fin = next(r for r in data["relative_exposures"] if r["sector_id"] == "40")
        assert Decimal(str(rel_fin["active_sector_weight"])) == Decimal("-10.000000") # 30% - 40%
        assert rel_fin["active_weight_status"] == "UNDERWEIGHT"

        # 2. Create Portfolio and Positions:
        # Long 500 AAPL @ $100 = $50,000 (Tech / Software)
        # Short 200 MSFT @ $100 = -$20,000 (Tech / Software)
        # Long 300 JPM @ $100 = $30,000 (Financials)
        # Long 100 UNCL @ $100 = $10,000 (Unclassified holding)
        await client.post(
            "/api/v1/portfolios",
            json={
                "portfolio_code": f"COD-SEC-{ts}",
                "portfolio_name": "Sector Exposure Test Portfolio",
                "base_currency": "USD",
                "strategy": "SECTOR_BALANCED",
                "owner_id": "USR-SEC-1",
            },
        )

        for inst, delta in [
            (inst_aapl, "500.000000"),
            (inst_msft, "-200.000000"),
            (inst_jpm, "300.000000"),
            (inst_unclass, "100.000000"),
        ]:
            side = "TRADE_BUY" if Decimal(delta) > 0 else "TRADE_SELL"
            await client.post(
                "/api/v1/positions/events",
                json={
                    "portfolio_id": portfolio_id,
                    "account_id": "ACC-SEC-1",
                    "instrument_id": inst,
                    "event_type": side,
                    "signed_quantity_delta": delta,
                    "settled_quantity_delta": delta,
                    "idempotency_key": f"EVT_{inst}_{ts}",
                },
            )

        # Run valuation ($100 mark for all)
        await client.post(
            "/api/v1/valuations/run",
            json={
                "portfolio_id": portfolio_id,
                "mark_prices": {
                    inst_aapl: "100.000000",
                    inst_msft: "100.000000",
                    inst_jpm: "100.000000",
                    inst_unclass: "100.000000",
                },
            },
        )

        # 3. Create Benchmark Sector Composition:
        # Benchmark "SP500_SEC" has:
        # Tech (45) = 30% (0.30)
        # Financials (40) = 40% (0.40)
        # Energy (10) = 30% (0.30)
        bm_id = f"BM-SP500-{ts}"
        await client.post(
            f"/api/v1/benchmarks/{bm_id}/sectors",
            json={
                "benchmark_id": bm_id,
                "benchmark_name": "S&P 500 Sector Weights",
                "sector_id": "45",
                "sector_name": "Information Technology",
                "classification_scheme_code": f"GICS_{ts}",
                "benchmark_weight": "30.000000",
            },
        )
        await client.post(
            f"/api/v1/benchmarks/{bm_id}/sectors",
            json={
                "benchmark_id": bm_id,
                "benchmark_name": "S&P 500 Sector Weights",
                "sector_id": "40",
                "sector_name": "Financials",
                "classification_scheme_code": f"GICS_{ts}",
                "benchmark_weight": "40.000000",
            },
        )

        # 4. Execute Sector Exposure Calculation with NAV = $100,000
        # Expected Portfolio Holdings:
        # Long Tech: $50,000, Short Tech: $20,000 -> Gross Tech: $70,000, Net Tech: $30,000
        # Long Tech Weight = 50,000 / 100,000 = 50%
        # Long Fin: $30,000, Short Fin: $0 -> Gross Fin: $30,000, Net Fin: $30,000
        # Long Fin Weight = 30,000 / 100,000 = 30%
        # Unclassified: $10,000
        # Benchmark Active Weights:
        # Tech Active Weight = 50% - 30% = +20% -> OVERWEIGHT
        # Fin Active Weight = 30% - 40% = -10% -> UNDERWEIGHT
        res = await client.post(
            f"/api/v1/portfolios/{portfolio_id}/risk/sector-exposure/calculate",
            json={
                "classification_scheme_code": scheme_code,
                "reporting_currency": "USD",
                "weight_basis": "NAV",
                "custom_denominator_value": "100000.000000",
                "benchmark_id": bm_id,
            },
        )
        assert res.status_code == 201
        data = res.json()

        assert Decimal(str(data["total_long_exposure"])) == Decimal("90000.000000") # 50k + 30k + 10k
        assert Decimal(str(data["total_absolute_short_exposure"])) == Decimal("20000.000000")
        assert Decimal(str(data["total_gross_exposure"])) == Decimal("110000.000000")
        assert Decimal(str(data["total_net_exposure"])) == Decimal("70000.000000")

        # Verify Sector Level
        sec_tech = next(s for s in data["sectors"] if s["sector_id"] == "45")
        assert Decimal(str(sec_tech["long_exposure"])) == Decimal("50000.000000")
        assert Decimal(str(sec_tech["absolute_short_exposure"])) == Decimal("20000.000000")
        assert Decimal(str(sec_tech["gross_exposure"])) == Decimal("70000.000000")
        assert Decimal(str(sec_tech["net_exposure"])) == Decimal("30000.000000")
        assert Decimal(str(sec_tech["long_weight"])) == Decimal("50.000000")

        sec_fin = next(s for s in data["sectors"] if s["sector_id"] == "40")
        assert Decimal(str(sec_fin["long_exposure"])) == Decimal("30000.000000")
        assert Decimal(str(sec_fin["long_weight"])) == Decimal("30.000000")

        # Verify Industry Level (Software under Tech)
        ind_soft = next(i for i in data["industries"] if i["industry_id"] == "4510")
        assert Decimal(str(ind_soft["gross_exposure"])) == Decimal("70000.000000")

        # Verify Unclassified Holding
        assert len(data["unclassified"]) == 1
        unclass = data["unclassified"][0]
        assert Decimal(str(unclass["long_exposure"])) == Decimal("10000.000000")
        assert unclass["classification_status"] == "MISSING_CLASSIFICATION"

        # Verify Classification Coverage
        cov = data["coverage"]
        assert cov["total_positions"] == 4
        assert cov["classified_positions"] == 3
        assert cov["unclassified_positions"] == 1
        assert cov["coverage_status"] == "PARTIAL"

        # Verify Benchmark Active Weights
        assert len(data["relative_exposures"]) >= 2
        rel_tech = next(r for r in data["relative_exposures"] if r["sector_id"] == "45")
        assert Decimal(str(rel_tech["active_sector_weight"])) == Decimal("20.000000") # 50% - 30%
        assert rel_tech["active_weight_status"] == "OVERWEIGHT"

        rel_fin = next(r for r in data["relative_exposures"] if r["sector_id"] == "40")
        assert Decimal(str(rel_fin["active_sector_weight"])) == Decimal("-10.000000") # 30% - 40%
        assert rel_fin["active_weight_status"] == "UNDERWEIGHT"


@pytest.mark.asyncio
async def test_group_sector_exposure():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ts = datetime.utcnow().timestamp()
        p1 = f"PORT-GSEC-1-{ts}"
        p2 = f"PORT-GSEC-2-{ts}"

        # Create portfolios
        await client.post(
            "/api/v1/portfolios",
            json={
                "portfolio_code": f"COD-GSEC1-{ts}",
                "portfolio_name": "Group Sector P1",
                "base_currency": "USD",
                "strategy": "LONG_ONLY",
                "owner_id": "USR-P1",
            },
        )
        await client.post(
            "/api/v1/portfolios",
            json={
                "portfolio_code": f"COD-GSEC2-{ts}",
                "portfolio_name": "Group Sector P2",
                "base_currency": "USD",
                "strategy": "LONG_ONLY",
                "owner_id": "USR-P2",
            },
        )

        # Positions
        await client.post(
            "/api/v1/positions/events",
            json={
                "portfolio_id": p1,
                "account_id": "ACC-GSEC-1",
                "instrument_id": "INST-P1-A",
                "event_type": "TRADE_BUY",
                "signed_quantity_delta": "100.000000",
                "settled_quantity_delta": "100.000000",
                "idempotency_key": f"EVT_P1_{ts}",
            },
        )
        await client.post(
            "/api/v1/positions/events",
            json={
                "portfolio_id": p2,
                "account_id": "ACC-GSEC-2",
                "instrument_id": "INST-P2-B",
                "event_type": "TRADE_BUY",
                "signed_quantity_delta": "200.000000",
                "settled_quantity_delta": "200.000000",
                "idempotency_key": f"EVT_P2_{ts}",
            },
        )

        # Valuations (defaults to $100 per share)
        # Group with P1 and P2
        grp_res = await client.post(
            "/api/v1/portfolio-groups",
            json={
                "group_code": f"GRP-SEC-{ts}",
                "group_name": "Sector Group",
                "group_type": "STRATEGY",
                "owner_reference": "USR-GRP-MGR",
                "reporting_currency": "USD",
            },
        )
        assert grp_res.status_code == 201
        group_id = grp_res.json()["id"]

        await client.post(
            f"/api/v1/portfolio-groups/{group_id}/members",
            json={"portfolio_id": p1},
        )
        await client.post(
            f"/api/v1/portfolio-groups/{group_id}/members",
            json={"portfolio_id": p2},
        )

        # Calculate Group Sector Exposure
        res = await client.post(
            f"/api/v1/portfolio-groups/{group_id}/risk/sector-exposure/calculate",
            json={
                "reporting_currency": "USD",
                "weight_basis": "NAV",
                "custom_denominator_value": "30000.000000",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert Decimal(str(data["total_long_exposure"])) == Decimal("30000.000000") # (100 * 100) + (200 * 100)
        assert data["scope"] == "PORTFOLIO_GROUP"
        assert len(data["unclassified"]) == 1
