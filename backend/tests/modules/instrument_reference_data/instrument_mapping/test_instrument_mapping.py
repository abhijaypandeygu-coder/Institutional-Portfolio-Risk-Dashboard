"""Tests for M04.07 - Instrument Mapping."""
import uuid
from datetime import date
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.instrument_reference_data.instrument_master.services.service import InstrumentMasterService
from backend.app.modules.instrument_reference_data.instrument_master.schemas import InstrumentCreateRequest
from backend.app.modules.instrument_reference_data.instrument_mapping.normalization.normalizer import (
    normalize_identifier,
)
from backend.app.modules.instrument_reference_data.instrument_mapping.models import (
    NamespaceType,
    MappingStatus,
    VerificationStatus,
    ResolutionMatchingLevel,
)


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
                canonical_name=f"Mapping Test Asset {rand_id}",
                short_name=f"TEST_MAP_{rand_id}",
                instrument_type="COMMON_STOCK",
                asset_class="EQUITY",
                issue_currency="USD",
            ),
            actor_id="admin",
        )
        return inst


@pytest.mark.asyncio
async def test_identifier_normalization():
    """Verify namespace-specific normalization rules."""
    # General ticker uppercase & trimming with default settings
    assert normalize_identifier("  aapl  ", case_sensitive=False) == "AAPL"
    
    # Preserve leading zeros for security codes (e.g. Hong Kong 0005, Japan 7203)
    assert normalize_identifier("0005", case_sensitive=False) == "0005"
    assert normalize_identifier("  0700  ", case_sensitive=False) == "0700"

    # ISIN uppercase and trim
    assert normalize_identifier("  us0378331005  ", case_sensitive=False) == "US0378331005"

    # Vendor symbol suffix stripping
    assert normalize_identifier("AAPL.US", case_sensitive=False, strip_exchange_suffix=True) == "AAPL"
    assert normalize_identifier("RELIANCE.NS", case_sensitive=False, strip_exchange_suffix=True) == "RELIANCE"
    assert normalize_identifier("7203.T", case_sensitive=False, strip_exchange_suffix=True) == "7203"


@pytest.mark.asyncio
async def test_instrument_mapping_crud_and_resolution(sample_instrument):
    """Test full workflow: create instrument, namespace, mapping, resolution, and ambiguity."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rand_id = uuid.uuid4().hex[:6].upper()
        instrument_id = sample_instrument.instrument_id

        # 1. Register Namespace
        ns_code = f"BLOOMBERG_{rand_id}"
        ns_payload = {
            "namespace_code": ns_code,
            "namespace_name": "Bloomberg Ticker Namespace",
            "namespace_type": "VENDOR_SYMBOL",
            "provider_name": "BLOOMBERG",
            "case_sensitive": False,
            "strip_suffix": True,
        }
        res_ns = await client.post("/api/v1/instrument-mappings/namespaces", json=ns_payload)
        assert res_ns.status_code == 201
        ns_data = res_ns.json()
        assert ns_data["namespace_code"] == ns_code

        # 2. Register Mapping
        map_payload = {
            "mapping_id": f"MAP_{rand_id}_1",
            "namespace_code": ns_code,
            "external_identifier_raw": "AAPL.US",
            "target_type": "LISTING_LEVEL",
            "instrument_id": instrument_id,
            "listing_id": f"LIST_{rand_id}",
            "exchange_code": "XNAS",
            "mapping_status": "APPROVED_FOR_INGESTION",
            "effective_from": "2020-01-01",
            "source_reference": "BLOOMBERG_FEED",
        }
        res_map = await client.post("/api/v1/instrument-mappings/", json=map_payload)
        assert res_map.status_code == 201
        map_data = res_map.json()
        assert map_data["external_identifier_normalized"] == "AAPL"
        assert map_data["mapping_id"] == f"MAP_{rand_id}_1"

        # 3. Resolve Single Identifier
        resolve_payload = {
            "namespace_code": ns_code,
            "raw_identifier": "aapl.us",
            "as_of_date": "2024-01-15",
            "exchange_code": "XNAS",
        }
        res_resolve = await client.post("/api/v1/instrument-mappings/resolve", json=resolve_payload)
        assert res_resolve.status_code == 200
        resolution = res_resolve.json()
        assert resolution["instrument_id"] == instrument_id
        assert resolution["listing_id"] == f"LIST_{rand_id}"
        assert resolution["matching_level"] == "EXACT_VERIFIED_MATCH"
        assert resolution["is_eligible_for_ingestion"] is True

        # 4. Bulk Resolution
        bulk_payload = {
            "requests": [
                {
                    "namespace_code": ns_code,
                    "raw_identifier": "AAPL.US",
                    "exchange_code": "XNAS",
                },
                {
                    "namespace_code": ns_code,
                    "raw_identifier": "UNKNOWN_TICKER",
                },
            ]
        }
        res_bulk = await client.post("/api/v1/instrument-mappings/resolve/bulk", json=bulk_payload)
        assert res_bulk.status_code == 200
        bulk_data = res_bulk.json()
        assert bulk_data["total_requested"] == 2
        assert bulk_data["resolved_count"] == 1
        assert bulk_data["unresolved_count"] == 1
        assert bulk_data["results"][0]["instrument_id"] == instrument_id
        assert bulk_data["results"][1]["instrument_id"] is None

        # 5. Ambiguity Resolution & Conflict Logging
        # Create second instrument directly via service
        async with AsyncSessionLocal() as session:
            inst2 = await InstrumentMasterService.create_instrument(
                session,
                InstrumentCreateRequest(
                    canonical_name=f"Apple London {rand_id}",
                    short_name=f"AAPL_L_{rand_id}",
                    instrument_type="COMMON_STOCK",
                    asset_class="EQUITY",
                    issue_currency="GBP",
                ),
                actor_id="admin",
            )
            instrument_id_2 = inst2.instrument_id

        ns_shared = f"GENERIC_{rand_id}"
        await client.post(
            "/api/v1/instrument-mappings/namespaces",
            json={
                "namespace_code": ns_shared,
                "namespace_name": "Generic Namespace",
                "namespace_type": "EXCHANGE_SYMBOL",
                "case_sensitive": False,
                "strip_suffix": False,
            },
        )

        # Register two mappings for the same symbol "SHARED"
        await client.post(
            "/api/v1/instrument-mappings/",
            json={
                "mapping_id": f"MAP_{rand_id}_S1",
                "namespace_code": ns_shared,
                "external_identifier_raw": "SHARED",
                "target_type": "INSTRUMENT_LEVEL",
                "instrument_id": instrument_id,
                "effective_from": "2020-01-01",
            },
        )
        await client.post(
            "/api/v1/instrument-mappings/",
            json={
                "mapping_id": f"MAP_{rand_id}_S2",
                "namespace_code": ns_shared,
                "external_identifier_raw": "SHARED",
                "target_type": "INSTRUMENT_LEVEL",
                "instrument_id": instrument_id_2,
                "effective_from": "2020-01-01",
            },
        )

        # Resolve SHARED without exchange filter -> AMBIGUOUS_MATCH
        res_ambig = await client.post(
            "/api/v1/instrument-mappings/resolve",
            json={
                "namespace_code": ns_shared,
                "raw_identifier": "SHARED",
            },
        )
        assert res_ambig.status_code == 200
        ambig_data = res_ambig.json()
        assert ambig_data["matching_level"] == "AMBIGUOUS_MATCH"
        assert ambig_data["is_eligible_for_ingestion"] is False
        assert len(ambig_data["candidate_instrument_ids"]) == 2
        assert "Ambiguous mapping" in ambig_data["reason"]
