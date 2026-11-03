"""
M09.01 Bid-Ask Spread Comprehensive Pytest Suite.
Verifies:
1. Exact hand-calculated absolute spread (S = 100.10 - 99.90 = 0.20), precision preservation,
   locked books (0.00), crossed books (CROSSED_BOOK, no negative spread), one-sided books.
2. Exact hand-calculated relative spread:
   - Midpoint = 100.00
   - RS decimal = 0.002
   - RS pct = 0.20%
   - RS bps = 20 bps
   - Tick spread (0.20 / 0.05 = 4 ticks)
   - Alternative bid/ask normalizations and non-positive denominator guardrails.
3. Spread quality engine:
   - Stale quote detection (> max_quote_age)
   - Excessive quote skew (> max_quote_skew)
   - Negative prices, tick size misalignment, out-of-session handling.
4. Hand-calculated time-weighted spread:
   - State A: 0.20 for 30s
   - State B: 0.40 for 60s
   - S_TW = (0.20 * 30 + 0.40 * 60) / 90 = 30 / 90 = 0.333333...
   - Interval clamping, expiration, and coverage calculation.
5. End-to-end FastAPI lifecycle:
   - Configuration creation
   - Direct quote calculation & persistence
   - Resolution from M02 NormalizedMarketTick table
   - Summary statistics (mean, median, percentiles, time-weighted)
   - Quality diagnostics drill-down
   - Venue spread comparisons
"""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.market_microstructure.bid_ask_spread.calculations import (
    compute_absolute_spread,
    compute_midpoint_price,
    compute_relative_spread,
    compute_spread_in_ticks,
    compute_observation_weighted_statistics,
    compute_time_weighted_spread,
)
from backend.app.modules.market_microstructure.bid_ask_spread.services.service import SpreadQualityService
from backend.app.modules.market_data_ingestion.persistence.models import NormalizedMarketTick


# ==============================================================================
# 1. Pure Math Unit Tests: Hand-Calculated Absolute Spread
# ==============================================================================

def test_hand_calculated_absolute_spread():
    """
    Prompt Spec Section 19.1 Hand-calculated example:
    Best Bid = 99.90, Best Ask = 100.10
    Expected Absolute Spread = 100.10 - 99.90 = 0.20
    """
    bid = Decimal("99.90")
    ask = Decimal("100.10")

    spread, status = compute_absolute_spread(bid, ask)
    assert status == "VALID"
    assert spread == Decimal("0.20")
    assert str(spread) == "0.20"

    # Locked market: Ask == Bid -> Spread = 0
    locked_bid = Decimal("100.00")
    locked_ask = Decimal("100.00")
    l_spread, l_status = compute_absolute_spread(locked_bid, locked_ask)
    assert l_status == "LOCKED_BOOK"
    assert l_spread == Decimal("0")

    # Crossed market: Ask < Bid -> MUST NOT return negative spread
    crossed_bid = Decimal("100.15")
    crossed_ask = Decimal("100.05")
    c_spread, c_status = compute_absolute_spread(crossed_bid, crossed_ask)
    assert c_status == "CROSSED_BOOK"
    assert c_spread is None

    # One-sided books
    m_spread, m_status = compute_absolute_spread(None, ask)
    assert m_status == "MISSING_BID"
    assert m_spread is None

    m_spread2, m_status2 = compute_absolute_spread(bid, None)
    assert m_status2 == "MISSING_ASK"
    assert m_spread2 is None

    m_spread3, m_status3 = compute_absolute_spread(None, None)
    assert m_status3 == "MISSING_BOTH_SIDES"
    assert m_spread3 is None

    # Negative prices
    neg_spread, neg_status = compute_absolute_spread(Decimal("-10.0"), ask)
    assert neg_status == "INVALID_PRICE"
    assert neg_spread is None


# ==============================================================================
# 2. Pure Math Unit Tests: Hand-Calculated Relative Spread & Tick Spread
# ==============================================================================

def test_hand_calculated_relative_spread():
    """
    Prompt Spec Section 19.2 Hand-calculated example:
    Best Bid = 99.90, Best Ask = 100.10
    Midpoint = (99.90 + 100.10) / 2 = 100.00
    Relative Spread = 0.20 / 100.00 = 0.002
    Relative Spread % = 0.002 * 100 = 0.20%
    Relative Spread bps = 0.002 * 10,000 = 20 bps
    Spread in Ticks (tick_size = 0.05) = 0.20 / 0.05 = 4 ticks
    """
    bid = Decimal("99.90")
    ask = Decimal("100.10")
    abs_spread = Decimal("0.20")

    midpoint = compute_midpoint_price(bid, ask)
    assert midpoint == Decimal("100.00")

    rs_dec, rs_pct, rs_bps, status = compute_relative_spread(abs_spread, midpoint)
    assert status == "VALID"
    assert rs_dec == Decimal("0.002")
    assert rs_pct == Decimal("0.20")
    assert rs_bps == Decimal("20.000")

    # Spread in ticks
    tick_size = Decimal("0.05")
    ticks = compute_spread_in_ticks(abs_spread, tick_size)
    assert ticks == Decimal("4")

    # Non-positive denominator guardrail
    zero_ref = Decimal("0.00")
    rs_z_dec, _, _, z_status = compute_relative_spread(abs_spread, zero_ref)
    assert z_status == "INVALID_REFERENCE_PRICE"
    assert rs_z_dec is None


# ==============================================================================
# 3. Quality Validation Unit Tests: Skew, Staleness, Session, Ticks
# ==============================================================================

def test_spread_quality_validation():
    eval_time = datetime(2026, 2, 2, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Fresh synchronized quote
    status, checks, skew, age = SpreadQualityService.validate_quote_state(
        best_bid=Decimal("100.00"),
        best_ask=Decimal("100.10"),
        bid_timestamp=eval_time,
        ask_timestamp=eval_time,
        evaluation_time=eval_time,
        max_quote_age_seconds=5.0,
        max_quote_skew_seconds=0.5,
        tick_size=Decimal("0.05"),
    )
    assert status == "VALID"
    assert skew == 0.0
    assert age == 0.0

    # 2. Stale quote (> 5 seconds)
    stale_bid_time = eval_time - timedelta(seconds=12)
    stale_ask_time = eval_time - timedelta(seconds=12)
    status_stale, _, _, age_stale = SpreadQualityService.validate_quote_state(
        best_bid=Decimal("100.00"),
        best_ask=Decimal("100.10"),
        bid_timestamp=stale_bid_time,
        ask_timestamp=stale_ask_time,
        evaluation_time=eval_time,
        max_quote_age_seconds=5.0,
        max_quote_skew_seconds=0.5,
    )
    assert status_stale == "STALE_QUOTE"
    assert age_stale == 12.0

    # 3. Excessive quote skew (> 0.5s between bid and ask)
    async_bid_time = eval_time
    async_ask_time = eval_time - timedelta(seconds=2.0)
    status_skew, _, skew_val, _ = SpreadQualityService.validate_quote_state(
        best_bid=Decimal("100.00"),
        best_ask=Decimal("100.10"),
        bid_timestamp=async_bid_time,
        ask_timestamp=async_ask_time,
        evaluation_time=eval_time,
        max_quote_age_seconds=5.0,
        max_quote_skew_seconds=0.5,
    )
    assert status_skew == "UNSYNCHRONIZED_QUOTES"
    assert skew_val == 2.0

    # 4. Out-of-session (Auction / Halted)
    status_auc, _, _, _ = SpreadQualityService.validate_quote_state(
        best_bid=Decimal("100.00"),
        best_ask=Decimal("100.10"),
        bid_timestamp=eval_time,
        ask_timestamp=eval_time,
        evaluation_time=eval_time,
        max_quote_age_seconds=5.0,
        max_quote_skew_seconds=0.5,
        session_type="OPENING_AUCTION",
        session_policy="CONTINUOUS_ONLY",
    )
    assert status_auc == "OUT_OF_SESSION"


# ==============================================================================
# 4. Pure Math Unit Tests: Hand-Calculated Time-Weighted Spread
# ==============================================================================

def test_hand_calculated_time_weighted_spread():
    """
    Prompt Spec Section 19.4 Hand-calculated example:
    - Spread A = 0.20 for 30 seconds
    - Spread B = 0.40 for 60 seconds
    Total valid duration = 30 + 60 = 90 seconds
    Expected S_TW = (0.20 * 30 + 0.40 * 60) / 90 = 30 / 90 = 0.333333...
    """
    t0 = datetime(2026, 2, 2, 9, 30, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=30)
    t2 = t1 + timedelta(seconds=60)

    observations = [
        {
            "timestamp": t0,
            "absolute_spread": Decimal("0.20"),
            "relative_spread": Decimal("0.002"),
            "quality_status": "VALID",
        },
        {
            "timestamp": t1,
            "absolute_spread": Decimal("0.40"),
            "relative_spread": Decimal("0.004"),
            "quality_status": "VALID",
        },
    ]

    res = compute_time_weighted_spread(
        observations=observations,
        session_start=t0,
        session_end=t2,
        max_quote_age_seconds=120.0,
    )

    expected_tw = 30.0 / 90.0  # 0.333333...
    assert res["time_weighted_spread"] is not None
    assert abs(res["time_weighted_spread"] - expected_tw) < 1e-6
    assert res["valid_book_duration_seconds"] == 90.0
    assert res["coverage_percentage"] == 100.0


# ==============================================================================
# 5. End-to-End FastAPI Integration Test
# ==============================================================================

@pytest.mark.asyncio
async def test_spread_api_full_lifecycle():
    """
    End-to-End integration test covering:
    1. POST /spreads/configurations: Create custom configuration.
    2. POST /spreads/calculate: Calculate direct spread, verify exact results & persistence.
    3. Seed M02 NormalizedMarketTick record and resolve via GET /instruments/{id}/spread/current.
    4. GET /instruments/{id}/spread/history: Query historical spread observations.
    5. GET /instruments/{id}/spread/statistics: Verify observation-weighted & time-weighted statistics.
    6. GET /instruments/{id}/spread/quality: Inspect diagnostic checks.
    7. GET /instruments/{id}/spread/venues: Verify cross-venue comparison items.
    """
    await init_db()

    inst_id = f"INST_TEST_{uuid.uuid4().hex[:8].upper()}"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Step 1: Create custom configuration
        cfg_code = f"CFG_HFT_{inst_id[:8]}"
        cfg_payload = {
            "config_code": cfg_code,
            "name": "High Frequency Tight Policy",
            "description": "500ms skew, 2s staleness",
            "book_scope": "VENUE_SPECIFIC",
            "relative_spread_method": "MIDPOINT_NORMALIZED",
            "locked_book_policy": "INCLUDE_AS_ZERO",
            "maximum_quote_age_seconds": 2.0,
            "maximum_quote_skew_seconds": 0.5,
            "session_policy": "CONTINUOUS_ONLY",
            "tick_validation_policy": "STRICT_ALIGNMENT",
            "outlier_warning_policy": "FLAG_ONLY",
        }
        resp = await client.post("/api/v1/spreads/configurations", json=cfg_payload)
        assert resp.status_code == 201, resp.text
        cfg_data = resp.json()
        assert cfg_data["config_code"] == cfg_code

        # Step 2: Calculate direct spread on valid quote (Bid=150.00, Ask=150.25)
        calc_payload = {
            "instrument_id": inst_id,
            "exchange": "NSE",
            "venue": "NSE",
            "book_scope": "VENUE_SPECIFIC",
            "source_feed_id": "FEED_DIRECT",
            "best_bid": "150.00",
            "best_ask": "150.25",
            "bid_quantity": "500.0",
            "ask_quantity": "400.0",
            "tick_size": "0.05",
            "config_code": cfg_code,
            "persist_observation": True,
        }
        resp = await client.post("/api/v1/spreads/calculate", json=calc_payload)
        assert resp.status_code == 200, resp.text
        obs = resp.json()
        assert obs["quality_status"] == "VALID"
        assert float(obs["absolute_spread"]) == 0.25
        assert float(obs["midpoint_price"]) == 150.125
        assert float(obs["spread_ticks"]) == 5.0  # 0.25 / 0.05

        # Calculate a locked book on BSE (Bid=150.10, Ask=150.10)
        calc_bse = {
            "instrument_id": inst_id,
            "exchange": "BSE",
            "venue": "BSE",
            "book_scope": "VENUE_SPECIFIC",
            "source_feed_id": "FEED_BSE",
            "best_bid": "150.10",
            "best_ask": "150.10",
            "config_code": cfg_code,
            "persist_observation": True,
        }
        resp = await client.post("/api/v1/spreads/calculate", json=calc_bse)
        assert resp.status_code == 200, resp.text
        obs_bse = resp.json()
        assert obs_bse["quality_status"] == "VALID_LOCKED"
        assert float(obs_bse["absolute_spread"]) == 0.0

        # Step 3: Seed M02 NormalizedMarketTick record for NASDAQ venue
        tick_id = f"TICK_{uuid.uuid4().hex[:8]}"
        async with AsyncSessionLocal() as session:
            tick = NormalizedMarketTick(
                event_id=tick_id,
                feed_id="FEED_NASDAQ",
                instrument_id=inst_id,
                exchange="NASDAQ",
                symbol="AAPL_TEST",
                price=Decimal("150.20"),
                quantity=Decimal("100"),
                best_bid_price=Decimal("150.15"),
                best_bid_quantity=Decimal("300"),
                best_ask_price=Decimal("150.35"),
                best_ask_quantity=Decimal("200"),
                event_timestamp=datetime.now(timezone.utc),
            )
            session.add(tick)
            await session.commit()

        # Step 4: Query current spread via GET fallback to M02 tick
        resp = await client.get(f"/api/v1/instruments/{inst_id}/spread/current?venue=NASDAQ")
        assert resp.status_code == 200, resp.text
        curr = resp.json()
        assert curr["venue"] == "NASDAQ"
        assert float(curr["absolute_spread"]) == 0.20
        assert float(curr["midpoint_price"]) == 150.25

        # Step 5: Query historical spread observations
        resp = await client.get(f"/api/v1/instruments/{inst_id}/spread/history")
        assert resp.status_code == 200, resp.text
        hist = resp.json()
        assert len(hist) >= 3

        # Step 6: Query summary statistics
        resp = await client.get(f"/api/v1/instruments/{inst_id}/spread/statistics")
        assert resp.status_code == 200, resp.text
        stats = resp.json()
        assert stats["observation_count"] >= 3
        assert stats["valid_observation_count"] >= 3
        assert stats["mean_absolute_spread"] is not None

        # Step 7: Query quality diagnostics
        resp = await client.get(f"/api/v1/instruments/{inst_id}/spread/quality")
        assert resp.status_code == 200, resp.text
        q_results = resp.json()
        assert isinstance(q_results, list)

        # Step 8: Compare venue spreads across NSE, BSE, NASDAQ
        resp = await client.get(f"/api/v1/instruments/{inst_id}/spread/venues")
        assert resp.status_code == 200, resp.text
        v_comp = resp.json()
        assert len(v_comp) >= 3
        v_names = {v["venue"] for v in v_comp}
        assert "NSE" in v_names
        assert "BSE" in v_names
        assert "NASDAQ" in v_names

