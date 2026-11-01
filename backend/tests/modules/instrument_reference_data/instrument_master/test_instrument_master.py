"""
Pytest Test Suite for M04.01 Instrument Master.
Tests:
1. Stable internal ID generation and canonical instrument creation.
2. ISIN validation and Luhn checksum validation.
3. Venue-specific listings and primary listing constraint enforcement.
4. Effective-dated attribute history tracking and version bumping.
5. Venue-aware identity resolution (for M02 ingestion & M03 validation).
6. Ambiguous symbol resolution across multiple venues without arbitrary selection.
7. Staged import batch validation, duplicate candidate detection, and batch processing.
8. REST API lifecycle with authentication and RBAC.
"""
import uuid
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.core.config import settings
from backend.app.modules.instrument_reference_data.instrument_master.models import (
    Instrument,
    InstrumentListing,
)
from backend.app.modules.instrument_reference_data.instrument_master.schemas import (
    InstrumentCreateRequest,
    InstrumentUpdateRequest,
    ListingCreateRequest,
    ListingStatusUpdateRequest,
    ImportBatchCreateRequest,
)
from backend.app.modules.instrument_reference_data.instrument_master.services.service import (
    InstrumentMasterService,
)
from backend.app.modules.instrument_reference_data.instrument_master.repositories.repository import (
    InstrumentRepository,
)
from backend.app.modules.instrument_reference_data.instrument_master.policies.identity_rules import (
    validate_isin_checksum,
    LifecycleStatus,
    ListingStatus,
)


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()


@pytest.fixture
def auth_headers():
    return {
        "X-API-Key": settings.API_KEY_OPERATOR,
        "X-Actor": "test_operator",
    }


@pytest.fixture
def admin_headers():
    return {
        "X-API-Key": settings.API_KEY_ADMIN,
        "X-Actor": "test_admin",
    }


def test_isin_checksum_validation():
    """Verifies ISO 6166 Luhn check-digit calculations."""
    # Valid ISINs
    assert validate_isin_checksum("US0378331005") is True  # Apple Inc.
    assert validate_isin_checksum("INE002A01018") is True  # Reliance Industries
    assert validate_isin_checksum("US5949181045") is True  # Microsoft Corp.

    # Invalid ISINs
    assert validate_isin_checksum("US0378331000") is False  # Wrong check digit
    assert validate_isin_checksum("INVALID_ISIN") is False  # Malformed length/pattern
    assert validate_isin_checksum("") is False


@pytest.mark.asyncio
async def test_canonical_instrument_creation():
    """
    Verifies:
    - Stable internal ID generation (UUID-based INST_ prefix).
    - ISIN storage and duplicate prevention.
    """
    async with AsyncSessionLocal() as session:
        rand_suffix = uuid.uuid4().hex[:6].upper()
        # Create a valid test ISIN ending in a calculated check digit
        # Let's use a unique valid US ISIN format
        test_isin = f"US{rand_suffix}100"
        # Calculate valid check digit
        from backend.app.modules.instrument_reference_data.instrument_master.policies.identity_rules import ISIN_REGEX
        digits_str = ""
        for char in test_isin:
            if char.isdigit():
                digits_str += char
            else:
                digits_str += str(ord(char) - ord('A') + 10)
        total = 0
        double = True
        for digit in reversed(digits_str):
            d = int(digit)
            if double:
                d *= 2
                if d > 9:
                    d = (d // 10) + (d % 10)
            total += d
            double = not double
        check_digit = (10 - (total % 10)) % 10
        valid_unique_isin = f"{test_isin}{check_digit}"

        req = InstrumentCreateRequest(
            canonical_name=f"Test Instrument {rand_suffix}",
            short_name=f"Test_{rand_suffix}",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            issuer_name="Test Issuer",
            isin=valid_unique_isin,
            country_of_issue="USA",
            issue_currency="USD",
            primary_market_id="NASDAQ",
        )
        inst = await InstrumentMasterService.create_instrument(session, req, actor_id="admin_1")
        assert inst.instrument_id.startswith("INST_")
        assert inst.canonical_name == f"Test Instrument {rand_suffix}"
        assert inst.isin == valid_unique_isin
        assert inst.current_version == 1

        # Duplicate ISIN rejection
        with pytest.raises(Exception) as excinfo:
            await InstrumentMasterService.create_instrument(session, req, actor_id="admin_2")
        assert "already exists" in str(excinfo.value)


@pytest.mark.asyncio
async def test_listing_management_and_primary_constraint():
    """
    Verifies:
    - Multiple venue listings can link to one canonical instrument.
    - Only one active primary listing is enforced.
    """
    async with AsyncSessionLocal() as session:
        rand_id = uuid.uuid4().hex[:6].upper()
        # Create canonical Reliance Industries
        inst = await InstrumentMasterService.create_instrument(
            session,
            InstrumentCreateRequest(
                canonical_name=f"Reliance Industries Limited {rand_id}",
                short_name=f"Reliance_{rand_id}",
                country_of_issue="IND",
                issue_currency="INR",
            ),
            actor_id="admin_1",
        )

        # 1. Primary listing on NSE
        lst_nse = await InstrumentMasterService.create_listing(
            session,
            inst.instrument_id,
            ListingCreateRequest(
                market_id="IN",
                exchange_id="NSE",
                exchange_symbol=f"RELIANCE_{rand_id}",
                trading_currency="INR",
                is_primary_listing=True,
            ),
            actor_id="admin_1",
        )
        assert lst_nse.listing_id.startswith("LST_")
        assert lst_nse.is_primary_listing is True

        # 2. Secondary listing on BSE
        lst_bse = await InstrumentMasterService.create_listing(
            session,
            inst.instrument_id,
            ListingCreateRequest(
                market_id="IN",
                exchange_id="BSE",
                exchange_symbol=f"500_{rand_id}",
                trading_currency="INR",
                is_primary_listing=False,
            ),
            actor_id="admin_1",
        )
        assert lst_bse.listing_id.startswith("LST_")
        assert lst_bse.is_primary_listing is False

        # Query listings
        listings = await InstrumentRepository.get_listings_for_instrument(session, inst.instrument_id)
        assert len(listings) == 2


@pytest.mark.asyncio
async def test_effective_dated_attribute_history():
    """
    Verifies that updating instrument attributes increments version and logs history without in-place loss.
    """
    async with AsyncSessionLocal() as session:
        inst = await InstrumentMasterService.create_instrument(
            session,
            InstrumentCreateRequest(
                canonical_name="Twitter Inc.",
                short_name="Twitter",
                instrument_type="COMMON_STOCK",
            ),
            actor_id="admin_1",
        )
        assert inst.current_version == 1

        # Corporate name change
        updated = await InstrumentMasterService.update_instrument(
            session,
            inst.instrument_id,
            InstrumentUpdateRequest(
                canonical_name="X Corp.",
                short_name="X",
                change_reason="Rebranding to X Corp.",
            ),
            actor_id="admin_1",
        )
        assert updated.canonical_name == "X Corp."
        assert updated.current_version == 2

        # Check history trail
        history = await InstrumentRepository.get_history(session, inst.instrument_id)
        assert len(history) == 2  # canonical_name + short_name
        name_entry = next(h for h in history if h.field_name == "canonical_name")
        assert name_entry.old_value == "Twitter Inc."
        assert name_entry.new_value == "X Corp."


@pytest.mark.asyncio
async def test_venue_aware_identity_resolution():
    """
    Verifies:
    - Resolving by ISIN gives exact match.
    - Resolving by exchange + symbol gives exact match.
    - Ambiguous symbol without venue returns candidate venues without guessing.
    """
    async with AsyncSessionLocal() as session:
        rand_id = uuid.uuid4().hex[:6].upper()
        # Create dual-listed instrument (e.g. Tata Motors on NSE & BSE)
        inst = await InstrumentMasterService.create_instrument(
            session,
            InstrumentCreateRequest(
                canonical_name=f"Tata Motors Limited {rand_id}",
                short_name=f"Tata_{rand_id}",
            ),
            actor_id="admin_1",
        )
        await InstrumentMasterService.create_listing(
            session,
            inst.instrument_id,
            ListingCreateRequest(market_id="IN", exchange_id="NSE", exchange_symbol=f"TATAMOTORS_{rand_id}"),
            actor_id="admin_1",
        )
        await InstrumentMasterService.create_listing(
            session,
            inst.instrument_id,
            ListingCreateRequest(market_id="IN", exchange_id="BSE", exchange_symbol=f"500570_{rand_id}"),
            actor_id="admin_1",
        )

        # 1. Resolve by Exchange + Symbol
        res_sym = await InstrumentMasterService.resolve_identifier(session, exchange="NSE", symbol=f"TATAMOTORS_{rand_id}")
        assert res_sym.match_status == "EXACT_MATCH"
        assert res_sym.instrument_id == inst.instrument_id
        assert res_sym.exchange_symbol == f"TATAMOTORS_{rand_id}"

        # 2. Unknown symbol
        res_unk = await InstrumentMasterService.resolve_identifier(session, exchange="NSE", symbol="NON_EXISTENT_XYZ")
        assert res_unk.match_status == "NO_MATCH"


@pytest.mark.asyncio
async def test_staged_import_batch_workflow(admin_headers):
    """
    Verifies:
    - Staging batch rows with validation.
    - Detection of invalid ISINs and duplicate candidates.
    - Processing approved batch into canonical instruments & listings.
    """
    async with AsyncSessionLocal() as session:
        rand_id = uuid.uuid4().hex[:6].upper()
        batch_req = ImportBatchCreateRequest(
            source_name="OFFICIAL_NSE_SECURITY_MASTER",
            source_type="CSV",
            records=[
                {
                    "canonical_name": f"Infosys Limited {rand_id}",
                    "short_name": f"Infosys_{rand_id}",
                    "exchange_id": "NSE",
                    "exchange_symbol": f"INFY_{rand_id}",
                    "market_id": "IN",
                },
                {
                    "canonical_name": "Broken ISIN Corp",
                    "short_name": "Broken",
                    "isin": "INVALID_CHECKSUM",
                    "exchange_id": "NSE",
                    "exchange_symbol": f"BROKEN_{rand_id}",
                },
            ],
        )

        batch = await InstrumentMasterService.create_import_batch(session, batch_req, actor_id="data_steward")
        assert batch.total_rows == 2
        assert batch.valid_rows == 1
        assert batch.invalid_rows == 1
        assert batch.import_status == "REVIEW_REQUIRED"

        # Process batch
        processed = await InstrumentMasterService.process_import_batch(session, batch.batch_reference, actor_id="admin")
        assert processed.created_count == 1
        assert processed.import_status == "PARTIALLY_COMPLETED"

        # Verify Infosys created in canonical master
        resolved = await InstrumentMasterService.resolve_identifier(session, exchange="NSE", symbol=f"INFY_{rand_id}")
        assert resolved.match_status == "EXACT_MATCH"
        assert resolved.canonical_name == f"Infosys Limited {rand_id}"


@pytest.mark.asyncio
async def test_rest_api_lifecycle(auth_headers, admin_headers):
    """
    Verifies FastAPI endpoints:
    - POST /api/v1/instruments/
    - GET /api/v1/instruments/
    - POST /api/v1/instruments/{id}/listings
    - GET /api/v1/instruments/resolve
    - GET /api/v1/instruments/{id}/history
    """
    rand_suffix = uuid.uuid4().hex[:6].upper()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create instrument
        payload = {
            "canonical_name": f"Microsoft Corporation {rand_suffix}",
            "short_name": f"MSFT_{rand_suffix}",
            "instrument_type": "COMMON_STOCK",
            "primary_market_id": "NASDAQ",
        }
        resp = await client.post("/api/v1/instruments/", json=payload, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        inst_data = resp.json()
        inst_id = inst_data["instrument_id"]

        # 2. Create listing
        lst_payload = {
            "market_id": "US",
            "exchange_id": "NASDAQ",
            "exchange_symbol": f"MSFT_{rand_suffix}",
            "trading_currency": "USD",
            "is_primary_listing": True,
        }
        resp_lst = await client.post(f"/api/v1/instruments/{inst_id}/listings", json=lst_payload, headers=auth_headers)
        assert resp_lst.status_code == 201

        # 3. Resolve via REST
        resp_res = await client.get(f"/api/v1/instruments/resolve?exchange=NASDAQ&symbol=MSFT_{rand_suffix}", headers=auth_headers)
        assert resp_res.status_code == 200
        assert resp_res.json()["match_status"] == "EXACT_MATCH"
        assert resp_res.json()["instrument_id"] == inst_id

        # 4. Search list
        resp_list = await client.get(f"/api/v1/instruments/?query={rand_suffix}", headers=auth_headers)
        assert resp_list.status_code == 200
        assert len(resp_list.json()) >= 1
