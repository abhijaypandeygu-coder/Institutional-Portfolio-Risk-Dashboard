import pytest
import uuid
from datetime import date, datetime
import httpx

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.instrument_reference_data.instrument_master.services.service import InstrumentMasterService
from backend.app.modules.instrument_reference_data.instrument_master.schemas import InstrumentCreateRequest
from backend.app.modules.instrument_reference_data.instrument_lifecycle.state_machine.transitions import (
    ListingLifecycleStatus,
    InstrumentLifecycleStatus,
    validate_listing_transition
)
from backend.app.modules.instrument_reference_data.instrument_lifecycle.models import (
    SuspensionType,
    ResumptionType,
    DelistingType
)
from backend.app.modules.instrument_reference_data.instrument_lifecycle.schemas import (
    RegisterListingLifecycleRequest,
    RegisterSuspensionRequest,
    RegisterResumptionRequest,
    RegisterDelistingRequest
)
from backend.app.modules.instrument_reference_data.instrument_lifecycle.services.service import InstrumentLifecycleService


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()
    yield


@pytest.fixture
async def sample_instrument():
    async with AsyncSessionLocal() as session:
        rand_id = uuid.uuid4().hex[:6].upper()
        inst = await InstrumentMasterService.create_instrument(
            session,
            InstrumentCreateRequest(
                canonical_name=f"Lifecycle Test Asset {rand_id}",
                short_name=f"TEST_LC_{rand_id}",
                instrument_type="COMMON_STOCK",
                asset_class="EQUITY",
                issue_currency="INR"
            ),
            actor_id="admin"
        )
        return inst


@pytest.mark.asyncio
async def test_state_machine_transition_validation():
    # Valid transitions
    assert validate_listing_transition(ListingLifecycleStatus.ACTIVE, ListingLifecycleStatus.SUSPENDED) is True
    assert validate_listing_transition(ListingLifecycleStatus.SUSPENDED, ListingLifecycleStatus.ACTIVE) is True
    assert validate_listing_transition(ListingLifecycleStatus.ACTIVE, ListingLifecycleStatus.DELISTING_ANNOUNCED) is True
    assert validate_listing_transition(ListingLifecycleStatus.DELISTING_ANNOUNCED, ListingLifecycleStatus.DELISTED) is True

    # Invalid transitions
    assert validate_listing_transition(ListingLifecycleStatus.DELISTED, ListingLifecycleStatus.ACTIVE) is False
    assert validate_listing_transition(ListingLifecycleStatus.PENDING_LISTING, ListingLifecycleStatus.DELISTED) is False


@pytest.mark.asyncio
async def test_suspension_and_resumption_workflow(sample_instrument):
    async with AsyncSessionLocal() as session:
        service = InstrumentLifecycleService(session)
        listing_id = f"LIST_{uuid.uuid4().hex[:6].upper()}"

        # 1. Register Active Listing
        rec = await service.register_listing_lifecycle(
            RegisterListingLifecycleRequest(
                listing_id=listing_id,
                instrument_id=sample_instrument.instrument_id,
                exchange_code="NSE",
                first_trading_date=date(2026, 1, 15),
                initial_status=ListingLifecycleStatus.ACTIVE
            )
        )
        assert rec.current_status == ListingLifecycleStatus.ACTIVE

        # 2. Register Suspension
        susp_id = f"SUSP_{uuid.uuid4().hex[:6].upper()}"
        susp = await service.register_suspension(
            RegisterSuspensionRequest(
                suspension_id=susp_id,
                listing_id=listing_id,
                suspension_type=SuspensionType.REGULATORY_SUSPENSION,
                effective_start_date=date(2026, 4, 1),
                is_open_ended=True,
                reason="Pending compliance disclosure"
            )
        )
        assert susp.suspension_id == susp_id
        
        # Verify status projected as SUSPENDED
        listing_updated = await service.repo.get_listing_record(listing_id)
        assert listing_updated.current_status == ListingLifecycleStatus.SUSPENDED

        # 3. Register Resumption
        resump_id = f"RESUMP_{uuid.uuid4().hex[:6].upper()}"
        resump = await service.register_resumption(
            RegisterResumptionRequest(
                resumption_id=resump_id,
                listing_id=listing_id,
                related_suspension_id=susp_id,
                effective_resume_date=date(2026, 4, 15),
                reason="Compliance disclosure filed and approved"
            )
        )
        assert resump.resumption_id == resump_id

        # Verify status returned to ACTIVE
        listing_resumed = await service.repo.get_listing_record(listing_id)
        assert listing_resumed.current_status == ListingLifecycleStatus.ACTIVE

        # Verify event history
        events = await service.repo.list_events_by_listing(listing_id)
        assert len(events) == 3


@pytest.mark.asyncio
async def test_multi_venue_listing_independence_and_delisting(sample_instrument):
    async with AsyncSessionLocal() as session:
        service = InstrumentLifecycleService(session)
        nse_listing = f"LIST_NSE_{uuid.uuid4().hex[:6].upper()}"
        bse_listing = f"LIST_BSE_{uuid.uuid4().hex[:6].upper()}"

        # Register NSE listing (Active)
        await service.register_listing_lifecycle(
            RegisterListingLifecycleRequest(
                listing_id=nse_listing,
                instrument_id=sample_instrument.instrument_id,
                exchange_code="NSE",
                initial_status=ListingLifecycleStatus.ACTIVE
            )
        )

        # Register BSE listing (Active)
        await service.register_listing_lifecycle(
            RegisterListingLifecycleRequest(
                listing_id=bse_listing,
                instrument_id=sample_instrument.instrument_id,
                exchange_code="BSE",
                initial_status=ListingLifecycleStatus.ACTIVE
            )
        )

        # Delist BSE listing
        delist_id = f"DELIST_{uuid.uuid4().hex[:6].upper()}"
        await service.register_delisting(
            RegisterDelistingRequest(
                delisting_id=delist_id,
                listing_id=bse_listing,
                delisting_type=DelistingType.VOLUNTARY_DELISTING,
                announcement_date=date(2026, 5, 1),
                last_trading_date=date(2026, 5, 20),
                effective_delisting_date=date(2026, 5, 21),
                reason="Consolidation of liquidity to NSE"
            )
        )

        # NSE listing must remain ACTIVE
        rec_nse = await service.repo.get_listing_record(nse_listing)
        assert rec_nse.current_status == ListingLifecycleStatus.ACTIVE

        # BSE listing is DELISTED
        rec_bse = await service.repo.get_listing_record(bse_listing)
        assert rec_bse.current_status in (ListingLifecycleStatus.DELISTED, ListingLifecycleStatus.DELISTING_ANNOUNCED)

        # Instrument-level summary must show PARTIALLY_TRADABLE (1 active, 1 delisted)
        summary = await service.get_instrument_summary(sample_instrument.instrument_id)
        assert summary.total_listings == 2
        assert summary.active_listings_count == 1
        assert summary.derived_status == InstrumentLifecycleStatus.PARTIALLY_TRADABLE


@pytest.mark.asyncio
async def test_bitemporal_point_in_time_status(sample_instrument):
    async with AsyncSessionLocal() as session:
        service = InstrumentLifecycleService(session)
        listing_id = f"LIST_TIME_{uuid.uuid4().hex[:6].upper()}"

        await service.register_listing_lifecycle(
            RegisterListingLifecycleRequest(
                listing_id=listing_id,
                instrument_id=sample_instrument.instrument_id,
                exchange_code="NASDAQ",
                first_trading_date=date(2026, 1, 1),
                initial_status=ListingLifecycleStatus.ACTIVE
            )
        )

        # Suspension on 2026-06-01
        await service.register_suspension(
            RegisterSuspensionRequest(
                suspension_id=f"SUSP_{uuid.uuid4().hex[:6].upper()}",
                listing_id=listing_id,
                effective_start_date=date(2026, 6, 1),
                reason="Late quarterly report"
            )
        )

        # Query as-of 2026-05-15 -> Should be ACTIVE
        status_may = await service.repo.get_historical_status_as_of(listing_id, date(2026, 5, 15))
        assert status_may == ListingLifecycleStatus.ACTIVE

        # Query as-of 2026-06-15 -> Should be SUSPENDED
        status_june = await service.repo.get_historical_status_as_of(listing_id, date(2026, 6, 15))
        assert status_june == ListingLifecycleStatus.SUSPENDED


@pytest.mark.asyncio
async def test_rest_api_lifecycle(sample_instrument):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        rand_id = uuid.uuid4().hex[:6].upper()
        listing_id = f"API_LIST_{rand_id}"

        # 1. Register listing
        payload = {
            "listing_id": listing_id,
            "instrument_id": sample_instrument.instrument_id,
            "exchange_code": "NYSE",
            "first_trading_date": "2026-01-10",
            "initial_status": "ACTIVE"
        }
        res_create = await client.post("/api/v1/instrument-lifecycle/listings", json=payload)
        assert res_create.status_code == 201

        # 2. Get listing
        res_get = await client.get(f"/api/v1/instrument-lifecycle/listings/{listing_id}")
        assert res_get.status_code == 200
        assert res_get.json()["current_status"] == "ACTIVE"

        # 3. Query historical status
        res_hist = await client.get(f"/api/v1/instrument-lifecycle/listings/{listing_id}/status/as-of?as_of_date=2026-02-01")
        assert res_hist.status_code == 200
        assert res_hist.json()["historical_status"] == "ACTIVE"

        # 4. Instrument summary
        res_sum = await client.get(f"/api/v1/instrument-lifecycle/instruments/{sample_instrument.instrument_id}/summary")
        assert res_sum.status_code == 200
        assert res_sum.json()["total_listings"] >= 1

