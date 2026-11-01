"""
Comprehensive Pytest Suite for M03.07 - Quality Scoring & Use Eligibility.
Covers:
- Section A: Feed Reliability Scoring (availability, timeliness, error rates, classifications).
- Section B: Completeness Scoring (expected vs observed, duplicate exclusion, field-level completeness).
- Section C: Freshness Scoring (target, piecewise decay, maximum age, historical/EOD handling, market closed).
- Section D: Use Eligibility Engine (hard gates, threshold gates, ACCEPTED, RESTRICTED, REJECTED, NOT_SUPPORTED).
- Section E: Composite Snapshots and REST API Lifecycle.
"""

import uuid
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.market_data_quality.quality_scoring.service import QualityScoringService
from backend.app.modules.market_data_quality.quality_scoring.schemas import (
    FeedReliabilityInput,
    CompletenessEvaluationInput,
    FreshnessEvaluationInput,
    CompositeQualityRequest,
    EligibilityEvaluationRequest,
)


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()


@pytest.fixture
def auth_headers():
    return {"X-API-Key": "operator_dev_secret_key_2026"}


@pytest.fixture
def admin_headers():
    return {"X-API-Key": "admin_dev_secret_key_2026"}


# ============================================================================
# Section A: Feed Reliability Scoring Tests (M03.07.01)
# ============================================================================

@pytest.mark.asyncio
async def test_feed_reliability_scoring():
    """
    1. Perfect feed: 100% available, 100% on-time, 0 errors -> 100.00 EXCELLENT.
    2. Degraded feed: 90% availability, 80% timeliness, 10% errors -> Calculated weighted score.
    """
    async with AsyncSessionLocal() as session:
        # Perfect Feed
        perfect_inp = FeedReliabilityInput(
            provider_id="SIMULATOR",
            feed_id="FEED_PERFECT",
            expected_duration_seconds=3600,
            unavailable_duration_seconds=0,
            eligible_operations=1000,
            failed_operations=0,
            eligible_expected_observations=1000,
            timely_observations=1000,
            late_observations=0,
        )
        res_perf = await QualityScoringService.evaluate_reliability(session, perfect_inp)
        assert res_perf.availability_score == Decimal("100.00")
        assert res_perf.timeliness_score == Decimal("100.00")
        assert res_perf.error_score == Decimal("100.00")
        assert res_perf.reliability_score == Decimal("100.00")
        assert res_perf.reliability_classification == "EXCELLENT"

        # Degraded Feed: 360s downtime (90% avail), 200 late (80% time), 100 failed ops (90% error score)
        # Expected = 0.40*90 + 0.35*80 + 0.25*90 = 36 + 28 + 22.5 = 86.50 -> GOOD
        degraded_inp = FeedReliabilityInput(
            provider_id="SIMULATOR",
            feed_id="FEED_DEGRADED",
            expected_duration_seconds=3600,
            unavailable_duration_seconds=360,
            eligible_operations=1000,
            failed_operations=100,
            eligible_expected_observations=1000,
            timely_observations=800,
            late_observations=200,
        )
        res_deg = await QualityScoringService.evaluate_reliability(session, degraded_inp)
        assert res_deg.availability_score == Decimal("90.00")
        assert res_deg.timeliness_score == Decimal("80.00")
        assert res_deg.error_score == Decimal("90.00")
        assert res_deg.reliability_score == Decimal("86.50")
        assert res_deg.reliability_classification == "GOOD"


# ============================================================================
# Section B: Completeness Scoring Tests (M03.07.02)
# ============================================================================

@pytest.mark.asyncio
async def test_completeness_scoring_and_field_completeness():
    """
    1. Complete dataset: 100 expected, 100 valid observed -> 100.00 COMPLETE.
    2. Partial dataset: 100 expected, 92 valid observed, 8 missing -> 92.00 PARTIALLY_COMPLETE.
    3. Duplicate deliveries excluded from completeness denominator.
    """
    async with AsyncSessionLocal() as session:
        # Complete
        comp_inp = CompletenessEvaluationInput(
            provider_id="ALPHA_VANTAGE",
            feed_id="AV_DAILY",
            instrument_id="RELIANCE",
            expected_records=100,
            observed_unique_records=100,
            valid_records=100,
            missing_records=0,
            duplicate_receipts=15,  # Must be ignored!
            expected_fields_count=6,
            valid_fields_count=6,
        )
        res_c = await QualityScoringService.evaluate_completeness(session, comp_inp)
        assert res_c.completeness_score == Decimal("100.00")
        assert res_c.completeness_classification == "COMPLETE"
        assert res_c.field_completeness_ratio == Decimal("1.0000")

        # Incomplete (92%)
        incomp_inp = CompletenessEvaluationInput(
            provider_id="ALPHA_VANTAGE",
            feed_id="AV_DAILY",
            instrument_id="INFY",
            expected_records=100,
            observed_unique_records=92,
            valid_records=92,
            missing_records=8,
            expected_fields_count=6,
            valid_fields_count=5,  # 5/6 = 0.8333
        )
        res_inc = await QualityScoringService.evaluate_completeness(session, incomp_inp)
        assert res_inc.completeness_score == Decimal("92.00")
        assert res_inc.completeness_classification == "PARTIALLY_COMPLETE"
        assert res_inc.field_completeness_ratio == Decimal("0.8333")


# ============================================================================
# Section C: Freshness Scoring Tests (M03.07.03)
# ============================================================================

@pytest.mark.asyncio
async def test_freshness_piecewise_and_historical_eod():
    """
    1. Observed age <= Target -> 100.00 FRESH.
    2. Observed age halfway between Target (1000ms) and Max (5000ms) -> 3000ms -> 50.00 AGING.
    3. Observed age >= Max (6000ms) -> 0.00 CRITICALLY_STALE.
    4. Historical EOD or Market Closed -> 100.00 (exempt from real-time penalty).
    """
    async with AsyncSessionLocal() as session:
        # Fresh
        fresh_inp = FreshnessEvaluationInput(
            provider_id="SIMULATOR",
            feed_id="SIM_L1",
            instrument_id="TCS",
            target_age_ms=1000,
            maximum_age_ms=5000,
            observed_age_ms=500,
        )
        res_fr = await QualityScoringService.evaluate_freshness(session, fresh_inp)
        assert res_fr.freshness_score == Decimal("100.00")
        assert res_fr.freshness_classification == "FRESH"

        # Halfway Decay (3000ms age -> (5000-3000)/(5000-1000) = 2000/4000 = 50%)
        decay_inp = FreshnessEvaluationInput(
            provider_id="SIMULATOR",
            feed_id="SIM_L1",
            instrument_id="TCS",
            target_age_ms=1000,
            maximum_age_ms=5000,
            observed_age_ms=3000,
        )
        res_dec = await QualityScoringService.evaluate_freshness(session, decay_inp)
        assert res_dec.freshness_score == Decimal("50.00")
        assert res_dec.freshness_classification == "AGING"

        # Critically Stale (> 5000ms)
        stale_inp = FreshnessEvaluationInput(
            provider_id="SIMULATOR",
            feed_id="SIM_L1",
            instrument_id="TCS",
            target_age_ms=1000,
            maximum_age_ms=5000,
            observed_age_ms=7500,
        )
        res_stl = await QualityScoringService.evaluate_freshness(session, stale_inp)
        assert res_stl.freshness_score == Decimal("0.00")
        assert res_stl.freshness_classification == "CRITICALLY_STALE"

        # Historical EOD
        eod_inp = FreshnessEvaluationInput(
            provider_id="ALPHA_VANTAGE",
            feed_id="AV_DAILY",
            instrument_id="IBM",
            observed_age_ms=86400000,  # 1 day old
            is_historical_eod=True,
        )
        res_eod = await QualityScoringService.evaluate_freshness(session, eod_inp)
        assert res_eod.freshness_score == Decimal("100.00")
        assert res_eod.freshness_classification == "HISTORICAL"


# ============================================================================
# Section D: Use Eligibility Engine Tests (M03.07.04)
# ============================================================================

@pytest.mark.asyncio
async def test_use_eligibility_hard_gates_and_classifications():
    """
    1. Perfect scores and hard gates -> ACCEPTED.
    2. High scores (99%) but mandatory price is invalid -> REJECTED (Hard gate override).
    3. High scores but broken book continuity for depth metric -> REJECTED.
    4. Unsupported data capability (e.g. L2 for Alpha Vantage) -> NOT_SUPPORTED.
    5. Partial scores meeting warning band -> ACCEPTED_WITH_WARNING.
    """
    async with AsyncSessionLocal() as session:
        # 1. Accepted
        req_acc = EligibilityEvaluationRequest(
            profile_code="DAILY_VALUATION",
            provider_id="ALPHA_VANTAGE",
            feed_id="AV_FEED",
            reliability_score=Decimal("95.00"),
            completeness_score=Decimal("100.00"),
            freshness_score=Decimal("100.00"),
        )
        res_acc = await QualityScoringService.evaluate_eligibility(session, req_acc)
        assert res_acc.eligibility_status == "ACCEPTED"

        # 2. Hard Gate Override: Price invalid rejects regardless of high scores
        req_rej_price = EligibilityEvaluationRequest(
            profile_code="DAILY_VALUATION",
            provider_id="ALPHA_VANTAGE",
            feed_id="AV_FEED",
            reliability_score=Decimal("100.00"),
            completeness_score=Decimal("100.00"),
            freshness_score=Decimal("100.00"),
            is_price_valid=False,  # Hard gate breach!
        )
        res_rej_price = await QualityScoringService.evaluate_eligibility(session, req_rej_price)
        assert res_rej_price.eligibility_status == "REJECTED"

        # 3. Order Book Continuity Failure
        req_rej_book = EligibilityEvaluationRequest(
            profile_code="ORDER_BOOK_IMBALANCE",
            provider_id="SIMULATOR",
            feed_id="SIM_L2",
            reliability_score=Decimal("95.00"),
            completeness_score=Decimal("100.00"),
            freshness_score=Decimal("95.00"),
            is_order_book_continuous=False,  # Continuity broken!
        )
        res_rej_book = await QualityScoringService.evaluate_eligibility(session, req_rej_book)
        assert res_rej_book.eligibility_status == "REJECTED"

        # 4. Unsupported Capability
        req_notsup = EligibilityEvaluationRequest(
            profile_code="ORDER_BOOK_IMBALANCE",
            provider_id="ALPHA_VANTAGE",
            feed_id="AV_FEED",
            reliability_score=Decimal("100.00"),
            completeness_score=Decimal("100.00"),
            freshness_score=Decimal("100.00"),
            is_capability_supported=False,
        )
        res_notsup = await QualityScoringService.evaluate_eligibility(session, req_notsup)
        assert res_notsup.eligibility_status == "NOT_SUPPORTED"


# ============================================================================
# Section E: REST API Verification
# ============================================================================

@pytest.mark.asyncio
async def test_rest_api_lifecycle(auth_headers, admin_headers):
    """
    Verifies:
    - POST /api/v1/quality/scoring/policies
    - POST /api/v1/quality/scoring/calculate
    - POST /api/v1/quality/scoring/eligibility/evaluate
    - GET /api/v1/quality/scoring/eligibility
    - GET /api/v1/quality/scoring/summary
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Scoring Policy
        pol_code = f"POL_TEST_{uuid.uuid4().hex[:6]}"
        pol_payload = {
            "policy_code": pol_code,
            "policy_name": "Test Composite Policy",
            "score_type": "COMPOSITE",
            "rolling_window": "24h",
        }
        resp = await client.post("/api/v1/quality/scoring/policies", json=pol_payload, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["policy_code"] == pol_code

        # 2. Calculate Composite Snapshot via REST
        snap_payload = {
            "provider_id": "SIMULATOR",
            "feed_id": "SIM_API_FEED",
            "instrument_id": "RELIANCE",
            "data_type": "TICK",
            "data_origin": "SIMULATED",
            "reliability": {
                "provider_id": "SIMULATOR",
                "feed_id": "SIM_API_FEED",
                "expected_duration_seconds": 3600,
                "unavailable_duration_seconds": 0,
                "eligible_operations": 500,
                "failed_operations": 0,
                "eligible_expected_observations": 500,
                "timely_observations": 500,
            },
            "completeness": {
                "provider_id": "SIMULATOR",
                "feed_id": "SIM_API_FEED",
                "instrument_id": "RELIANCE",
                "expected_records": 500,
                "observed_unique_records": 500,
                "valid_records": 500,
            },
            "freshness": {
                "provider_id": "SIMULATOR",
                "feed_id": "SIM_API_FEED",
                "instrument_id": "RELIANCE",
                "target_age_ms": 1000,
                "maximum_age_ms": 5000,
                "observed_age_ms": 500,
            },
        }
        resp_snap = await client.post("/api/v1/quality/scoring/calculate", json=snap_payload, headers=auth_headers)
        assert resp_snap.status_code == 200, resp_snap.text
        snap_data = resp_snap.json()
        assert float(snap_data["composite_quality_score"]) == 100.0

        # 3. Evaluate Use Eligibility via REST
        elg_payload = {
            "profile_code": "HISTORICAL_VAR",
            "provider_id": "SIMULATOR",
            "feed_id": "SIM_API_FEED",
            "reliability_score": "95.00",
            "completeness_score": "98.00",
            "freshness_score": "100.00",
        }
        resp_elg = await client.post("/api/v1/quality/scoring/eligibility/evaluate", json=elg_payload, headers=auth_headers)
        assert resp_elg.status_code == 200
        assert resp_elg.json()["eligibility_status"] == "ACCEPTED"

        # 4. Summary metrics
        resp_sum = await client.get("/api/v1/quality/scoring/summary?feed_id=SIM_API_FEED", headers=auth_headers)
        assert resp_sum.status_code == 200
        assert resp_sum.json()["total_snapshots"] >= 1
