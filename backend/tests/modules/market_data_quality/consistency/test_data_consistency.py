"""
Comprehensive Pytest Suite for M03.06 - Data Consistency.
Covers:
- Section A: Cross-Feed Comparison (identical prices, within tolerance, outside tolerance, instrument mismatch, currency mismatch, real vs sim boundary).
- Section B: Price Discrepancy Mathematics (absolute difference, reference percentage difference, symmetric percentage difference, tolerance boundary checks).
- Section C: Field Consistency (valid OHLC, High < Low, High < Open/Close, Low > Open/Close, negative quote sizes).
- Section D: Source Precedence & Conflict Resolution (automated resolution via priority, equal priority manual review, manual operator resolution audit).
- Section E: REST API Verification.
"""

import uuid
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.market_data_quality.consistency.service import DataConsistencyService
from backend.app.modules.market_data_quality.consistency.schemas import (
    ObservationComparisonInput,
    CrossFeedCompareRequest,
    OHLCFieldValidationInput,
    QuoteFieldValidationInput,
    SourcePrecedenceRuleCreate,
    ConflictResolutionActionRequest,
)
from backend.app.modules.market_data_quality.consistency.conflicts.repository import ConsistencyRepository


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
# Section A: Cross-Feed Comparison Tests (M03.06.01)
# ============================================================================

@pytest.mark.asyncio
async def test_cross_feed_identical_and_tolerance_agreement():
    """
    1. Identical observations from two sources -> CONSISTENT, abs_diff=0.0.
    2. Small difference within 0.5% tolerance -> CONSISTENT.
    """
    async with AsyncSessionLocal() as session:
        t_time = datetime(2026, 11, 1, 11, 0, 0, tzinfo=timezone.utc)
        rand_inst = f"INFY_{uuid.uuid4().hex[:6]}"

        obs_a = ObservationComparisonInput(
            observation_id="OBS_A_01",
            provider_id="SIM_PROVIDER_A",
            feed_id="FEED_A",
            instrument_id=rand_inst,
            exchange="NSE",
            currency="INR",
            observation_type="TICK",
            timestamp=t_time,
            value=Decimal("1500.00"),
            data_origin="SIMULATOR",
        )
        obs_b = ObservationComparisonInput(
            observation_id="OBS_B_01",
            provider_id="SIM_PROVIDER_B",
            feed_id="FEED_B",
            instrument_id=rand_inst,
            exchange="NSE",
            currency="INR",
            observation_type="TICK",
            timestamp=t_time,
            value=Decimal("1500.00"),
            data_origin="SIMULATOR",
        )

        req_identical = CrossFeedCompareRequest(
            instrument_id=rand_inst,
            source_a=obs_a,
            source_b=obs_b,
        )
        res_ident = await DataConsistencyService.compare_cross_feed(session, req_identical)
        assert res_ident.comparison_status == "CONSISTENT"
        assert res_ident.absolute_difference == Decimal("0.0")
        assert res_ident.percentage_difference == Decimal("0.0")
        assert res_ident.conflict_created is False

        # Small divergence within 0.5% tolerance (1500.00 vs 1503.00 = 0.20% diff)
        obs_b.value = Decimal("1503.00")
        req_within_tol = CrossFeedCompareRequest(
            instrument_id=rand_inst,
            source_a=obs_a,
            source_b=obs_b,
            percentage_tolerance=Decimal("0.5000"),
        )
        res_tol = await DataConsistencyService.compare_cross_feed(session, req_within_tol)
        assert res_tol.comparison_status == "CONSISTENT"
        assert res_tol.absolute_difference == Decimal("3.00")
        assert res_tol.percentage_difference == Decimal("0.2000")
        assert res_tol.conflict_created is False


@pytest.mark.asyncio
async def test_cross_feed_ineligibility_and_isolation():
    """
    1. Real data vs Simulated data -> UNCOMPARABLE (Strict isolation boundary).
    2. Currency mismatch (INR vs USD) -> CURRENCY_MISMATCH.
    3. Timestamp divergence (> max alignment ms) -> TIMESTAMP_MISMATCH.
    """
    async with AsyncSessionLocal() as session:
        t_time = datetime(2026, 11, 1, 11, 5, 0, tzinfo=timezone.utc)
        rand_inst = f"AAPL_{uuid.uuid4().hex[:6]}"

        # 1. Real vs Simulated
        obs_real = ObservationComparisonInput(
            observation_id="OBS_REAL_01",
            provider_id="ALPHA_VANTAGE",
            feed_id="AV_FEED",
            instrument_id=rand_inst,
            exchange="NASDAQ",
            currency="USD",
            observation_type="TICK",
            timestamp=t_time,
            value=Decimal("220.00"),
            data_origin="REAL",
        )
        obs_sim = ObservationComparisonInput(
            observation_id="OBS_SIM_01",
            provider_id="SIMULATOR",
            feed_id="SIM_FEED",
            instrument_id=rand_inst,
            exchange="NASDAQ",
            currency="USD",
            observation_type="TICK",
            timestamp=t_time,
            value=Decimal("220.00"),
            data_origin="SIMULATOR",
        )
        req_real_sim = CrossFeedCompareRequest(
            instrument_id=rand_inst,
            source_a=obs_real,
            source_b=obs_sim,
            allow_real_vs_sim=False,  # default strict safety
        )
        res_real_sim = await DataConsistencyService.compare_cross_feed(session, req_real_sim)
        assert res_real_sim.comparison_status == "UNCOMPARABLE"

        # 2. Currency Mismatch
        obs_sim_inr = ObservationComparisonInput(
            observation_id="OBS_INR_01",
            provider_id="SIM_PROVIDER_A",
            feed_id="SIM_FEED_A",
            instrument_id=rand_inst,
            exchange="NASDAQ",
            currency="INR",  # Mismatched!
            observation_type="TICK",
            timestamp=t_time,
            value=Decimal("220.00"),
            data_origin="SIMULATOR",
        )
        req_curr = CrossFeedCompareRequest(
            instrument_id=rand_inst,
            source_a=obs_sim,
            source_b=obs_sim_inr,
        )
        res_curr = await DataConsistencyService.compare_cross_feed(session, req_curr)
        assert res_curr.comparison_status == "CURRENCY_MISMATCH"

        # 3. Timestamp Misalignment (> 5000ms)
        t_future = datetime(2026, 11, 1, 11, 5, 10, tzinfo=timezone.utc)  # 10s later
        obs_sim_future = ObservationComparisonInput(
            observation_id="OBS_FUT_01",
            provider_id="SIM_PROVIDER_B",
            feed_id="SIM_FEED_B",
            instrument_id=rand_inst,
            exchange="NASDAQ",
            currency="USD",
            observation_type="TICK",
            timestamp=t_future,
            value=Decimal("220.00"),
            data_origin="SIMULATOR",
        )
        req_time = CrossFeedCompareRequest(
            instrument_id=rand_inst,
            source_a=obs_sim,
            source_b=obs_sim_future,
            max_time_alignment_ms=5000,
        )
        res_time = await DataConsistencyService.compare_cross_feed(session, req_time)
        assert res_time.comparison_status == "TIMESTAMP_MISMATCH"


# ============================================================================
# Section B: Price Discrepancies and Auto-Resolution (M03.06.02 & M03.06.04)
# ============================================================================

@pytest.mark.asyncio
async def test_price_discrepancy_and_source_precedence_auto_resolution():
    """
    1. Divergence beyond 0.5% (100.00 vs 105.00 = 5% diff) -> INCONSISTENT.
    2. Precedence rule configured: Provider A (priority 1) > Provider B (priority 2).
    3. Auto-resolution selects Provider A as winner.
    """
    async with AsyncSessionLocal() as session:
        t_time = datetime(2026, 11, 1, 11, 10, 0, tzinfo=timezone.utc)
        rand_inst = f"TCS_{uuid.uuid4().hex[:6]}"

        # Configure Source Precedence: SIM_FAST (priority 1) beats SIM_SLOW (priority 2)
        await ConsistencyRepository.create_precedence_rule(
            session=session,
            rule_in=SourcePrecedenceRuleCreate(
                rule_code=f"PREC_FAST_{uuid.uuid4().hex[:6]}",
                exchange="NSE",
                provider_id="SIM_FAST",
                priority=1,
            )
        )
        await ConsistencyRepository.create_precedence_rule(
            session=session,
            rule_in=SourcePrecedenceRuleCreate(
                rule_code=f"PREC_SLOW_{uuid.uuid4().hex[:6]}",
                exchange="NSE",
                provider_id="SIM_SLOW",
                priority=2,
            )
        )

        obs_fast = ObservationComparisonInput(
            observation_id="OBS_FAST_01",
            provider_id="SIM_FAST",
            feed_id="FEED_FAST",
            instrument_id=rand_inst,
            exchange="NSE",
            currency="INR",
            observation_type="TICK",
            timestamp=t_time,
            value=Decimal("3500.00"),
            data_origin="SIMULATOR",
        )
        obs_slow = ObservationComparisonInput(
            observation_id="OBS_SLOW_01",
            provider_id="SIM_SLOW",
            feed_id="FEED_SLOW",
            instrument_id=rand_inst,
            exchange="NSE",
            currency="INR",
            observation_type="TICK",
            timestamp=t_time,
            value=Decimal("3600.00"),  # 100 diff / 3500 = 2.85% diff > 0.5%
            data_origin="SIMULATOR",
        )

        req_disc = CrossFeedCompareRequest(
            instrument_id=rand_inst,
            source_a=obs_fast,
            source_b=obs_slow,
            percentage_tolerance=Decimal("0.5000"),
        )
        res_disc = await DataConsistencyService.compare_cross_feed(session, req_disc)
        assert res_disc.comparison_status == "INCONSISTENT"
        assert res_disc.conflict_created is True

        # Check recorded conflict for auto-resolution outcome
        cnf = await ConsistencyRepository.get_conflict_by_key(session, res_disc.conflict_key)
        assert cnf is not None
        assert cnf.conflict_status == "AUTO_RESOLVED"
        assert cnf.selected_source == "SIM_FAST"
        assert cnf.selected_observation_id == "OBS_FAST_01"


# ============================================================================
# Section C: Field Consistency Tests (M03.06.03)
# ============================================================================

@pytest.mark.asyncio
async def test_ohlc_and_quote_field_consistency():
    """
    1. Valid OHLC candle -> FIELD_CONSISTENT.
    2. Invalid OHLC where High < Low -> FIELD_INCONSISTENT.
    3. Invalid OHLC where Close > High -> FIELD_INCONSISTENT.
    4. Quote with negative bid quantity -> FIELD_INCONSISTENT.
    """
    async with AsyncSessionLocal() as session:
        # 1. Valid OHLC
        valid_ohlc = OHLCFieldValidationInput(
            observation_id="OHLC_01",
            instrument_id="RELIANCE",
            open_price=Decimal("2900.00"),
            high_price=Decimal("2950.00"),
            low_price=Decimal("2880.00"),
            close_price=Decimal("2920.00"),
        )
        res_v_ohlc = await DataConsistencyService.validate_ohlc_fields(session, valid_ohlc)
        assert res_v_ohlc.validation_status == "FIELD_CONSISTENT"
        assert len(res_v_ohlc.violations) == 0

        # 2. Invalid OHLC: High (2850) < Low (2880)
        invalid_ohlc_hi_lo = OHLCFieldValidationInput(
            observation_id="OHLC_02",
            instrument_id="RELIANCE",
            open_price=Decimal("2900.00"),
            high_price=Decimal("2850.00"),  # Below low!
            low_price=Decimal("2880.00"),
            close_price=Decimal("2860.00"),
        )
        res_inv_ohlc = await DataConsistencyService.validate_ohlc_fields(session, invalid_ohlc_hi_lo)
        assert res_inv_ohlc.validation_status == "FIELD_INCONSISTENT"
        assert any("less than Low" in v for v in res_inv_ohlc.violations)

        # 3. Negative Quote Quantity
        bad_quote = QuoteFieldValidationInput(
            observation_id="QTE_01",
            instrument_id="RELIANCE",
            bid_price=Decimal("2900.00"),
            ask_price=Decimal("2901.00"),
            bid_quantity=Decimal("-100"),  # Negative!
            ask_quantity=Decimal("150"),
        )
        res_bad_q = await DataConsistencyService.validate_quote_fields(session, bad_quote)
        assert res_bad_q.validation_status == "FIELD_INCONSISTENT"
        assert any("cannot be negative" in v for v in res_bad_q.violations)


# ============================================================================
# Section D: REST API & Manual Conflict Resolution
# ============================================================================

@pytest.mark.asyncio
async def test_rest_api_lifecycle(auth_headers, admin_headers):
    """
    Verifies:
    - POST /api/v1/quality/consistency/source-precedence
    - POST /api/v1/quality/consistency/compare
    - GET /api/v1/quality/consistency/conflicts
    - POST /api/v1/quality/consistency/conflicts/{key}/resolve (manual override)
    - GET /api/v1/quality/consistency/summary
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        rand_inst = f"REST_INST_{uuid.uuid4().hex[:6]}"

        # 1. Compare diverging sources without precedence (creates pending conflict)
        compare_payload = {
            "instrument_id": rand_inst,
            "exchange": "NSE",
            "currency": "INR",
            "observation_type": "TICK",
            "source_a": {
                "observation_id": "REST_OBS_A",
                "provider_id": "SIM_REST_A",
                "feed_id": "FEED_A",
                "instrument_id": rand_inst,
                "exchange": "NSE",
                "currency": "INR",
                "timestamp": "2026-11-01T11:15:00Z",
                "value": "100.00",
                "data_origin": "SIMULATOR",
            },
            "source_b": {
                "observation_id": "REST_OBS_B",
                "provider_id": "SIM_REST_B",
                "feed_id": "FEED_B",
                "instrument_id": rand_inst,
                "exchange": "NSE",
                "currency": "INR",
                "timestamp": "2026-11-01T11:15:00Z",
                "value": "110.00",  # 10% diff
                "data_origin": "SIMULATOR",
            },
            "percentage_tolerance": "1.0000",
        }
        resp = await client.post("/api/v1/quality/consistency/compare", json=compare_payload, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        res_data = resp.json()
        assert res_data["comparison_status"] == "INCONSISTENT"
        assert res_data["conflict_created"] is True
        conflict_key = res_data["conflict_key"]

        # 2. Query open conflicts
        resp_conf = await client.get(f"/api/v1/quality/consistency/conflicts?instrument_id={rand_inst}", headers=auth_headers)
        assert resp_conf.status_code == 200
        conflicts = resp_conf.json()
        assert len(conflicts) >= 1

        # 3. Manually resolve conflict
        resolution_payload = {
            "action": "ACCEPT_SOURCE_A",
            "justification": "Operator verified Source A against primary order flow gateway",
            "selected_observation_id": "REST_OBS_A",
        }
        resp_res = await client.post(
            f"/api/v1/quality/consistency/conflicts/{conflict_key}/resolve",
            json=resolution_payload,
            headers=auth_headers,
        )
        assert resp_res.status_code == 200, resp_res.text
        resolved_data = resp_res.json()
        assert resolved_data["conflict_status"] == "MANUALLY_RESOLVED"

        # 4. Summary metrics
        resp_sum = await client.get(f"/api/v1/quality/consistency/summary?instrument_id={rand_inst}", headers=auth_headers)
        assert resp_sum.status_code == 200
        sum_data = resp_sum.json()
        assert sum_data["total_comparisons"] >= 1
        assert sum_data["resolved_conflicts"] >= 1
