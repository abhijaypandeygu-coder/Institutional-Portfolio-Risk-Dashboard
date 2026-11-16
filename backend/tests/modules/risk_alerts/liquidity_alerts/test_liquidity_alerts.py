"""
Unit and integration tests for M12.03 Liquidity Alerts.

Tests:
1. Spread metrics & robust deviation math (absolute, relative, basis points, MAD, robust Z-score, percentile).
2. Order-book depth deterioration & state machine (decline %, SEVERELY_DETERIORATED, NORMAL, RECOVERING).
3. Liquidity score & liquidation deterioration math.
4. Liquidity rule creation and immutable versioning.
5. End-to-end spread widening evaluation with quality rejection.
6. Order-book depth deterioration evaluation with side-specific portfolio impacts.
7. Composite liquidity score tolerance breach evaluation.
8. Liquidation risk evaluation (cost and horizon thresholds) and analyst review label tracking.
"""

import pytest
from datetime import datetime
from decimal import Decimal
import uuid
import pytest_asyncio

from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.risk_alerts.liquidity_alerts.calculations.liquidity_alerts_math import (
    calculate_spread_metrics,
    calculate_robust_spread_deviation,
    calculate_depth_deterioration,
    evaluate_depth_state,
    calculate_liquidity_score_decline,
    calculate_liquidation_deterioration,
    map_liquidity_side_for_position,
)
from backend.app.modules.risk_alerts.liquidity_alerts.services.liquidity_alerts_service import LiquidityAlertsService
from backend.app.modules.risk_alerts.liquidity_alerts.schemas.liquidity_alerts_schemas import (
    LiquidityAlertRuleCreate,
    LiquidityAlertRuleUpdate,
    SpreadEvaluationRequest,
    DepthEvaluationRequest,
    LiquidityScoreEvaluationRequest,
    LiquidationRiskEvaluationRequest,
    LiquidityReviewLabelCreate,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield


def test_spread_math_and_robust_deviation():
    # Bid 99.80, Ask 100.20 -> Spread 0.40, Mid 100.00 -> 40 bps
    abs_s, rel_s, s_bps, delta_bps, rel_w = calculate_spread_metrics(
        best_bid=Decimal("99.80"),
        best_ask=Decimal("100.20"),
        reference_spread_bps=Decimal("15.00"),
    )
    assert abs_s == Decimal("0.40")
    assert rel_s == Decimal("0.004000")
    assert s_bps == Decimal("40.00")
    assert delta_bps == Decimal("25.00")
    assert rel_w > Decimal("1.6")

    # Robust spread deviation
    historical_bps = [
        Decimal("12.0"), Decimal("14.0"), Decimal("15.0"), Decimal("16.0"),
        Decimal("14.5"), Decimal("15.5"), Decimal("13.0"), Decimal("15.0"),
    ]
    med_s, mad_s, z_robust, pct_s = calculate_robust_spread_deviation(Decimal("40.0"), historical_bps)
    assert med_s is not None
    assert z_robust is not None
    assert z_robust > Decimal("5.0")  # Major outlier
    assert pct_s == Decimal("100.00")


def test_depth_deterioration_and_state_math():
    # 100,000 shares baseline falling to 35,000 shares -> 65% decline
    delta_d, decline_pct = calculate_depth_deterioration(Decimal("35000"), Decimal("100000"))
    assert delta_d == Decimal("-65000")
    assert decline_pct == Decimal("65.00")

    state = evaluate_depth_state(Decimal("35000"), Decimal("100000"), decline_threshold_pct=Decimal("40.0"))
    assert state == "SEVERELY_DETERIORATED"

    # Mild drop to 85,000 shares -> NORMAL
    state_norm = evaluate_depth_state(Decimal("85000"), Decimal("100000"))
    assert state_norm == "NORMAL"


def test_liquidity_score_and_side_mapping():
    # Score drop from 82 to 46
    delta_score, decline_pct = calculate_liquidity_score_decline(Decimal("46.0"), Decimal("82.0"))
    assert delta_score == Decimal("-36.0")
    assert decline_pct > Decimal("43.0")

    # Cost increase from 40 bps to 75 bps
    delta_cost, inc_pct = calculate_liquidation_deterioration(Decimal("75.0"), Decimal("40.0"))
    assert delta_cost == Decimal("35.0")
    assert inc_pct == Decimal("87.50")

    # Liquidity side mapping
    assert map_liquidity_side_for_position("LONG") == "BID"
    assert map_liquidity_side_for_position("SHORT") == "ASK"


@pytest.mark.asyncio
async def test_rule_creation_and_versioning():
    async with AsyncSessionLocal() as session:
        service = LiquidityAlertsService(session)
        code = f"RULE_SPREAD_{uuid.uuid4().hex[:6]}"
        req = LiquidityAlertRuleCreate(
            rule_code=code,
            name="Spread Widening Alert 25 bps",
            rule_type="SPREAD_WIDENING",
            metric_type="SPREAD_BPS",
            market="INDIA",
            exchange="NSE",
            threshold_value=Decimal("25.0000"),
            threshold_unit="BPS",
        )
        rule = await service.create_rule(req)
        assert rule.id.startswith("LQRULE_")
        assert len(rule.versions) == 1
        assert rule.versions[0].version_number == 1

        # Update rule version
        update_req = LiquidityAlertRuleUpdate(
            threshold_value=Decimal("30.0000"),
            change_reason="Increased tolerance to 30 bps",
        )
        updated = await service.update_rule(rule.id, update_req)
        assert updated.threshold_value == Decimal("30.0000")
        assert len(updated.versions) == 2


@pytest.mark.asyncio
async def test_spread_widening_evaluation():
    async with AsyncSessionLocal() as session:
        service = LiquidityAlertsService(session)
        code = f"RULE_SPREAD_TCS_{uuid.uuid4().hex[:6]}"
        await service.create_rule(LiquidityAlertRuleCreate(
            rule_code=code,
            name="TCS Spread Widening",
            rule_type="SPREAD_WIDENING",
            metric_type="SPREAD_BPS",
            market="INDIA",
            exchange="NSE",
            instrument_id="EQ_TCS_NSE",
            threshold_value=Decimal("20.0000"),
            threshold_unit="BPS",
        ))

        # 1. Stale or crossed quotes must be rejected
        stale_req = SpreadEvaluationRequest(
            rule_code=code,
            instrument_id="EQ_TCS_NSE",
            exchange="NSE",
            market="INDIA",
            best_bid=Decimal("3500.00"),
            best_ask=Decimal("3500.00"),  # Locked book
            event_timestamp=datetime.utcnow(),
            quality_state="VALID",
        )
        assert (await service.evaluate_spread_widening(stale_req)) is None

        # 2. Valid widening: Bid 3490.00, Ask 3510.00 -> Spread 20.00, Mid 3500.00 -> 57.14 bps
        valid_req = SpreadEvaluationRequest(
            rule_code=code,
            instrument_id="EQ_TCS_NSE",
            exchange="NSE",
            market="INDIA",
            best_bid=Decimal("3490.00"),
            best_ask=Decimal("3510.00"),
            baseline_spread_bps=Decimal("12.00"),
            historical_spreads_bps=[Decimal("10.0"), Decimal("11.5"), Decimal("12.0"), Decimal("13.0")],
            event_timestamp=datetime.utcnow(),
            quality_state="VALID",
        )
        event = await service.evaluate_spread_widening(valid_req)
        assert event is not None
        assert event.event_type == "SPREAD_WIDENING"
        assert event.metric_type == "SPREAD_BPS"
        assert len(event.evidence_items) >= 1
        assert len(event.portfolio_impacts) >= 1


@pytest.mark.asyncio
async def test_depth_deterioration_and_side_specific_impacts():
    async with AsyncSessionLocal() as session:
        service = LiquidityAlertsService(session)
        code = f"RULE_DEPTH_INFY_{uuid.uuid4().hex[:6]}"
        await service.create_rule(LiquidityAlertRuleCreate(
            rule_code=code,
            name="Infosys Bid Depth Drop",
            rule_type="DEPTH_DETERIORATION",
            metric_type="BID_DEPTH",
            market="INDIA",
            exchange="NSE",
            instrument_id="EQ_INFY_NSE",
            threshold_value=Decimal("40.0000"),
            threshold_unit="PERCENT",
        ))

        # Bid depth dropping from 80,000 to 25,000 (68.75% decline)
        req = DepthEvaluationRequest(
            rule_code=code,
            instrument_id="EQ_INFY_NSE",
            exchange="NSE",
            market="INDIA",
            depth_side="BID",
            current_depth=Decimal("25000"),
            baseline_depth=Decimal("80000"),
            event_timestamp=datetime.utcnow(),
        )
        event = await service.evaluate_depth_deterioration(req)
        assert event is not None
        assert event.event_type == "DEPTH_DETERIORATION"
        assert event.portfolio_impacts[0].affected_liquidity_side == "BID"


@pytest.mark.asyncio
async def test_score_and_liquidation_risk_alerts():
    async with AsyncSessionLocal() as session:
        service = LiquidityAlertsService(session)
        # 1. Composite Score Alert
        score_code = f"RULE_SCORE_{uuid.uuid4().hex[:6]}"
        await service.create_rule(LiquidityAlertRuleCreate(
            rule_code=score_code,
            name="Low Liquidity Score",
            rule_type="LIQUIDITY_SCORE",
            metric_type="COMPOSITE_SCORE",
            market="INDIA",
            instrument_id="EQ_HDFC_NSE",
            threshold_value=Decimal("50.0000"),
            threshold_unit="SCORE",
        ))
        score_req = LiquidityScoreEvaluationRequest(
            rule_code=score_code,
            instrument_id="EQ_HDFC_NSE",
            exchange="NSE",
            market="INDIA",
            current_score=Decimal("42.0"),
            baseline_score=Decimal("78.0"),
            methodology_version="M09.03_v1",
            components_json={"spread_comp": "40.0", "depth_comp": "35.0"},
            event_timestamp=datetime.utcnow(),
        )
        score_evt = await service.evaluate_liquidity_score(score_req)
        assert score_evt is not None
        assert score_evt.event_type == "LOW_LIQUIDITY_SCORE"

        # 2. Liquidation Horizon Alert
        horizon_code = f"RULE_HORIZON_{uuid.uuid4().hex[:6]}"
        await service.create_rule(LiquidityAlertRuleCreate(
            rule_code=horizon_code,
            name="Excess Liquidation Horizon",
            rule_type="LIQUIDATION_HORIZON",
            metric_type="LIQUIDATION_TIME_MINUTES",
            market="INDIA",
            instrument_id="EQ_HDFC_NSE",
            threshold_value=Decimal("120.0000"),  # Max 120 minutes
            threshold_unit="MINUTES",
        ))
        horizon_req = LiquidationRiskEvaluationRequest(
            rule_code=horizon_code,
            instrument_id="EQ_HDFC_NSE",
            exchange="NSE",
            market="INDIA",
            position_direction="LONG",
            position_quantity=Decimal("50000.0"),
            estimated_liquidation_horizon_minutes=Decimal("180.0"),  # 3 hours
            baseline_horizon_minutes=Decimal("60.0"),
            event_timestamp=datetime.utcnow(),
        )
        horizon_evt = await service.evaluate_liquidation_risk(horizon_req)
        assert horizon_evt is not None
        assert horizon_evt.event_type == "EXCESS_LIQUIDATION_HORIZON"

        # Add analyst review label
        review = await service.add_review_label(
            event_id=horizon_evt.id,
            req=LiquidityReviewLabelCreate(
                review_label="VALID_LIQUIDITY_DETERIORATION",
                review_comment="Confirmed sudden volume depletion during block trade",
                reviewed_by="HEAD_OF_EXECUTION",
            ),
        )
        assert review is not None
        assert review.review_label == "VALID_LIQUIDITY_DETERIORATION"

        # Verify overview metrics
        overview = await service.get_overview(market="INDIA")
        assert overview["active_liquidity_alerts_count"] >= 2

