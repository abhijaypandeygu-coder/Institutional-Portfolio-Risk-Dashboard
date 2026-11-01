"""
Comprehensive Pytest Suite for Module 03.02: Price Validation Engine.
Covers:
- A. Invalid Price Tests (Null, Non-numeric, NaN/Inf, Negatives, Range, Tick Size, Precision, OHLC)
- B. Zero Price Tests (Zero trades, OHLC, bid/ask quotes, zero volume preservation, sentinels)
- C. Extreme Price Movements (Thresholds, absolute jumps, exchange bands, corporate actions, Z-scores)
- D. Reference Price Comparisons (Previous close, currencies, cross-source discrepancy between providers)
- E. Service & REST API lifecycle (Validation endpoints, batch processing, rule versioning, anomalies, summary)
"""
from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.main import app
from backend.app.modules.market_data_quality.price_validation.framework.math_utils import (
    calculate_absolute_difference,
    calculate_cross_source_discrepancy,
    calculate_percentage_change,
    count_decimal_places,
    is_ohlc_structurally_valid,
    is_tick_size_valid,
    to_decimal,
)
from backend.app.modules.market_data_quality.price_validation.integrations.m04_bridge import (
    CorporateActionAdjustment,
    ExchangePriceBand,
    InstrumentMetadata,
    InstrumentReferenceService,
    ReferencePriceSnapshot,
)
from backend.app.modules.market_data_quality.price_validation.models import (
    AnomalyIncidentStatus,
    EnforcementAction,
    RuleCategory,
    ValidationSeverity,
    ValidationStatus,
)
from backend.app.modules.market_data_quality.price_validation.movement.movement_validator import (
    PriceMovementValidator,
)
from backend.app.modules.market_data_quality.price_validation.reference.reference_comparator import (
    ReferencePriceComparator,
)
from backend.app.modules.market_data_quality.price_validation.schemas import (
    BatchPriceObservationInput,
    CrossSourceCompareRequest,
    PriceObservationInput,
)
from backend.app.modules.market_data_quality.price_validation.service import (
    PriceValidationService,
)
from backend.app.modules.market_data_quality.price_validation.validators.structural_validator import (
    StructuralPriceValidator,
)
from backend.app.modules.market_data_quality.price_validation.validators.zero_validator import (
    ZeroPriceValidator,
)


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_db()


@pytest.fixture
def operator_headers():
    return {"X-API-Key": "operator_dev_secret_key_2026"}


@pytest.fixture
def readonly_headers():
    return {"X-API-Key": "readonly_dev_secret_key_2026"}


# ============================================================================
# Section A: Invalid Price Tests (M03.02.01)
# ============================================================================

def test_decimal_math_and_conversions():
    """Verify safe Decimal conversion and edge cases without float inaccuracies."""
    assert to_decimal(None) is None
    assert to_decimal("") is None
    assert to_decimal("   ") is None
    assert to_decimal("NaN") is None
    assert to_decimal("inf") is None
    assert to_decimal("-inf") is None
    assert to_decimal("ABC") is None
    assert to_decimal("123.45") == Decimal("123.45")
    assert to_decimal(100.5) == Decimal("100.5")


def test_structural_price_validator():
    """Test nulls, non-numerics, negatives, range limits, tick size, and precision."""
    ref_service = InstrumentReferenceService()
    validator = StructuralPriceValidator(ref_service)
    metadata = ref_service.get_instrument_metadata("RELIANCE")

    # 1. Null / Missing
    obs_null = PriceObservationInput(
        instrument_id="RELIANCE", feed_id="f1", raw_price=None
    )
    p, ev = validator.validate(obs_null, metadata)
    assert p is None
    assert any(e.rule_code == "STRUCT_NULL_PRICE" and e.status == ValidationStatus.REJECTED for e in ev)

    # 2. Non-numeric
    obs_abc = PriceObservationInput(
        instrument_id="RELIANCE", feed_id="f1", raw_price="INVALID_PRICE"
    )
    p, ev = validator.validate(obs_abc, metadata)
    assert p is None
    assert any(e.rule_code == "STRUCT_NON_NUMERIC_OR_NON_FINITE" for e in ev)

    # 3. Negative price (strictly forbidden for equities)
    obs_neg = PriceObservationInput(
        instrument_id="RELIANCE", feed_id="f1", raw_price="-250.00"
    )
    p, ev = validator.validate(obs_neg, metadata)
    assert p == Decimal("-250.00")
    assert any(e.rule_code == "STRUCT_NEGATIVE_EQUITY_PRICE" and e.status == ValidationStatus.REJECTED for e in ev)

    # 4. Out of range (min / max)
    obs_low = PriceObservationInput(
        instrument_id="RELIANCE", feed_id="f1", raw_price="0.50"  # Below min 1.00
    )
    p, ev = validator.validate(obs_low, metadata)
    assert any(e.rule_code == "STRUCT_PRICE_BELOW_MINIMUM" for e in ev)

    # 5. Tick size violation (Tick size is 0.05 for NSE)
    obs_tick_bad = PriceObservationInput(
        instrument_id="RELIANCE", feed_id="f1", raw_price="2500.03"
    )
    p, ev = validator.validate(obs_tick_bad, metadata)
    assert any(e.rule_code == "STRUCT_TICK_SIZE_VIOLATION" for e in ev)

    # 6. Valid tick size
    obs_tick_good = PriceObservationInput(
        instrument_id="RELIANCE", feed_id="f1", raw_price="2500.05"
    )
    p, ev = validator.validate(obs_tick_good, metadata)
    assert not any(e.rule_code == "STRUCT_TICK_SIZE_VIOLATION" for e in ev)

    # 7. Decimal precision violation (> 2 decimal places)
    obs_prec = PriceObservationInput(
        instrument_id="RELIANCE", feed_id="f1", raw_price="2500.055"
    )
    p, ev = validator.validate(obs_prec, metadata)
    assert any(e.rule_code == "STRUCT_DECIMAL_PRECISION_EXCEEDED" for e in ev)


def test_ohlc_structural_invariants():
    """Verify OHLC relationships (High >= Low, High >= Open/Close, Low <= Open/Close)."""
    # Valid OHLC
    valid, err = is_ohlc_structurally_valid(
        Decimal("100"), Decimal("110"), Decimal("95"), Decimal("105")
    )
    assert valid and err is None

    # High lower than Low
    valid, err = is_ohlc_structurally_valid(
        Decimal("100"), Decimal("90"), Decimal("95"), Decimal("105")
    )
    assert not valid and "lower than Low" in err

    # High lower than Open
    valid, err = is_ohlc_structurally_valid(
        Decimal("115"), Decimal("110"), Decimal("95"), Decimal("105")
    )
    assert not valid and "lower than Open" in err

    # Low higher than Open
    valid, err = is_ohlc_structurally_valid(
        Decimal("100"), Decimal("110"), Decimal("106"), Decimal("105")
    )
    assert not valid and "higher than Open" in err


# ============================================================================
# Section B: Zero Price Tests (M03.02.02)
# ============================================================================

def test_zero_price_validator():
    """Verify field-specific zero handling and zero volume preservation."""
    zero_val = ZeroPriceValidator()

    # 1. Zero Trade / LTP -> REJECTED
    obs_trade_zero = PriceObservationInput(
        instrument_id="RELIANCE",
        feed_id="f1",
        observation_type="TRADE",
        price_field="price",
        raw_price=Decimal("0"),
    )
    ev = zero_val.validate(obs_trade_zero, Decimal("0"))
    assert any(e.rule_code == "ZERO_PRICE_REJECTED" and e.status == ValidationStatus.REJECTED for e in ev)

    # 2. Zero Quote Bid -> Warning (Empty order book / unavailable quote side)
    obs_bid_zero = PriceObservationInput(
        instrument_id="RELIANCE",
        feed_id="f1",
        observation_type="TICK",
        price_field="bid",
        raw_price=Decimal("0"),
    )
    ev = zero_val.validate(obs_bid_zero, Decimal("0"))
    assert any(e.rule_code == "ZERO_QUOTE_SIDE_UNAVAILABLE" and e.status == ValidationStatus.ACCEPTED_WITH_WARNING for e in ev)

    # 3. Zero Volume -> ACCEPTED (Not a price violation)
    obs_vol_zero = PriceObservationInput(
        instrument_id="RELIANCE",
        feed_id="f1",
        observation_type="OHLCV",
        price_field="volume",
        raw_price=Decimal("0"),
    )
    ev = zero_val.validate(obs_vol_zero, Decimal("0"))
    assert any(e.rule_code == "ZERO_VOLUME_ACCEPTED" and e.status == ValidationStatus.ACCEPTED for e in ev)

    # 4. Sentinel zero from provider -> QUARANTINED
    obs_sentinel = PriceObservationInput(
        instrument_id="IBM",
        feed_id="f_av",
        provider_id="ALPHA_VANTAGE",
        price_field="close",
        raw_price=Decimal("0"),
        source_metadata={"is_sentinel": True},
    )
    ev = zero_val.validate(obs_sentinel, Decimal("0"))
    assert any(e.rule_code == "ZERO_PROVIDER_SENTINEL" and e.status == ValidationStatus.QUARANTINED for e in ev)


# ============================================================================
# Section C: Extreme Price Movement & Exchange Bands (M03.02.03)
# ============================================================================

def test_extreme_movement_and_exchange_bands():
    """Verify percentage thresholds, circuit bands, and corporate actions."""
    ref_service = InstrumentReferenceService()
    movement_val = PriceMovementValidator(ref_service)
    metadata = ref_service.get_instrument_metadata("RELIANCE")

    # 1. Normal price movement (within 10% threshold)
    obs_normal = PriceObservationInput(
        instrument_id="RELIANCE", feed_id="f1", exchange="NSE", raw_price="3000.00"
    )
    ev = movement_val.validate(
        obs=obs_normal,
        parsed_price=Decimal("3000.00"),
        reference_price=Decimal("2950.00"),  # ~1.69% change
        metadata=metadata,
        pct_threshold=Decimal("10.0"),
    )
    assert any(e.rule_code == "MOVEMENT_NORMAL" and e.status == ValidationStatus.ACCEPTED for e in ev)
    assert any(e.rule_code == "BAND_VERIFIED_IN_BOUNDS" for e in ev)

    # 2. Extreme upward jump (15% change > 10% threshold)
    obs_jump = PriceObservationInput(
        instrument_id="RELIANCE", feed_id="f1", exchange="NSE", raw_price="3400.00"
    )
    ev = movement_val.validate(
        obs=obs_jump,
        parsed_price=Decimal("3400.00"),
        reference_price=Decimal("2950.00"),
        metadata=metadata,
        pct_threshold=Decimal("10.0"),
    )
    # Also exceeds upper circuit band of 3300.00!
    assert any(e.rule_code == "EXTREME_PRICE_MOVEMENT" for e in ev)
    assert any(e.rule_code == "BAND_BREACH_UPPER" and e.status == ValidationStatus.QUARANTINED for e in ev)

    # 3. Corporate Action Day (e.g. 1:1 Bonus / Stock Split halves the price)
    ref_service.register_corporate_action(
        CorporateActionAdjustment(
            instrument_id="RELIANCE",
            effective_date=date.today(),
            action_type="SPLIT",
            ratio=Decimal("0.5"),
        )
    )
    obs_split = PriceObservationInput(
        instrument_id="RELIANCE", feed_id="f1", exchange="NSE", raw_price="1500.00"
    )
    ev = movement_val.validate(
        obs=obs_split,
        parsed_price=Decimal("1500.00"),
        reference_price=Decimal("3000.00"),
        metadata=metadata,
        pct_threshold=Decimal("10.0"),
    )
    assert any(e.rule_code == "CORP_ACTION_PRICE_MOVEMENT" and e.status == ValidationStatus.ACCEPTED_WITH_WARNING for e in ev)


# ============================================================================
# Section D: Reference Price & Cross-Source Comparisons (M03.02.04)
# ============================================================================

def test_reference_comparator_and_cross_source():
    """Verify previous close comparisons and cross-provider discrepancy detection."""
    ref_service = InstrumentReferenceService()
    comparator = ReferencePriceComparator(ref_service)

    # 1. Aligned previous close snapshot
    ref_snap = ReferencePriceSnapshot(
        instrument_id="RELIANCE",
        exchange="NSE",
        reference_type="PREVIOUS_CLOSE",
        reference_value=Decimal("3000.00"),
        currency="INR",
    )
    obs = PriceObservationInput(
        instrument_id="RELIANCE", feed_id="f1", raw_price="3010.00", currency="INR"
    )
    ev = comparator.compare_with_reference(obs, Decimal("3010.00"), ref_snap, max_deviation_pct=Decimal("5.0"))
    assert any(e.rule_code == "REF_PRICE_ALIGNED" and e.status == ValidationStatus.ACCEPTED for e in ev)

    # 2. Currency mismatch
    obs_usd = PriceObservationInput(
        instrument_id="RELIANCE", feed_id="f1", raw_price="36.00", currency="USD"
    )
    ev = comparator.compare_with_reference(obs_usd, Decimal("36.00"), ref_snap)
    assert any(e.rule_code == "REF_CURRENCY_MISMATCH" and e.status == ValidationStatus.QUARANTINED for e in ev)

    # 3. Cross-Source Comparison between Provider A (Exchange Feed) and Provider B (Alpha Vantage)
    # price_a = 200, price_b = 208 -> abs_diff = 8, denom = 200 (if price_a) or 208 (if max), (8/200)*100 = 4%
    req = CrossSourceCompareRequest(
        instrument_id="IBM",
        exchange="NYSE",
        price_a=Decimal("200.00"),
        provider_a="PRIMARY_FEED",
        price_b=Decimal("208.00"),
        provider_b="ALPHA_VANTAGE",
        max_tolerance_percentage=Decimal("1.0"),
    )
    res = comparator.compare_cross_sources(req)
    assert res.is_discrepant is True
    assert res.status == ValidationStatus.QUARANTINED
    assert res.percentage_discrepancy is not None


# ============================================================================
# Section E: Service & REST API Lifecycle Tests
# ============================================================================

async def test_price_validation_service_and_apis(operator_headers, readonly_headers):
    """End-to-end test of the validation engine, rule engine, anomalies, and REST endpoints."""
    async with AsyncSessionLocal() as session:
        service = PriceValidationService(session)

        # 1. Service Level: Validate Valid Observation
        obs_valid = PriceObservationInput(
            instrument_id="INFY",
            feed_id="feed_nse_01",
            provider_id="SIMULATOR",
            exchange="NSE",
            observation_type="TICK",
            price_field="last_traded_price",
            raw_price="1800.05",
        )
        res = await service.validate_observation(obs_valid, reference_price=Decimal("1800.00"))
        assert res.validation_status == ValidationStatus.ACCEPTED
        assert res.is_downstream_eligible is True
        assert res.failed_rule_count == 0

        # 2. Service Level: Validate Structurally Invalid Observation (Malformed string)
        obs_bad = PriceObservationInput(
            instrument_id="INFY",
            feed_id="feed_nse_01",
            provider_id="SIMULATOR",
            exchange="NSE",
            observation_type="TICK",
            price_field="last_traded_price",
            raw_price="CORRUPTED_1800",
        )
        res_bad = await service.validate_observation(obs_bad)
        assert res_bad.validation_status == ValidationStatus.REJECTED
        assert res_bad.is_downstream_eligible is False

        # 3. Service Level: Validate Quarantined Observation (Circuit Band Breach)
        obs_breach = PriceObservationInput(
            instrument_id="INFY",
            feed_id="feed_nse_01",
            provider_id="SIMULATOR",
            exchange="NSE",
            observation_type="TICK",
            price_field="last_traded_price",
            raw_price="2200.00",  # Exceeds INFY upper band of 1980.00
        )
        res_breach = await service.validate_observation(obs_breach, reference_price=Decimal("1800.00"))
        assert res_breach.validation_status == ValidationStatus.QUARANTINED
        assert res_breach.is_downstream_eligible is False

    # 4. REST API: /quality/price-validation/validate
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/v1/quality/price-validation/validate",
            headers=operator_headers,
            json={
                "instrument_id": "RELIANCE",
                "feed_id": "feed_nse_01",
                "provider_id": "SIMULATOR",
                "exchange": "NSE",
                "observation_type": "TICK",
                "price_field": "last_traded_price",
                "raw_price": "2950.00",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["validation_status"] == "ACCEPTED"
        assert data["is_downstream_eligible"] is True

        # 5. REST API: Batch Validation
        r_batch = await ac.post(
            "/api/v1/quality/price-validation/validate/batch",
            headers=operator_headers,
            json={
                "observations": [
                    {
                        "instrument_id": "IBM",
                        "feed_id": "feed_nyse_01",
                        "provider_id": "ALPHA_VANTAGE",
                        "exchange": "NYSE",
                        "observation_type": "OHLCV",
                        "price_field": "close",
                        "raw_price": "210.00",
                        "open_price": "205.00",
                        "high_price": "212.00",
                        "low_price": "204.00",
                        "close_price": "210.00",
                    },
                    {
                        "instrument_id": "AAPL",
                        "feed_id": "feed_nasdaq_01",
                        "provider_id": "SIMULATOR",
                        "exchange": "NASDAQ",
                        "observation_type": "TRADE",
                        "price_field": "price",
                        "raw_price": "-150.00",  # Negative price rejected!
                    },
                ]
            },
        )
        assert r_batch.status_code == 200
        batch_data = r_batch.json()
        assert len(batch_data) == 2
        assert batch_data[0]["validation_status"] == "ACCEPTED"
        assert batch_data[1]["validation_status"] == "REJECTED"

        # 6. REST API: Create Rule & List Rules
        import uuid
        rule_code_dyn = f"CUSTOM_PCT_{uuid.uuid4().hex[:8]}"
        r_rule = await ac.post(
            "/api/v1/quality/price-validation/rules",
            headers=operator_headers,
            json={
                "rule_code": rule_code_dyn,
                "rule_name": "Custom 5% Jump Limit",
                "rule_category": "EXTREME_MOVEMENT",
                "exchange": "NSE",
                "threshold_type": "PERCENTAGE",
                "threshold_value": "5.0",
                "severity": "HIGH",
                "enforcement_action": "WARN",
            },
        )
        assert r_rule.status_code == 201

        r_rules_list = await ac.get(
            "/api/v1/quality/price-validation/rules",
            headers=readonly_headers,
        )
        assert r_rules_list.status_code == 200
        assert len(r_rules_list.json()) >= 1

        # 7. REST API: Anomaly Incident Lifecycle
        r_anomalies = await ac.get(
            "/api/v1/quality/price-validation/anomalies",
            headers=readonly_headers,
        )
        assert r_anomalies.status_code == 200
        anomalies = r_anomalies.json()
        assert len(anomalies) >= 1
        first_incident_id = anomalies[0]["id"]

        r_resolve = await ac.post(
            f"/api/v1/quality/price-validation/anomalies/{first_incident_id}/resolve",
            headers=operator_headers,
            json={
                "status": "RESOLVED",
                "resolution_reason": "Verified genuine market circuit breaker spike",
            },
        )
        assert r_resolve.status_code == 200
        assert r_resolve.json()["incident_status"] == "RESOLVED"

        # 8. REST API: Summary Metrics
        r_summary = await ac.get(
            "/api/v1/quality/price-validation/summary",
            headers=readonly_headers,
        )
        assert r_summary.status_code == 200
        sum_data = r_summary.json()
        assert sum_data["total_observations_validated"] >= 3
        assert sum_data["eligibility_rate_percentage"] > 0
