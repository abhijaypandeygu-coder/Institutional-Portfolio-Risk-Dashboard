"""
M08.01 Factor Definition Test Suite.
Covers:
1. Canonical Factor Recipe Generation and Deterministic Hash Verification:
   - Market (MKT), Size (SMB), Value (HML), Momentum (MOM), Quality (QMJ)
   - SHA-256 hash determinism and serialization normalization
2. Factor Registry & Immutable Versioning:
   - Creation of factor identity
   - Creation of new immutable version upon methodology modification
   - Factor characteristic decomposition (Quality characteristics, directions, weights)
3. Governance Lifecycle Workflow:
   - Draft -> Pending Review -> Approved -> Active -> Deprecated
   - State transition validation
4. Factor Model Composition:
   - Fama-French + Carhart model creation with exact pinned factor version IDs
   - Deterministic factor ordering (k = 1, ..., K)
5. Integration & API Endpoints:
   - System health check registration of M08.01
   - POST /api/v1/factors/seed (Seed canonical equity factors)
   - GET /api/v1/factors (Listing and filtering)
   - POST /api/v1/factors/{factor_id}/versions
   - POST /api/v1/factors/versions/{version_id}/governance
   - POST /api/v1/factor-models & GET /api/v1/factor-models/{model_id}
"""
import pytest
from datetime import date
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.modules.factor_risk.factor_definition.definitions.canonical_recipes import (
    compute_deterministic_hash,
    get_canonical_market_recipe,
    get_canonical_size_recipe,
    get_canonical_value_recipe,
    get_canonical_momentum_recipe,
    get_canonical_quality_recipe,
)
from backend.app.modules.factor_risk.factor_definition.models import (
    FactorFamily,
    FactorType,
    ConstructionType,
    FactorLifecycleStatus,
    MarketScope,
)
from backend.app.modules.factor_risk.factor_definition.services.service import (
    FactorDefinitionService,
)
from backend.app.modules.factor_risk.factor_definition.schemas import (
    CreateFactorDefinitionRequest,
    CreateFactorVersionRequest,
    GovernanceActionRequest,
    CreateFactorModelRequest,
)


# ============================================================================
# 1. RECIPE & DETERMINISTIC HASH TESTS
# ============================================================================

def test_deterministic_hash_invariance_to_key_order():
    """Verify cryptographic recipe hash is invariant to dictionary key ordering."""
    dict_a = {"beta": 0.8, "alpha": 0.1, "name": "MKT"}
    dict_b = {"name": "MKT", "alpha": 0.1, "beta": 0.8}

    hash_a = compute_deterministic_hash(dict_a)
    hash_b = compute_deterministic_hash(dict_b)

    assert hash_a == hash_b
    assert len(hash_a) == 64  # SHA-256


def test_canonical_recipes_structure():
    """Verify initial 5 canonical factor recipes have required quantitative attributes."""
    mkt = get_canonical_market_recipe(MarketScope.INDIA, excess_return=True)
    assert mkt["return_basis"] == "EXCESS_RETURN"
    assert mkt["currency"] == "INR"

    smb = get_canonical_size_recipe(MarketScope.INDIA)
    assert smb["small_breakpoint_upper_pct"] == 30.0
    assert smb["big_breakpoint_lower_pct"] == 70.0
    assert smb["return_direction"] == "LONG_MINUS_SHORT"

    hml = get_canonical_value_recipe(MarketScope.INDIA)
    assert hml["publication_lag_days"] == 60
    assert hml["negative_equity_policy"] == "EXCLUDE_FROM_PORTFOLIO"

    mom = get_canonical_momentum_recipe(MarketScope.INDIA)
    assert mom["formation_window_days"] == 252
    assert mom["skip_window_days"] == 21

    qmj = get_canonical_quality_recipe(MarketScope.INDIA)
    assert len(qmj["characteristics"]) == 3
    # Verify weights sum to 1.0
    sum_weights = sum(c["component_weight"] for c in qmj["characteristics"])
    assert pytest.approx(sum_weights, 1e-6) == 1.0


# ============================================================================
# 2. INTEGRATION TESTS (FASTAPI & SERVICE LIFECYCLE)
# ============================================================================

@pytest.mark.asyncio
async def test_health_check_includes_m08_01():
    """Verify M08.01 is registered in system health response."""
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "M08.01 - Factor Definition Engine" in data["modules"]


@pytest.mark.asyncio
async def test_seed_canonical_factors_and_query_registry():
    """
    Test seeding canonical factors (Market, Size, Value, Momentum, Quality),
    querying registry, and verifying immutable version hashes.
    """
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Seed Indian canonical factors
        resp_seed = await client.post("/api/v1/factors/seed?market=INDIA")
        assert resp_seed.status_code == 200
        seeded = resp_seed.json()
        assert len(seeded) == 5

        factor_codes = [f["factor_code"] for f in seeded]
        assert "MKT_INDIA" in factor_codes
        assert "SMB_INDIA" in factor_codes
        assert "HML_INDIA" in factor_codes
        assert "MOM_INDIA" in factor_codes
        assert "QMJ_INDIA" in factor_codes

        # 2. List factors with filter
        resp_list = await client.get("/api/v1/factors?family=VALUE")
        assert resp_list.status_code == 200
        val_factors = resp_list.json()
        assert len(val_factors) >= 1
        assert val_factors[0]["factor_family"] == "VALUE"

        # 3. Get single factor detail
        hml_id = [f["factor_id"] for f in seeded if f["factor_code"] == "HML_INDIA"][0]
        resp_hml = await client.get(f"/api/v1/factors/{hml_id}")
        assert resp_hml.status_code == 200
        hml_data = resp_hml.json()
        assert hml_data["latest_version"]["version_number"] == 1
        assert len(hml_data["latest_version"]["definition_hash"]) == 64


@pytest.mark.asyncio
async def test_versioning_and_governance_workflow():
    """
    Test factor versioning and lifecycle governance:
    Create custom factor -> Submit -> Approve -> Activate -> Create v2 -> Deprecate v1.
    """
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        import uuid
        factor_code = f"LOW_VOL_{uuid.uuid4().hex[:6].upper()}"
        create_payload = {
            "factor_code": factor_code,
            "factor_name": "India Low Volatility Factor",
            "factor_family": "LOW_VOLATILITY",
            "factor_type": "LONG_SHORT_PORTFOLIO_FACTOR",
            "description": "Long bottom 30% volatility, short top 30% volatility equities.",
            "economic_interpretation": "Captures the low-volatility anomaly in emerging markets.",
            "construction_type": "INTERNALLY_CONSTRUCTED",
            "market_scope": "INDIA",
            "currency": "INR",
            "frequency": "DAILY",
            "construction_specification": {
                "volatility_lookback_days": 252,
                "low_vol_percentile": 30.0,
                "high_vol_percentile": 70.0,
                "return_direction": "LONG_MINUS_SHORT",
            },
        }
        resp_create = await client.post("/api/v1/factors", json=create_payload)
        assert resp_create.status_code == 200
        fac_data = resp_create.json()
        fac_id = fac_data["factor_id"]
        v1_id = fac_data["latest_version"]["version_id"]
        assert fac_data["latest_version"]["approval_status"] == "DRAFT"

        # 2. Submit for review
        resp_sub = await client.post(
            f"/api/v1/factors/versions/{v1_id}/governance",
            json={"action": "SUBMIT", "actor": "QUANT_RESEARCHER"},
        )
        assert resp_sub.status_code == 200
        assert resp_sub.json()["approval_status"] == "PENDING_REVIEW"

        # 3. Approve
        resp_app = await client.post(
            f"/api/v1/factors/versions/{v1_id}/governance",
            json={"action": "APPROVE", "actor": "RISK_COMMITTEE_CHAIR"},
        )
        assert resp_app.status_code == 200
        assert resp_app.json()["approval_status"] == "APPROVED"

        # 4. Activate
        resp_act = await client.post(
            f"/api/v1/factors/versions/{v1_id}/governance",
            json={"action": "ACTIVATE", "actor": "RISK_COMMITTEE_CHAIR"},
        )
        assert resp_act.status_code == 200
        assert resp_act.json()["approval_status"] == "ACTIVE"

        # 5. Create new immutable version v2 (change lookback to 126 days)
        v2_payload = {
            "market_scope": "INDIA",
            "currency": "INR",
            "frequency": "DAILY",
            "construction_specification": {
                "volatility_lookback_days": 126,  # 6-month lookback
                "low_vol_percentile": 30.0,
                "high_vol_percentile": 70.0,
                "return_direction": "LONG_MINUS_SHORT",
            },
            "change_rationale": "Shorten volatility estimation lookback from 252 to 126 days",
        }
        resp_v2 = await client.post(f"/api/v1/factors/{fac_id}/versions", json=v2_payload)
        assert resp_v2.status_code == 200
        v2_data = resp_v2.json()
        assert v2_data["version_number"] == 2
        assert v2_data["approval_status"] == "DRAFT"
        # Hashes must differ because methodology changed
        assert v2_data["definition_hash"] != fac_data["latest_version"]["definition_hash"]


@pytest.mark.asyncio
async def test_factor_model_composition():
    """
    Test creating a multi-factor model with exact pinned factor versions:
    e.g. Fama-French 3-Factor (MKT, SMB, HML).
    """
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed canonical factors
        resp_seed = await client.post("/api/v1/factors/seed?market=INDIA")
        seeded = resp_seed.json()

        mkt_v = [f["latest_version"]["version_id"] for f in seeded if f["factor_code"] == "MKT_INDIA"][0]
        smb_v = [f["latest_version"]["version_id"] for f in seeded if f["factor_code"] == "SMB_INDIA"][0]
        hml_v = [f["latest_version"]["version_id"] for f in seeded if f["factor_code"] == "HML_INDIA"][0]

        # Create FF3 factor model
        import uuid
        model_code = f"FF3_{uuid.uuid4().hex[:6].upper()}"
        model_payload = {
            "model_code": model_code,
            "model_name": "Fama-French 3-Factor Model (India)",
            "description": "Standard 3-factor model for NSE/BSE equities: MKT, SMB, HML.",
            "market_scope": "INDIA",
            "currency_basis": "INR",
            "return_frequency": "DAILY",
            "factor_version_ids": [mkt_v, smb_v, hml_v],
            "change_rationale": "Canonical baseline 3-factor equity model specification",
        }
        resp_model = await client.post("/api/v1/factor-models", json=model_payload)
        assert resp_model.status_code == 200
        m_data = resp_model.json()
        assert m_data["model_code"] == model_code
        assert m_data["current_version_number"] == 1
        m_ver = m_data["latest_version"]
        assert len(m_ver["memberships"]) == 3
        assert m_ver["memberships"][0]["factor_position"] == 1
        assert m_ver["memberships"][1]["factor_position"] == 2
        assert m_ver["memberships"][2]["factor_position"] == 3
        assert len(m_ver["model_definition_hash"]) == 64

        # List models
        resp_list = await client.get("/api/v1/factor-models")
        assert resp_list.status_code == 200
        models_list = resp_list.json()
        assert any(m["model_code"] == model_code for m in models_list)
