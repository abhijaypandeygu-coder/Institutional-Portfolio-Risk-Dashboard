"""
Unit and integration tests for M12.04 Portfolio Alerts.

Tests:
1. Portfolio loss calculations (P&L, positive loss magnitude, NAV-adjusted loss, velocity, attribution residual).
2. Concentration change calculations (percentage-point changes, HHI).
3. Position movement classification (NEW_LONG, INCREASE, REDUCTION, CLOSED, REVERSAL).
4. Cash movement calculations and NAV percentages.
5. Reconciliation break calculations (signed, absolute magnitude, relative percentage).
6. Rule creation and versioning lifecycle.
7. Portfolio loss evaluation with quality rejection.
8. Concentration change evaluation and alert triggering.
9. Position movement evaluation.
10. Cash movement evaluation.
11. Reconciliation break alerting and linking with M05.06 break references.
"""

import pytest
from datetime import datetime
from decimal import Decimal
import uuid
import pytest_asyncio

from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.risk_alerts.portfolio_alerts.calculations.portfolio_alerts_math import (
    calculate_portfolio_loss,
    calculate_loss_velocity,
    calculate_loss_attribution,
    calculate_concentration_changes,
    calculate_hhi,
    classify_position_movement,
    calculate_cash_movement,
    calculate_reconciliation_break_magnitude,
)
from backend.app.modules.risk_alerts.portfolio_alerts.services.portfolio_alerts_service import PortfolioAlertsService
from backend.app.modules.risk_alerts.portfolio_alerts.schemas.portfolio_alerts_schemas import (
    PortfolioAlertRuleCreate,
    PortfolioAlertRuleUpdate,
    PortfolioLossEvaluationRequest,
    ConcentrationEvaluationRequest,
    PositionMovementEvaluationRequest,
    CashMovementEvaluationRequest,
    ReconciliationBreakEvaluationRequest,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield


def test_portfolio_loss_and_velocity_math():
    # Value drops from 10,000,000 to 9,700,000 (Loss of 300,000 or 3.0% NAV)
    curr = Decimal("9700000.00")
    ref = Decimal("10000000.00")
    pnl, pnl_pct, loss_mag, nav_loss_pct = calculate_portfolio_loss(curr, ref, reference_nav=ref)

    assert pnl == Decimal("-300000.00")
    assert pnl_pct == Decimal("-3.0000")
    assert loss_mag == Decimal("300000.00")
    assert nav_loss_pct == Decimal("3.0000")

    # Velocity: 300,000 loss over 15 minutes (900 seconds)
    vel_hr, bps_min = calculate_loss_velocity(pnl, Decimal("0"), delta_seconds=900, reference_nav=ref)
    assert vel_hr == Decimal("-1200000.00")  # -1.2M per hour
    assert bps_min == Decimal("-20.00")  # -20 bps per minute

    # Loss attribution: Instrument A (-200k), Instrument B (-100k)
    inst_pnls = {"EQ_RELIANCE": Decimal("-200000.00"), "EQ_TCS": Decimal("-100000.00")}
    _, contrib_pcts, residual = calculate_loss_attribution(pnl, inst_pnls, reference_nav=ref)
    assert contrib_pcts["EQ_RELIANCE"] == Decimal("-2.0000")
    assert residual == Decimal("0.00")


def test_concentration_and_hhi_math():
    # Weight increases from 12% to 22% (+10 percentage points)
    delta_pp, rel_change = calculate_concentration_changes(Decimal("0.22"), Decimal("0.12"))
    assert delta_pp == Decimal("10.00")
    assert rel_change > Decimal("0.83")

    # HHI for 4 weights: 40%, 30%, 20%, 10%
    weights = [Decimal("0.4"), Decimal("0.3"), Decimal("0.2"), Decimal("0.1")]
    hhi = calculate_hhi(weights)
    # 0.16 + 0.09 + 0.04 + 0.01 = 0.30 -> HHI = 3000
    assert hhi == Decimal("3000.00")


def test_position_movement_classification():
    # New Long
    mtype1, delta1, pct1 = classify_position_movement(Decimal("0"), Decimal("500"))
    assert mtype1 == "NEW_LONG"
    assert delta1 == Decimal("500")

    # Increase
    mtype2, delta2, pct2 = classify_position_movement(Decimal("500"), Decimal("800"))
    assert mtype2 == "INCREASE"
    assert delta2 == Decimal("300")
    assert pct2 == Decimal("60.00")

    # Closed
    mtype3, delta3, pct3 = classify_position_movement(Decimal("800"), Decimal("0"))
    assert mtype3 == "CLOSED"
    assert delta3 == Decimal("-800")

    # Reversal
    mtype4, delta4, pct4 = classify_position_movement(Decimal("200"), Decimal("-100"))
    assert mtype4 == "REVERSAL"
    assert delta4 == Decimal("-300")


def test_cash_and_reconciliation_math():
    # Cash withdrawal: 1,000,000 -> 750,000 (-250,000, 2.5% of 10M NAV)
    delta_cash, pct_nav = calculate_cash_movement(Decimal("750000"), Decimal("1000000"), reference_nav=Decimal("10000000"))
    assert delta_cash == Decimal("-250000")
    assert pct_nav == Decimal("2.50")

    # Reconciliation break: internal 1,000 shares vs external 950 shares (diff = 50)
    signed_b, break_mag, rel_pct = calculate_reconciliation_break_magnitude(Decimal("1000"), Decimal("950"))
    assert signed_b == Decimal("50")
    assert break_mag == Decimal("50")
    assert rel_pct > Decimal("5.0")


@pytest.mark.asyncio
async def test_rule_creation_and_versioning():
    async with AsyncSessionLocal() as session:
        service = PortfolioAlertsService(session)
        code = f"RULE_LOSS_{uuid.uuid4().hex[:6]}"
        req = PortfolioAlertRuleCreate(
            rule_code=code,
            portfolio_id="PORTFOLIO_ALPHA",
            rule_name="Intraday 2.5% NAV Loss",
            category="PORTFOLIO_LOSS",
            event_type="INTRADAY_LOSS",
            metric_name="intraday_loss_pct_nav",
            threshold_value=Decimal("2.5000"),
            threshold_unit="PERCENT_NAV",
        )
        rule = await service.create_rule(req)
        assert rule.id.startswith("PRULE_")
        assert len(rule.versions) == 1
        assert rule.rule_version == 1

        # Update rule version
        update_req = PortfolioAlertRuleUpdate(
            threshold_value=Decimal("2.0000"),
            change_reason="Lowered threshold for risk reduction",
        )
        updated = await service.update_rule(rule.id, update_req)
        assert updated.threshold_value == Decimal("2.0000")
        assert len(updated.versions) == 2
        assert updated.rule_version == 2


@pytest.mark.asyncio
async def test_portfolio_loss_evaluation_and_attribution():
    async with AsyncSessionLocal() as session:
        service = PortfolioAlertsService(session)
        code = f"RULE_LOSS_EVAL_{uuid.uuid4().hex[:6]}"
        await service.create_rule(PortfolioAlertRuleCreate(
            rule_code=code,
            portfolio_id="PORTFOLIO_MAIN",
            rule_name="Portfolio Main Loss Alert",
            category="PORTFOLIO_LOSS",
            event_type="INTRADAY_LOSS",
            metric_name="intraday_loss_pct_nav",
            threshold_value=Decimal("2.0000"),
            threshold_unit="PERCENT_NAV",
        ))

        # 1. Stale valuation should be suppressed
        stale_req = PortfolioLossEvaluationRequest(
            rule_code=code,
            portfolio_id="PORTFOLIO_MAIN",
            current_valuation=Decimal("9700000.00"),
            reference_valuation=Decimal("10000000.00"),
            reference_nav=Decimal("10000000.00"),
            event_timestamp=datetime.utcnow(),
            quality_status="STALE",
        )
        assert (await service.evaluate_portfolio_loss(stale_req)) is None

        # 2. Valid 3% loss with instrument attribution
        valid_req = PortfolioLossEvaluationRequest(
            rule_code=code,
            portfolio_id="PORTFOLIO_MAIN",
            current_valuation=Decimal("9700000.00"),
            reference_valuation=Decimal("10000000.00"),
            reference_nav=Decimal("10000000.00"),
            instrument_pnls={"EQ_RELIANCE": Decimal("-200000.00"), "EQ_TCS": Decimal("-100000.00")},
            event_timestamp=datetime.utcnow(),
            quality_status="VALID",
        )
        event = await service.evaluate_portfolio_loss(valid_req)
        assert event is not None
        assert event.category == "PORTFOLIO_LOSS"
        assert event.event_type == "INTRADAY_LOSS"
        assert len(event.evidence_items) == 2  # loss + attribution


@pytest.mark.asyncio
async def test_concentration_and_position_movement_alerts():
    async with AsyncSessionLocal() as session:
        service = PortfolioAlertsService(session)
        # 1. Concentration Alert
        conc_code = f"RULE_CONC_{uuid.uuid4().hex[:6]}"
        await service.create_rule(PortfolioAlertRuleCreate(
            rule_code=conc_code,
            portfolio_id="PORTFOLIO_MAIN",
            rule_name="Single Instrument Concentration",
            category="CONCENTRATION",
            event_type="INSTRUMENT_CONCENTRATION",
            metric_name="concentration_pp",
            threshold_value=Decimal("8.0000"),  # +8 pp increase
            threshold_unit="PERCENT_POINTS",
        ))
        conc_req = ConcentrationEvaluationRequest(
            rule_code=conc_code,
            portfolio_id="PORTFOLIO_MAIN",
            entity_key="EQ_RELIANCE",
            current_weight=Decimal("0.25"),  # 25%
            baseline_weight=Decimal("0.15"),  # 15% -> +10 pp
            event_timestamp=datetime.utcnow(),
        )
        conc_evt = await service.evaluate_concentration_change(conc_req)
        assert conc_evt is not None
        assert conc_evt.category == "CONCENTRATION"

        # 2. Position Movement Alert
        pos_code = f"RULE_POS_{uuid.uuid4().hex[:6]}"
        await service.create_rule(PortfolioAlertRuleCreate(
            rule_code=pos_code,
            portfolio_id="PORTFOLIO_MAIN",
            rule_name="Large Position Shift",
            category="POSITION_MOVEMENT",
            event_type="INCREASE",
            metric_name="quantity_delta",
            threshold_value=Decimal("5000.0000"),
            threshold_unit="SHARES",
        ))
        pos_req = PositionMovementEvaluationRequest(
            rule_code=pos_code,
            portfolio_id="PORTFOLIO_MAIN",
            instrument_id="EQ_INFY",
            prior_quantity=Decimal("10000"),
            current_quantity=Decimal("18000"),  # +8,000 shares
            event_timestamp=datetime.utcnow(),
        )
        pos_evt = await service.evaluate_position_movement(pos_req)
        assert pos_evt is not None
        assert pos_evt.category == "POSITION_MOVEMENT"
        assert pos_evt.event_type == "INCREASE"


@pytest.mark.asyncio
async def test_cash_and_reconciliation_alerts():
    async with AsyncSessionLocal() as session:
        service = PortfolioAlertsService(session)
        # 1. Cash Movement Alert
        cash_code = f"RULE_CASH_{uuid.uuid4().hex[:6]}"
        await service.create_rule(PortfolioAlertRuleCreate(
            rule_code=cash_code,
            portfolio_id="PORTFOLIO_MAIN",
            rule_name="Material Cash Outflow",
            category="CASH_MOVEMENT",
            event_type="WITHDRAWAL",
            metric_name="cash_delta",
            threshold_value=Decimal("200000.0000"),
            threshold_unit="CURRENCY",
        ))
        cash_req = CashMovementEvaluationRequest(
            rule_code=cash_code,
            portfolio_id="PORTFOLIO_MAIN",
            current_cash=Decimal("700000.00"),
            prior_cash=Decimal("1000000.00"),  # -300k
            movement_type="WITHDRAWAL",
            event_timestamp=datetime.utcnow(),
        )
        cash_evt = await service.evaluate_cash_movement(cash_req)
        assert cash_evt is not None
        assert cash_evt.category == "CASH_MOVEMENT"

        # 2. Reconciliation Break Alert
        rec_code = f"RULE_REC_{uuid.uuid4().hex[:6]}"
        await service.create_rule(PortfolioAlertRuleCreate(
            rule_code=rec_code,
            portfolio_id="PORTFOLIO_MAIN",
            rule_name="Position Reconciliation Break",
            category="RECONCILIATION_BREAK",
            event_type="POSITION_QUANTITY",
            metric_name="break_quantity",
            threshold_value=Decimal("20.0000"),  # > 20 shares
            threshold_unit="SHARES",
        ))
        rec_req = ReconciliationBreakEvaluationRequest(
            rule_code=rec_code,
            portfolio_id="PORTFOLIO_MAIN",
            reconciliation_break_id="BRK_M0506_84920",
            break_category="POSITION_QUANTITY",
            internal_value=Decimal("1500"),
            external_value=Decimal("1450"),  # 50 shares break
            event_timestamp=datetime.utcnow(),
        )
        rec_evt = await service.evaluate_reconciliation_break(rec_req)
        assert rec_evt is not None
        assert rec_evt.category == "RECONCILIATION_BREAK"
        assert len(rec_evt.reconciliation_links) == 1
        assert rec_evt.reconciliation_links[0].reconciliation_break_id == "BRK_M0506_84920"

        # Verify overview metrics
        overview = await service.get_overview(portfolio_id="PORTFOLIO_MAIN")
        assert overview["active_alerts"] >= 2
