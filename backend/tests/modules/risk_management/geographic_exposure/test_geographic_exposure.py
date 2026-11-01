"""
Tests for M06.05 Geographic Exposure.
Verifies country and regional exposure aggregation, issuer domicile mapping,
revenue-source geography allocation, residual unknown tracking, and historical snapshot comparisons.
"""

import pytest
import time
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.modules.instrument_reference_data.instrument_master.services.service import (
    InstrumentMasterService,
)
from backend.app.modules.instrument_reference_data.instrument_master.schemas import (
    InstrumentCreateRequest,
)
from backend.app.modules.instrument_reference_data.geographic_classification.services.service import (
    GeographicReferenceService,
)
from backend.app.modules.instrument_reference_data.geographic_classification.schemas import (
    CountryCreateRequest,
    RegionCreateRequest,
    CountryRegionAssignRequest,
    IssuerGeographicAssignRequest,
    IssuerRevenueGeographyCreateRequest,
)
from backend.app.modules.instrument_reference_data.geographic_classification.models import (
    GeographicAttributeType,
)
from backend.app.modules.portfolio_management.portfolio_history.models import (
    PortfolioBookSnapshot,
    HistoricalPositionSnapshot,
    HistoricalValuationSnapshot,
)
from backend.app.modules.portfolio_management.portfolio_history.repositories.repository import (
    PortfolioHistoryRepository,
)
from backend.app.modules.portfolio_management.multi_portfolio_management.services.service import (
    MultiPortfolioService,
)
from backend.app.modules.portfolio_management.multi_portfolio_management.schemas import (
    PortfolioGroupCreateRequest,
    PortfolioGroupMembershipAddRequest,
)


@pytest.mark.asyncio
async def test_geographic_exposure_domicile_and_revenue_attribution():
    await init_db()
    ts = datetime.utcnow().timestamp()
    port_id = f"port-geo-test-{ts}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register Geographic Reference Data (Countries and Regions)
        async with AsyncSessionLocal() as session:
            geo_svc = GeographicReferenceService(session)

            # Countries: USA, IND, GBR
            await geo_svc.register_country(
                CountryCreateRequest(country_id="USA", iso_alpha2="US", canonical_name="United States")
            )
            await geo_svc.register_country(
                CountryCreateRequest(country_id="IND", iso_alpha2="IN", canonical_name="India")
            )
            await geo_svc.register_country(
                CountryCreateRequest(country_id="GBR", iso_alpha2="GB", canonical_name="United Kingdom")
            )

            # Regions: North America, Asia, Europe
            await geo_svc.register_region(
                RegionCreateRequest(region_id="REG_NA", region_code="NA", region_name="North America")
            )
            await geo_svc.register_region(
                RegionCreateRequest(region_id="REG_ASIA", region_code="ASIA", region_name="Asia")
            )
            await geo_svc.register_region(
                RegionCreateRequest(region_id="REG_EMEA", region_code="EMEA", region_name="Europe")
            )

            # Country-to-Region assignments
            await geo_svc.assign_country_to_region(
                CountryRegionAssignRequest(country_id="USA", region_id="REG_NA")
            )
            await geo_svc.assign_country_to_region(
                CountryRegionAssignRequest(country_id="IND", region_id="REG_ASIA")
            )
            await geo_svc.assign_country_to_region(
                CountryRegionAssignRequest(country_id="GBR", region_id="REG_EMEA")
            )

            # Canonical instruments:
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
            i_infy = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Infosys Ltd {ts}",
                    short_name=f"INFY_{ts}",
                    instrument_type="COMMON_STOCK",
                    asset_class="EQUITY",
                    issue_currency="USD",
                    primary_market_id="NSE",
                ),
                actor_id="admin",
            )
            i_uncl = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Unknown Domicile Co {ts}",
                    short_name=f"UNCL_{ts}",
                    instrument_type="COMMON_STOCK",
                    asset_class="EQUITY",
                    issue_currency="USD",
                    primary_market_id="NYSE",
                ),
                actor_id="admin",
            )

            inst_aapl = i_aapl.instrument_id
            inst_infy = i_infy.instrument_id
            inst_uncl = i_uncl.instrument_id

            # Issuer Domicile Assignments
            await geo_svc.assign_issuer_geography(
                IssuerGeographicAssignRequest(
                    instrument_id=inst_aapl,
                    country_id="USA",
                    attribute_type=GeographicAttributeType.ISSUER_DOMICILE,
                    allocation_weight=Decimal("1.000000"),
                )
            )
            await geo_svc.assign_issuer_geography(
                IssuerGeographicAssignRequest(
                    instrument_id=inst_infy,
                    country_id="IND",
                    attribute_type=GeographicAttributeType.ISSUER_DOMICILE,
                    allocation_weight=Decimal("1.000000"),
                )
            )

            # Revenue Geography Assignments for AAPL
            now = datetime.now(timezone.utc)
            await geo_svc.add_revenue_geography(
                IssuerRevenueGeographyCreateRequest(
                    instrument_id=inst_aapl,
                    country_id="USA",
                    geographic_segment_code="US_DOMESTIC",
                    fiscal_period_end=now,
                    revenue_percentage=Decimal("0.600000"),
                    allocation_weight=Decimal("0.600000"),
                )
            )
            await geo_svc.add_revenue_geography(
                IssuerRevenueGeographyCreateRequest(
                    instrument_id=inst_aapl,
                    country_id="IND",
                    geographic_segment_code="ASIA_PACIFIC",
                    fiscal_period_end=now,
                    revenue_percentage=Decimal("0.300000"),
                    allocation_weight=Decimal("0.300000"),
                )
            )
            await session.commit()

        # 2. Setup Positions and Valuations via REST
        # AAPL: Long 100 @ $100 = $10,000
        # INFY: Short 50 @ $100 = -$5,000 (Absolute Short = $5,000)
        # UNCL: Long 10 @ $100 = $1,000
        # Total Long: 10,000 + 1,000 = 11,000
        # Total Short: 5,000
        # Total Gross: 16,000
        # Total Net: 6,000
        for inst, delta in [
            (inst_aapl, "100.000000"),
            (inst_infy, "-50.000000"),
            (inst_uncl, "10.000000"),
        ]:
            side = "TRADE_BUY" if Decimal(delta) > 0 else "TRADE_SELL"
            await client.post(
                "/api/v1/positions/events",
                json={
                    "portfolio_id": port_id,
                    "account_id": "ACC-GEO-1",
                    "instrument_id": inst,
                    "event_type": side,
                    "signed_quantity_delta": delta,
                    "settled_quantity_delta": delta,
                    "idempotency_key": f"EVT_{inst}_{ts}",
                },
            )

        await client.post(
            "/api/v1/valuations/run",
            json={
                "portfolio_id": port_id,
                "mark_prices": {
                    inst_aapl: "100.000000",
                    inst_infy: "100.000000",
                    inst_uncl: "100.000000",
                },
            },
        )

        # 3. Calculate Geographic Exposure under ISSUER_DOMICILE
        res_dom = await client.post(
            f"/api/v1/portfolios/{port_id}/risk/geographic-exposure/calculate",
            json={
                "portfolio_id": port_id,
                "geographic_attribute": "ISSUER_DOMICILE",
            },
        )
        assert res_dom.status_code == 200, res_dom.text
        data_dom = res_dom.json()

        assert Decimal(data_dom["total_long_exposure"]) == Decimal("11000.000000")
        assert Decimal(data_dom["total_short_exposure"]) == Decimal("5000.000000")
        assert Decimal(data_dom["total_gross_exposure"]) == Decimal("16000.000000")
        assert Decimal(data_dom["classified_gross_exposure"]) == Decimal("15000.000000")
        assert Decimal(data_dom["unknown_gross_exposure"]) == Decimal("1000.000000")
        assert data_dom["coverage_status"] == "PARTIAL"

        # USA (AAPL): Gross 10,000
        # IND (INFY): Gross 5,000 (Short 5,000)
        c_usa = next(c for c in data_dom["countries"] if c["country_id"] == "USA")
        c_ind = next(c for c in data_dom["countries"] if c["country_id"] == "IND")
        assert Decimal(c_usa["gross_exposure"]) == Decimal("10000.000000")
        assert Decimal(c_ind["short_exposure"]) == Decimal("5000.000000")
        assert c_usa["rank"] == 1
        assert c_ind["rank"] == 2

        # Check regional roll-up
        r_na = next(r for r in data_dom["regions"] if r["region_id"] == "REG_NA")
        r_asia = next(r for r in data_dom["regions"] if r["region_id"] == "REG_ASIA")
        assert Decimal(r_na["gross_exposure"]) == Decimal("10000.000000")
        assert Decimal(r_asia["gross_exposure"]) == Decimal("5000.000000")

        # Unknown holdings
        assert len(data_dom["unknown_holdings"]) == 1
        assert data_dom["unknown_holdings"][0]["instrument_id"] == inst_uncl

        # 4. Calculate Geographic Exposure under REVENUE_GEOGRAPHY
        res_rev = await client.post(
            f"/api/v1/portfolios/{port_id}/risk/geographic-exposure/calculate",
            json={
                "portfolio_id": port_id,
                "geographic_attribute": "REVENUE_GEOGRAPHY",
            },
        )
        assert res_rev.status_code == 200, res_rev.text
        data_rev = res_rev.json()

        # AAPL ($10k gross): 60% USA ($6k), 30% IND ($3k), 10% Residual ($1k)
        # INFY ($5k gross): No revenue data -> 100% Unknown
        # UNCL ($1k gross): No revenue data -> 100% Unknown
        # Total Unknown Gross = $1k (AAPL residual) + $5k (INFY) + $1k (UNCL) = $7,000
        # Classified Gross = $6k (USA) + $3k (IND) = $9,000
        assert Decimal(data_rev["classified_gross_exposure"]) == Decimal("9000.000000")
        assert Decimal(data_rev["unknown_gross_exposure"]) == Decimal("7000.000000")
        rev_usa = next(c for c in data_rev["countries"] if c["country_id"] == "USA")
        rev_ind = next(c for c in data_rev["countries"] if c["country_id"] == "IND")
        assert Decimal(rev_usa["gross_exposure"]) == Decimal("6000.000000")
        assert Decimal(rev_ind["gross_exposure"]) == Decimal("3000.000000")

        # Check query endpoints
        countries_resp = await client.get(f"/api/v1/portfolios/{port_id}/risk/geographic-exposure/countries")
        assert countries_resp.status_code == 200
        regions_resp = await client.get(f"/api/v1/portfolios/{port_id}/risk/geographic-exposure/regions")
        assert regions_resp.status_code == 200
        unknown_resp = await client.get(f"/api/v1/portfolios/{port_id}/risk/geographic-exposure/unknown")
        assert unknown_resp.status_code == 200


@pytest.mark.asyncio
async def test_geographic_exposure_group_and_comparison():
    await init_db()
    ts = datetime.utcnow().timestamp()
    p1 = f"port-geo-p1-{ts}"
    p2 = f"port-geo-p2-{ts}"
    group_id = f"grp-geo-{ts}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with AsyncSessionLocal() as session:
            geo_svc = GeographicReferenceService(session)
            hist_repo = PortfolioHistoryRepository(session)
            multi_port_svc = MultiPortfolioService(session)

            inst_obj = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Microsoft Corp {ts}",
                    short_name=f"MSFT_{ts}",
                    instrument_type="COMMON_STOCK",
                    asset_class="EQUITY",
                    issue_currency="USD",
                    primary_market_id="NASDAQ",
                ),
                actor_id="admin",
            )
            inst = inst_obj.instrument_id

            await geo_svc.register_country(
                CountryCreateRequest(country_id="USA", iso_alpha2="US", canonical_name="United States")
            )
            await geo_svc.assign_issuer_geography(
                IssuerGeographicAssignRequest(
                    instrument_id=inst,
                    country_id="USA",
                    allocation_weight=Decimal("1.000000"),
                )
            )

            # Portfolio group setup
            grp = await multi_port_svc.create_group(
                PortfolioGroupCreateRequest(
                    group_code=f"GEO_GRP_{int(ts)}",
                    group_name=f"Global Group {ts}",
                    owner_reference="admin",
                    reporting_currency="USD",
                )
            )
            group_id = grp.id
            await multi_port_svc.add_portfolio_to_group(
                group_id, PortfolioGroupMembershipAddRequest(portfolio_id=p1)
            )
            await multi_port_svc.add_portfolio_to_group(
                group_id, PortfolioGroupMembershipAddRequest(portfolio_id=p2)
            )

            # Historical Snapshots
            now = datetime.now(timezone.utc)
            snap_prior = await hist_repo.create_snapshot(
                PortfolioBookSnapshot(
                    snapshot_id=f"snap-geo-prior-{ts}",
                    portfolio_id=p1,
                    effective_as_of=now,
                    knowledge_as_of=now,
                    base_currency="USD",
                    total_positions_count=1,
                    snapshot_hash=f"hash-geo-prior-{ts}",
                )
            )
            snap_curr = await hist_repo.create_snapshot(
                PortfolioBookSnapshot(
                    snapshot_id=f"snap-geo-curr-{ts}",
                    portfolio_id=p1,
                    effective_as_of=now,
                    knowledge_as_of=now,
                    base_currency="USD",
                    total_positions_count=1,
                    snapshot_hash=f"hash-geo-curr-{ts}",
                )
            )

            # Prior: 50 MSFT @ $100 = $5,000 (USA)
            session.add(
                HistoricalPositionSnapshot(
                    id=f"hpos-geo-prior-{ts}",
                    snapshot_id=snap_prior.snapshot_id,
                    portfolio_id=p1,
                    account_id=f"acct1-{ts}",
                    instrument_id=inst,
                    net_signed_quantity=Decimal("50.000000"),
                    currency="USD",
                    effective_as_of=now,
                    knowledge_as_of=now,
                )
            )
            session.add(
                HistoricalValuationSnapshot(
                    id=f"hval-geo-prior-{ts}",
                    snapshot_id=snap_prior.snapshot_id,
                    portfolio_id=p1,
                    instrument_id=inst,
                    price_source="EOD_CLOSE",
                    price_timestamp=now,
                    market_price=Decimal("100.000000"),
                    price_currency="USD",
                    market_value_local=Decimal("5000.000000"),
                    market_value_base=Decimal("5000.000000"),
                    cost_basis_base=Decimal("5000.000000"),
                    unrealized_pnl_base=Decimal("0.000000"),
                )
            )

            # Current: 100 MSFT @ $100 = $10,000 (USA)
            session.add(
                HistoricalPositionSnapshot(
                    id=f"hpos-geo-curr-{ts}",
                    snapshot_id=snap_curr.snapshot_id,
                    portfolio_id=p1,
                    account_id=f"acct1-{ts}",
                    instrument_id=inst,
                    net_signed_quantity=Decimal("100.000000"),
                    currency="USD",
                    effective_as_of=now,
                    knowledge_as_of=now,
                )
            )
            session.add(
                HistoricalValuationSnapshot(
                    id=f"hval-geo-curr-{ts}",
                    snapshot_id=snap_curr.snapshot_id,
                    portfolio_id=p1,
                    instrument_id=inst,
                    price_source="EOD_CLOSE",
                    price_timestamp=now,
                    market_price=Decimal("100.000000"),
                    price_currency="USD",
                    market_value_local=Decimal("10000.000000"),
                    market_value_base=Decimal("10000.000000"),
                    cost_basis_base=Decimal("10000.000000"),
                    unrealized_pnl_base=Decimal("0.000000"),
                )
            )
            await session.commit()

        # Add positions: P1 (100 MSFT), P2 (50 MSFT)
        await client.post(
            "/api/v1/positions/events",
            json={
                "portfolio_id": p1,
                "account_id": f"acct1-{ts}",
                "instrument_id": inst,
                "event_type": "TRADE_BUY",
                "signed_quantity_delta": "100.000000",
                "settled_quantity_delta": "100.000000",
                "idempotency_key": f"EVT_P1_{inst}_{ts}",
            },
        )
        await client.post(
            "/api/v1/positions/events",
            json={
                "portfolio_id": p2,
                "account_id": f"acct2-{ts}",
                "instrument_id": inst,
                "event_type": "TRADE_BUY",
                "signed_quantity_delta": "50.000000",
                "settled_quantity_delta": "50.000000",
                "idempotency_key": f"EVT_P2_{inst}_{ts}",
            },
        )
        await client.post(
            "/api/v1/valuations/run",
            json={"portfolio_id": p1, "mark_prices": {inst: "100.000000"}},
        )
        await client.post(
            "/api/v1/valuations/run",
            json={"portfolio_id": p2, "mark_prices": {inst: "100.000000"}},
        )

        # 1. Group geographic calculation
        grp_resp = await client.post(
            f"/api/v1/portfolio-groups/{group_id}/risk/geographic-exposure/calculate",
            json={"portfolio_group_id": group_id},
        )
        assert grp_resp.status_code == 200, grp_resp.text
        grp_data = grp_resp.json()
        assert grp_data["entity_type"] == "PORTFOLIO_GROUP"
        assert Decimal(grp_data["total_gross_exposure"]) == Decimal("15000.000000")
        assert len(grp_data["countries"]) == 1
        assert grp_data["countries"][0]["country_id"] == "USA"
        assert Decimal(grp_data["countries"][0]["gross_exposure"]) == Decimal("15000.000000")

        # 2. Historical snapshot comparison
        comp_resp = await client.get(
            f"/api/v1/portfolios/{p1}/risk/geographic-exposure/comparison"
            f"?current_snapshot_id={snap_curr.snapshot_id}&prior_snapshot_id={snap_prior.snapshot_id}"
        )
        assert comp_resp.status_code == 200, comp_resp.text
        comp_data = comp_resp.json()
        assert len(comp_data["items"]) == 1
        c_item = comp_data["items"][0]
        assert c_item["entity_id"] == "USA"
        assert Decimal(c_item["current_gross_exposure"]) == Decimal("10000.000000")
        assert Decimal(c_item["prior_gross_exposure"]) == Decimal("5000.000000")
        assert Decimal(c_item["gross_exposure_change"]) == Decimal("5000.000000")
        assert Decimal(c_item["gross_percentage_change"]) == Decimal("100.000000")
        assert c_item["lifecycle_status"] == "INCREASED_EXPOSURE"
