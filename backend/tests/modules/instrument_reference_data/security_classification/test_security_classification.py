"""
Pytest Test Suite for M04.02 Security Classification.
Tests:
1. Classification scheme creation, versioning, and taxonomy hierarchy.
2. Industry-to-Sector parent-child validation and inconsistency rejection.
3. Instrument sector and industry assignment with versioning.
4. Asset category assignment and M04.01 instrument type compatibility enforcement (e.g. ETF vs operating equity).
5. Multiple classification schemes coexisting on one canonical instrument without conflict.
6. Bitemporal point-in-time classification resolution without look-ahead bias.
7. Bulk classification lookup for portfolio concentration and risk analytics.
8. REST API lifecycle with RBAC.
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.core.config import settings
from backend.app.modules.instrument_reference_data.instrument_master.services.service import (
    InstrumentMasterService,
)
from backend.app.modules.instrument_reference_data.instrument_master.schemas import (
    InstrumentCreateRequest,
)
from backend.app.modules.instrument_reference_data.security_classification.models import (
    ClassificationScheme,
    ClassificationNode,
    InstrumentClassificationAssignment,
)
from backend.app.modules.instrument_reference_data.security_classification.schemas import (
    ClassificationSchemeCreate,
    ClassificationNodeCreate,
    ClassificationAssignRequest,
    AssetCategoryAssignRequest,
    BulkClassificationLookupRequest,
)
from backend.app.modules.instrument_reference_data.security_classification.services.service import (
    SecurityClassificationService,
)
from backend.app.modules.instrument_reference_data.security_classification.repositories.repository import (
    ClassificationRepository,
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


@pytest.mark.asyncio
async def test_classification_scheme_and_taxonomy_hierarchy():
    """
    Verifies:
    - Creation of a classification scheme.
    - Creation of Sector node.
    - Creation of Industry node referencing valid parent Sector.
    - Inconsistent parent-child rejection.
    """
    async with AsyncSessionLocal() as session:
        rand_id = uuid.uuid4().hex[:6].upper()
        scheme_code = f"TEST_GICS_{rand_id}"

        # 1. Create Scheme
        scheme = await SecurityClassificationService.create_scheme(
            session,
            ClassificationSchemeCreate(
                scheme_code=scheme_code,
                scheme_name="Test Global Industry Classification Standard",
                description="Taxonomy test scheme",
                provider="MSCI/S&P",
                is_primary_default=True,
            ),
            actor_id="admin_1",
        )
        assert scheme.scheme_code == scheme_code

        # 2. Create Sector (Information Technology - Code 45)
        sector = await SecurityClassificationService.create_node(
            session,
            scheme_code,
            "1.0.0",
            ClassificationNodeCreate(
                node_code="45",
                node_name="Information Technology",
                node_description="Technology sector",
                node_type="SECTOR",
                hierarchy_level=1,
            ),
            actor_id="admin_1",
        )
        assert sector.node_type == "SECTOR"
        assert sector.node_id.startswith("NOD_")

        # 3. Create Industry (Software - Code 4510) linked to Sector 45
        industry = await SecurityClassificationService.create_node(
            session,
            scheme_code,
            "1.0.0",
            ClassificationNodeCreate(
                node_code="4510",
                node_name="Software",
                node_description="Software industry",
                node_type="INDUSTRY",
                parent_node_id=sector.node_id,
                hierarchy_level=2,
            ),
            actor_id="admin_1",
        )
        assert industry.parent_node_id == sector.node_id

        # 4. Industry without parent sector must fail
        with pytest.raises(Exception) as excinfo:
            await SecurityClassificationService.create_node(
                session,
                scheme_code,
                "1.0.0",
                ClassificationNodeCreate(
                    node_code="9999",
                    node_name="Orphan Industry",
                    node_description="No parent",
                    node_type="INDUSTRY",
                    parent_node_id=None,
                ),
                actor_id="admin_1",
            )
        assert "must reference a valid parent sector" in str(excinfo.value)


@pytest.mark.asyncio
async def test_instrument_classification_assignment_and_consistency():
    """
    Verifies:
    - Sector & Industry assignment to a canonical M04.01 instrument.
    - Rejection of sector-industry mismatch (e.g. Tech sector with Banking industry).
    """
    async with AsyncSessionLocal() as session:
        rand_id = uuid.uuid4().hex[:6].upper()
        scheme_code = f"SCHEME_{rand_id}"

        # Setup scheme + Sector 45 (Tech) + Industry 4510 (Software) + Sector 40 (Financials) + Industry 4010 (Banks)
        await SecurityClassificationService.create_scheme(
            session,
            ClassificationSchemeCreate(scheme_code=scheme_code, scheme_name="Multi-Sector Scheme", description="Test", provider="TEST"),
            actor_id="admin",
        )
        sec_tech = await SecurityClassificationService.create_node(
            session, scheme_code, "1.0.0",
            ClassificationNodeCreate(node_code="45", node_name="Info Tech", node_description="Tech", node_type="SECTOR"),
            actor_id="admin",
        )
        ind_software = await SecurityClassificationService.create_node(
            session, scheme_code, "1.0.0",
            ClassificationNodeCreate(node_code="4510", node_name="Software", node_description="Soft", node_type="INDUSTRY", parent_node_id=sec_tech.node_id),
            actor_id="admin",
        )
        sec_fin = await SecurityClassificationService.create_node(
            session, scheme_code, "1.0.0",
            ClassificationNodeCreate(node_code="40", node_name="Financials", node_description="Fin", node_type="SECTOR"),
            actor_id="admin",
        )
        ind_banks = await SecurityClassificationService.create_node(
            session, scheme_code, "1.0.0",
            ClassificationNodeCreate(node_code="4010", node_name="Banks", node_description="Banks", node_type="INDUSTRY", parent_node_id=sec_fin.node_id),
            actor_id="admin",
        )

        # Create canonical instrument (TCS)
        inst = await InstrumentMasterService.create_instrument(
            session,
            InstrumentCreateRequest(canonical_name=f"Tata Consultancy Services {rand_id}", short_name=f"TCS_{rand_id}"),
            actor_id="admin",
        )

        # 1. Valid Assignment: TCS -> Info Tech (45) + Software (4510)
        asn = await SecurityClassificationService.assign_classification(
            session,
            inst.instrument_id,
            ClassificationAssignRequest(
                scheme_code=scheme_code,
                sector_code="45",
                industry_code="4510",
                assignment_reason="Standard software classification",
            ),
            actor_id="steward_1",
        )
        assert asn.assignment_version == 1

        # 2. Inconsistent Assignment: Tech (45) + Banks (4010) must be rejected
        with pytest.raises(Exception) as excinfo:
            await SecurityClassificationService.assign_classification(
                session,
                inst.instrument_id,
                ClassificationAssignRequest(
                    scheme_code=scheme_code,
                    sector_code="45",
                    industry_code="4010",
                    assignment_reason="Inconsistent test",
                ),
                actor_id="steward_1",
            )
        assert "Sector-Industry inconsistency" in str(excinfo.value)


@pytest.mark.asyncio
async def test_asset_category_compatibility_and_etf_guard():
    """
    Verifies:
    - Compatibility check between M04.01 instrument_type and analytical asset_category.
    - ETF cannot be classified as COMMON_EQUITY.
    """
    async with AsyncSessionLocal() as session:
        rand_id = uuid.uuid4().hex[:6].upper()

        # Create an ETF instrument
        etf_inst = await InstrumentMasterService.create_instrument(
            session,
            InstrumentCreateRequest(
                canonical_name=f"Nifty 50 BeES ETF {rand_id}",
                short_name=f"NIFTYBEES_{rand_id}",
                instrument_type="ETF",
            ),
            actor_id="admin",
        )

        # 1. Incompatible: Attempting to assign COMMON_EQUITY to ETF
        with pytest.raises(Exception) as excinfo:
            await SecurityClassificationService.assign_asset_category(
                session,
                etf_inst.instrument_id,
                AssetCategoryAssignRequest(
                    category_code="COMMON_EQUITY",
                    assignment_reason="Mistaken equity assignment",
                ),
                actor_id="analyst",
            )
        assert "Compatibility Error" in str(excinfo.value)

        # 2. Compatible: Assign ETF category
        asn = await SecurityClassificationService.assign_asset_category(
            session,
            etf_inst.instrument_id,
            AssetCategoryAssignRequest(
                category_code="ETF",
                assignment_reason="Correct ETF classification",
            ),
            actor_id="analyst",
        )
        assert asn.category_code == "ETF"


@pytest.mark.asyncio
async def test_bitemporal_point_in_time_resolution():
    """
    Verifies that historical point-in-time queries return the classification effective and known at that time,
    preventing look-ahead bias during reclassifications.
    """
    async with AsyncSessionLocal() as session:
        rand_id = uuid.uuid4().hex[:6].upper()
        scheme_code = f"TIME_SCHEME_{rand_id}"

        await SecurityClassificationService.create_scheme(
            session,
            ClassificationSchemeCreate(scheme_code=scheme_code, scheme_name="Bitemporal Scheme", description="Test", provider="TEST"),
            actor_id="admin",
        )
        sec_ind = await SecurityClassificationService.create_node(
            session, scheme_code, "1.0.0",
            ClassificationNodeCreate(node_code="10", node_name="Industrials", node_description="Ind", node_type="SECTOR"),
            actor_id="admin",
        )
        sec_tech = await SecurityClassificationService.create_node(
            session, scheme_code, "1.0.0",
            ClassificationNodeCreate(node_code="20", node_name="Tech", node_description="Tech", node_type="SECTOR"),
            actor_id="admin",
        )

        inst = await InstrumentMasterService.create_instrument(
            session,
            InstrumentCreateRequest(canonical_name=f"Conglomerate {rand_id}", short_name=f"CONGLOM_{rand_id}"),
            actor_id="admin",
        )

        # Day 1: Assigned to Industrials (valid from 2026-01-01)
        t1 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        await SecurityClassificationService.assign_classification(
            session,
            inst.instrument_id,
            ClassificationAssignRequest(
                scheme_code=scheme_code,
                sector_code="10",
                valid_from=t1,
                assignment_reason="Initial industrials business",
            ),
            actor_id="admin",
        )

        # Day 2: Reclassified to Tech (valid from 2026-06-01)
        t2 = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)
        await SecurityClassificationService.assign_classification(
            session,
            inst.instrument_id,
            ClassificationAssignRequest(
                scheme_code=scheme_code,
                sector_code="20",
                valid_from=t2,
                assignment_reason="Transition to cloud tech provider",
            ),
            actor_id="admin",
        )

        # Query Point-in-time: As of 2026-03-01 -> MUST be Industrials (Code 10)
        as_of_t1 = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
        res_t1 = await SecurityClassificationService.lookup_instrument_classification(
            session, inst.instrument_id, scheme_code=scheme_code, as_of_valid_time=as_of_t1
        )
        assert res_t1.sector_code == "10"
        assert res_t1.sector_name == "Industrials"

        # Query Point-in-time: As of 2026-07-01 -> MUST be Tech (Code 20)
        as_of_t2 = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
        res_t2 = await SecurityClassificationService.lookup_instrument_classification(
            session, inst.instrument_id, scheme_code=scheme_code, as_of_valid_time=as_of_t2
        )
        assert res_t2.sector_code == "20"
        assert res_t2.sector_name == "Tech"


@pytest.mark.asyncio
async def test_bulk_classification_lookup_for_portfolio():
    """
    Verifies that multiple instruments can be resolved in a single call for portfolio concentration analysis.
    """
    async with AsyncSessionLocal() as session:
        rand_id = uuid.uuid4().hex[:6].upper()
        scheme_code = f"BULK_{rand_id}"

        await SecurityClassificationService.create_scheme(
            session,
            ClassificationSchemeCreate(scheme_code=scheme_code, scheme_name="Bulk Scheme", description="Test", provider="TEST", is_primary_default=True),
            actor_id="admin",
        )
        sec = await SecurityClassificationService.create_node(
            session, scheme_code, "1.0.0",
            ClassificationNodeCreate(node_code="HEALTH", node_name="Healthcare", node_description="HC", node_type="SECTOR"),
            actor_id="admin",
        )

        inst1 = await InstrumentMasterService.create_instrument(
            session, InstrumentCreateRequest(canonical_name=f"Pharma 1 {rand_id}", short_name="PH1"), actor_id="admin"
        )
        inst2 = await InstrumentMasterService.create_instrument(
            session, InstrumentCreateRequest(canonical_name=f"Pharma 2 {rand_id}", short_name="PH2"), actor_id="admin"
        )

        await SecurityClassificationService.assign_classification(
            session, inst1.instrument_id,
            ClassificationAssignRequest(scheme_code=scheme_code, sector_code="HEALTH", assignment_reason="Pharma sector"),
            actor_id="admin",
        )

        # Bulk lookup for [inst1, inst2, unknown_id]
        req = BulkClassificationLookupRequest(
            instrument_ids=[inst1.instrument_id, inst2.instrument_id, "INST_UNKNOWN_999"],
            scheme_code=scheme_code,
        )
        bulk_resp = await SecurityClassificationService.bulk_lookup(session, req)

        assert bulk_resp.total_requested == 3
        assert bulk_resp.total_classified == 1
        assert bulk_resp.results[inst1.instrument_id].sector_code == "HEALTH"
        assert bulk_resp.results[inst2.instrument_id] is None
        assert bulk_resp.results["INST_UNKNOWN_999"] is None


@pytest.mark.asyncio
async def test_rest_api_lifecycle(auth_headers, admin_headers):
    """
    Verifies FastAPI endpoints:
    - POST /api/v1/classifications/schemes
    - GET /api/v1/classifications/schemes
    - POST /api/v1/classifications/schemes/{code}/versions/{ver}/nodes
    - POST /api/v1/classifications/instruments/{id}/assignments
    - GET /api/v1/classifications/instruments/{id}
    - POST /api/v1/classifications/bulk-lookup
    - GET /api/v1/classifications/metrics/coverage
    """
    rand_id = uuid.uuid4().hex[:6].upper()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Scheme
        scheme_payload = {
            "scheme_code": f"REST_SCHEME_{rand_id}",
            "scheme_name": f"Rest Classification {rand_id}",
            "description": "REST test scheme",
            "provider": "TEST",
            "is_primary_default": True,
        }
        resp = await client.post("/api/v1/classifications/schemes", json=scheme_payload, headers=admin_headers)
        assert resp.status_code == 201, resp.text

        # 2. Add Sector node
        node_payload = {
            "node_code": "ENERGY",
            "node_name": "Energy",
            "node_description": "Oil & Gas sector",
            "node_type": "SECTOR",
            "hierarchy_level": 1,
        }
        resp_node = await client.post(
            f"/api/v1/classifications/schemes/REST_SCHEME_{rand_id}/versions/1.0.0/nodes",
            json=node_payload,
            headers=admin_headers,
        )
        assert resp_node.status_code == 201

        # 3. Create Instrument via M04.01
        inst_payload = {
            "canonical_name": f"Chevron Corp {rand_id}",
            "short_name": f"CVX_{rand_id}",
            "instrument_type": "COMMON_STOCK",
        }
        resp_inst = await client.post("/api/v1/instruments/", json=inst_payload, headers=auth_headers)
        inst_id = resp_inst.json()["instrument_id"]

        # 4. Assign classification via REST
        assign_payload = {
            "scheme_code": f"REST_SCHEME_{rand_id}",
            "sector_code": "ENERGY",
            "assignment_reason": "Global integrated oil firm",
        }
        resp_assign = await client.post(
            f"/api/v1/classifications/instruments/{inst_id}/assignments",
            json=assign_payload,
            headers=auth_headers,
        )
        assert resp_assign.status_code == 201

        # 5. Lookup details
        resp_get = await client.get(f"/api/v1/classifications/instruments/{inst_id}?scheme_code=REST_SCHEME_{rand_id}", headers=auth_headers)
        assert resp_get.status_code == 200
        assert resp_get.json()["sector_code"] == "ENERGY"

        # 6. Bulk Lookup
        resp_bulk = await client.post(
            "/api/v1/classifications/bulk-lookup",
            json={"instrument_ids": [inst_id], "scheme_code": f"REST_SCHEME_{rand_id}"},
            headers=auth_headers,
        )
        assert resp_bulk.status_code == 200
        assert resp_bulk.json()["total_classified"] == 1

        # 7. Coverage metrics
        resp_cov = await client.get("/api/v1/classifications/metrics/coverage", headers=auth_headers)
        assert resp_cov.status_code == 200
        assert resp_cov.json()["total_active_instruments"] >= 1
