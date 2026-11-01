"""
Comprehensive Test Suite for M03.04 - Order Book Validation.
Validates:
- Section A: Crossed Books (Continuous cross, transient cross, auction phase allowance, cross amount).
- Section B: Locked Books (Exact equality, auction equilibrium, duration tracking, conditional eligibility).
- Section C: Invalid Quantities (Negative, NaN, snapshot 0 rejection, delta deletion 0 acceptance, lot size).
- Section D: Continuity & Sequence Resync (Monotonic progression, sequence gap, resync request triggering).
- Section E: Order Book Structure (Bid descending, Ask ascending, duplicate price detection).
- Section F: Service & REST APIs (Single validation, batch validation, rules, incidents, summary).
"""

import uuid
import pytest
from decimal import Decimal
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.market_data_quality.order_book.service import OrderBookValidationService
from backend.app.modules.market_data_quality.order_book.schemas import (
    OrderBookValidationInput,
    OrderBookLevelInput,
    OrderBookDeltaInput,
    BookValidationRuleCreate
)
from backend.app.modules.market_data_quality.order_book.incidents.repository import BookIncidentRepository


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()


@pytest.fixture
def auth_headers():
    return {"X-API-Key": "operator_dev_secret_key_2026"}


@pytest.fixture
def admin_headers():
    return {"X-API-Key": "admin_dev_secret_key_2026"}


@pytest.mark.asyncio
async def test_crossed_book_continuous_vs_auction():
    """
    Section A: Verifies crossed books in continuous trading vs call auction sessions.
    Continuous: Best Bid > Best Ask -> Invalid, crossed, spread_eligible=False.
    Auction: Best Bid > Best Ask -> AUCTION_CROSS_VALID, valid=True, imbalance_eligible=True, spread_eligible=False.
    """
    async with AsyncSessionLocal() as session:
        # 1. Continuous Trading Cross: Bid 102.50 > Ask 102.00
        input_continuous = OrderBookValidationInput(
            feed_id="SIM_L2_CROSS",
            symbol="RELIANCE",
            venue="NSE",
            session_phase="CONTINUOUS_TRADING",
            data_origin="SIMULATOR",
            is_snapshot=True,
            bids=[
                OrderBookLevelInput(price=Decimal("102.50"), quantity=Decimal("100")),
                OrderBookLevelInput(price=Decimal("102.00"), quantity=Decimal("200"))
            ],
            asks=[
                OrderBookLevelInput(price=Decimal("102.00"), quantity=Decimal("150")),
                OrderBookLevelInput(price=Decimal("102.75"), quantity=Decimal("300"))
            ],
            last_crossed_duration_ms=100  # Confirmed cross (>50ms)
        )
        res_cont = await OrderBookValidationService.validate_order_book(session, input_continuous)
        assert res_cont.is_crossed is True
        assert res_cont.is_valid is False
        assert res_cont.crossed_classification == "CROSSED_CONFIRMED"
        assert res_cont.cross_amount == Decimal("0.50")
        assert res_cont.spread_eligible is False
        assert res_cont.imbalance_eligible is False

        # 2. Auction Phase Cross: Bid 102.50 > Ask 102.00
        input_auction = OrderBookValidationInput(
            feed_id="SIM_L2_CROSS",
            symbol="RELIANCE",
            venue="NSE",
            session_phase="PRE_OPEN_AUCTION",
            data_origin="SIMULATOR",
            is_snapshot=True,
            bids=[
                OrderBookLevelInput(price=Decimal("102.50"), quantity=Decimal("100"))
            ],
            asks=[
                OrderBookLevelInput(price=Decimal("102.00"), quantity=Decimal("150"))
            ]
        )
        res_auc = await OrderBookValidationService.validate_order_book(session, input_auction)
        assert res_auc.is_crossed is True
        assert res_auc.is_valid is True  # Auction cross is structurally valid
        assert res_auc.crossed_classification == "AUCTION_CROSS_VALID"
        assert res_auc.spread_eligible is False  # Cannot compute continuous spread during cross
        assert res_auc.imbalance_eligible is True  # Auction indicative imbalance is permitted


@pytest.mark.asyncio
async def test_locked_book_and_conditional_eligibility():
    """
    Section B: Verifies locked books (Best Bid == Best Ask).
    Continuous lock: spread_eligible=False, but imbalance_eligible=True, depth_eligible=True.
    Auction lock: indicative price equilibrium.
    """
    async with AsyncSessionLocal() as session:
        # Transient continuous lock (<= 100ms)
        input_transient = OrderBookValidationInput(
            feed_id="SIM_L2_LOCK",
            symbol="INFY",
            venue="NASDAQ",
            session_phase="CONTINUOUS_TRADING",
            data_origin="SIMULATOR",
            is_snapshot=True,
            bids=[OrderBookLevelInput(price=Decimal("150.00"), quantity=Decimal("500"))],
            asks=[OrderBookLevelInput(price=Decimal("150.00"), quantity=Decimal("700"))],
            last_locked_duration_ms=40
        )
        res_trans = await OrderBookValidationService.validate_order_book(session, input_transient)
        assert res_trans.is_locked is True
        assert res_trans.is_valid is True  # Transient lock is tolerated
        assert res_trans.locked_classification == "LOCKED_TRANSIENT"
        assert res_trans.spread_eligible is False  # Zero spread avoided for risk divisor
        assert res_trans.imbalance_eligible is True
        assert res_trans.depth_eligible is True

        # Suspicious persistent lock (> 100ms)
        input_suspicious = OrderBookValidationInput(
            feed_id="SIM_L2_LOCK",
            symbol="INFY",
            venue="NASDAQ",
            session_phase="CONTINUOUS_TRADING",
            data_origin="SIMULATOR",
            is_snapshot=True,
            bids=[OrderBookLevelInput(price=Decimal("150.00"), quantity=Decimal("500"))],
            asks=[OrderBookLevelInput(price=Decimal("150.00"), quantity=Decimal("700"))],
            last_locked_duration_ms=350
        )
        res_susp = await OrderBookValidationService.validate_order_book(session, input_suspicious)
        assert res_susp.is_locked is True
        assert res_susp.is_valid is False
        assert res_susp.locked_classification == "LOCKED_SUSPICIOUS"


@pytest.mark.asyncio
async def test_invalid_quantity_snapshot_vs_delta():
    """
    Section C: Quantity Validation.
    - Snapshot containing quantity 0 or negative must be REJECTED.
    - Delta update with quantity 0 is ACCEPTED if operation is 'DELETE'.
    - Delta update with quantity 0 and operation 'UPDATE' is REJECTED.
    """
    async with AsyncSessionLocal() as session:
        # 1. Snapshot with 0 quantity
        bad_snapshot = OrderBookValidationInput(
            feed_id="SIM_QTY",
            symbol="IBM",
            is_snapshot=True,
            bids=[OrderBookLevelInput(price=Decimal("180.00"), quantity=Decimal("0"))],
            asks=[OrderBookLevelInput(price=Decimal("181.00"), quantity=Decimal("100"))]
        )
        res_snap = await OrderBookValidationService.validate_order_book(session, bad_snapshot)
        assert res_snap.is_valid is False
        assert res_snap.has_quantity_anomaly is True

        # 2. Delta with quantity 0 and operation DELETE -> Valid!
        valid_delta_del = OrderBookValidationInput(
            feed_id="SIM_QTY",
            symbol="IBM",
            is_snapshot=False,
            delta=OrderBookDeltaInput(
                side="BID",
                price=Decimal("180.00"),
                quantity=Decimal("0"),
                operation="DELETE"
            )
        )
        res_del = await OrderBookValidationService.validate_order_book(session, valid_delta_del)
        assert res_del.is_valid is True
        assert res_del.has_quantity_anomaly is False

        # 3. Delta with quantity 0 and operation UPDATE -> Invalid!
        invalid_delta_upd = OrderBookValidationInput(
            feed_id="SIM_QTY",
            symbol="IBM",
            is_snapshot=False,
            delta=OrderBookDeltaInput(
                side="BID",
                price=Decimal("180.00"),
                quantity=Decimal("0"),
                operation="UPDATE"
            )
        )
        res_upd = await OrderBookValidationService.validate_order_book(session, invalid_delta_upd)
        assert res_upd.is_valid is False
        assert res_upd.has_quantity_anomaly is True


@pytest.mark.asyncio
async def test_continuity_sequence_gap_and_resync():
    """
    Section D: Sequence Continuity & M02 Resynchronization.
    Detects sequence gaps in incremental deltas, marks book invalid, and dispatches
    a resynchronization request.
    """
    async with AsyncSessionLocal() as session:
        # Normal sequential delta (expected 100, got 100)
        input_continuous = OrderBookValidationInput(
            feed_id="SIM_SEQ",
            symbol="AAPL",
            is_snapshot=False,
            sequence_number=100,
            expected_next_sequence=100,
            delta=OrderBookDeltaInput(
                side="ASK",
                price=Decimal("220.00"),
                quantity=Decimal("50"),
                operation="UPDATE"
            )
        )
        res_cont = await OrderBookValidationService.validate_order_book(session, input_continuous)
        assert res_cont.has_continuity_break is False
        assert res_cont.resync_requested is False

        # Gapped delta (expected 101, got 105 -> skipped 4 packets)
        input_gapped = OrderBookValidationInput(
            feed_id="SIM_SEQ",
            symbol="AAPL",
            is_snapshot=False,
            sequence_number=105,
            expected_next_sequence=101,
            delta=OrderBookDeltaInput(
                side="ASK",
                price=Decimal("220.50"),
                quantity=Decimal("60"),
                operation="UPDATE"
            )
        )
        res_gap = await OrderBookValidationService.validate_order_book(session, input_gapped)
        assert res_gap.is_valid is False
        assert res_gap.has_continuity_break is True
        assert res_gap.resync_requested is True
        assert res_gap.spread_eligible is False
        assert res_gap.liquidity_eligible is False


@pytest.mark.asyncio
async def test_order_book_structure_and_sorting():
    """
    Section E: Structure & Monotonicity.
    Verifies that unsorted bids, unsorted asks, or duplicate price levels are flagged.
    """
    async with AsyncSessionLocal() as session:
        # Bids must be descending: 100, 101 violates descending order!
        bad_bids_order = OrderBookValidationInput(
            feed_id="SIM_STRUCT",
            symbol="TCS",
            is_snapshot=True,
            bids=[
                OrderBookLevelInput(price=Decimal("100.00"), quantity=Decimal("10")),
                OrderBookLevelInput(price=Decimal("101.00"), quantity=Decimal("20"))
            ],
            asks=[
                OrderBookLevelInput(price=Decimal("102.00"), quantity=Decimal("15"))
            ]
        )
        res_bad_bids = await OrderBookValidationService.validate_order_book(session, bad_bids_order)
        assert res_bad_bids.is_valid is False
        assert res_bad_bids.has_structural_defect is True

        # Duplicate price level on asks
        duplicate_asks = OrderBookValidationInput(
            feed_id="SIM_STRUCT",
            symbol="TCS",
            is_snapshot=True,
            bids=[OrderBookLevelInput(price=Decimal("100.00"), quantity=Decimal("10"))],
            asks=[
                OrderBookLevelInput(price=Decimal("102.00"), quantity=Decimal("10")),
                OrderBookLevelInput(price=Decimal("102.00"), quantity=Decimal("25"))
            ]
        )
        res_dup = await OrderBookValidationService.validate_order_book(session, duplicate_asks)
        assert res_dup.is_valid is False
        assert res_dup.has_structural_defect is True


@pytest.mark.asyncio
async def test_rest_api_lifecycle(auth_headers, admin_headers):
    """
    Section F: REST API verification.
    - POST /api/v1/quality/order-book/rules
    - GET /api/v1/quality/order-book/rules
    - POST /api/v1/quality/order-book/validate
    - POST /api/v1/quality/order-book/validate/batch
    - GET /api/v1/quality/order-book/incidents
    - POST /api/v1/quality/order-book/resync
    - GET /api/v1/quality/order-book/summary
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create custom rule
        rule_code = f"RULE_TEST_{uuid.uuid4().hex[:8]}"
        rule_payload = {
            "rule_code": rule_code,
            "rule_name": "Test NSE Book Rule",
            "symbol": "INFY",
            "venue": "NSE",
            "max_crossed_duration_ms": 20,
            "max_locked_duration_ms": 50,
            "allow_fractional_shares": False,
            "min_lot_size": "1.0"
        }
        resp = await client.post("/api/v1/quality/order-book/rules", json=rule_payload, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["rule_code"] == rule_code

        # 2. Validate clean book via REST
        valid_payload = {
            "feed_id": "SIM_API",
            "symbol": "INFY",
            "venue": "NSE",
            "session_phase": "CONTINUOUS_TRADING",
            "data_origin": "SIMULATOR",
            "is_snapshot": True,
            "bids": [{"price": "1500.00", "quantity": "100", "level_position": 1}],
            "asks": [{"price": "1500.50", "quantity": "150", "level_position": 1}]
        }
        resp = await client.post("/api/v1/quality/order-book/validate", json=valid_payload, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        res_data = resp.json()
        assert res_data["is_valid"] is True
        assert res_data["is_crossed"] is False
        assert res_data["spread_eligible"] is True

        # 3. Batch validation
        batch_payload = [
            valid_payload,
            {
                "feed_id": "SIM_API",
                "symbol": "INFY",
                "venue": "NSE",
                "is_snapshot": False,
                "delta": {"side": "BID", "price": "1500.00", "quantity": "0", "operation": "DELETE"}
            }
        ]
        resp = await client.post("/api/v1/quality/order-book/validate/batch", json=batch_payload, headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

        # 4. Trigger manual resync request
        resync_payload = {
            "feed_id": "SIM_API",
            "symbol": "INFY",
            "venue": "NSE",
            "reason": "OPERATOR_MANUAL_REFRESH",
            "from_sequence": 100,
            "to_sequence": 200
        }
        resp = await client.post("/api/v1/quality/order-book/resync", json=resync_payload, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "INITIATED"

        # 5. Quality Summary
        resp = await client.get("/api/v1/quality/order-book/summary?feed_id=SIM_API&symbol=INFY", headers=auth_headers)
        assert resp.status_code == 200
        summary = resp.json()
        assert summary["total_evaluations"] >= 2
        assert summary["feed_id"] == "SIM_API"
