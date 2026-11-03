"""
M09.02 Order Book Depth Comprehensive Pytest Suite.
Verifies:
1. Pure Math Hand-Calculated Bid-Side & Ask-Side Depth:
   - Example from Prompt Section M09.02.01:
     Bids: 100.00 (1200), 99.95 (1500), 99.90 (2000), 99.85 (1700), 99.80 (2100)
     Total 5-level bid quantity = 8,500
     Notionals:
       L1: 100.00 * 1200 = 120,000
       L2: 99.95 * 1500 = 149,925 (cum = 269,925)
       L3: 99.90 * 2000 = 199,800 (cum = 469,725)
       L4: 99.85 * 1700 = 169,745
       L5: 99.80 * 2100 = 209,580
       Total 5-level notional = 849,050
2. Level Distances & Cumulative Depth Profiles:
   - Midpoint calculation: (100.00 + 100.05) / 2 = 100.025
   - Distance in absolute, bps, and ticks.
3. Quantity & Notional Imbalance:
   - Hand-calculated I_Q = (D_b - D_a) / (D_b + D_a)
   - Hand-calculated I_N = (ND_b - ND_a) / (ND_b + ND_a)
   - Zero-denominator guardrails (returns None, never fabricated 0).
4. Price-Band Depth:
   - Grouping into 0-5 bps, 5-10 bps, 10-25 bps, 25-50 bps.
5. Time-Weighted Depth Persistence & Stability:
   - Time-weighted mean depth D_TW = sum(D_j * dt_j) / sum(dt_j)
   - Time-weighted standard deviation & CV
   - Threshold persistence % (depth >= D_min)
   - Price-level persistence %
6. End-to-End FastAPI Lifecycle:
   - Configuration creation
   - Direct calculation & persistence
   - Resolution from M02 OrderBookSnapshotRecord
   - Level queries, cumulative depth, imbalance, bands, persistence.
"""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.modules.market_microstructure.order_book_depth.calculations import (
    sort_and_validate_levels,
    compute_depth_by_level,
    compute_cumulative_depth,
    compute_depth_imbalance,
    compute_distance_weighted_depth,
    compute_price_band_depth,
    compute_depth_persistence,
)
from backend.app.modules.market_data_ingestion.persistence.models import OrderBookSnapshotRecord


# ==============================================================================
# 1. Pure Math Unit Tests: Hand-Calculated Bid-Side & Ask-Side Depth
# ==============================================================================

def test_hand_calculated_depth_and_notional():
    """
    Prompt Section M09.02.01 Hand-Calculated Example:
    Bids:
      L1: 100.00, qty 1200
      L2:  99.95, qty 1500
      L3:  99.90, qty 2000
      L4:  99.85, qty 1700
      L5:  99.80, qty 2100
    Total 5-level bid quantity = 8,500
    """
    raw_bids = [
        {"price": Decimal("100.00"), "quantity": Decimal("1200")},
        {"price": Decimal("99.95"), "quantity": Decimal("1500")},
        {"price": Decimal("99.90"), "quantity": Decimal("2000")},
        {"price": Decimal("99.85"), "quantity": Decimal("1700")},
        {"price": Decimal("99.80"), "quantity": Decimal("2100")},
    ]

    raw_asks = [
        {"price": Decimal("100.05"), "quantity": Decimal("1100")},
        {"price": Decimal("100.10"), "quantity": Decimal("1800")},
        {"price": Decimal("100.15"), "quantity": Decimal("1600")},
    ]

    midpoint, proc_bids, proc_asks, status = compute_depth_by_level(
        bids=raw_bids,
        asks=raw_asks,
        contract_multiplier=Decimal("1.0"),
        tick_size=Decimal("0.05"),
        max_levels=5,
    )

    assert status == "VALID"
    assert len(proc_bids) == 5
    assert len(proc_asks) == 3

    # Check Bid Quantities & Cumulative Quantities
    assert proc_bids[0]["quantity"] == Decimal("1200")
    assert proc_bids[0]["cumulative_quantity"] == Decimal("1200")
    assert proc_bids[1]["cumulative_quantity"] == Decimal("2700")
    assert proc_bids[2]["cumulative_quantity"] == Decimal("4700")
    assert proc_bids[3]["cumulative_quantity"] == Decimal("6400")
    assert proc_bids[4]["cumulative_quantity"] == Decimal("8500")

    # Check Notionals
    assert proc_bids[0]["notional"] == Decimal("120000.00")
    assert proc_bids[1]["notional"] == Decimal("149925.00")
    assert proc_bids[1]["cumulative_notional"] == Decimal("269925.00")
    assert proc_bids[2]["notional"] == Decimal("199800.00")
    assert proc_bids[2]["cumulative_notional"] == Decimal("469725.00")

    # Midpoint: (100.00 + 100.05) / 2 = 100.025
    assert midpoint == Decimal("100.025")

    # Distance in ticks for Best Bid (100.025 - 100.00 = 0.025; 0.025 / 0.05 = 0.5 ticks)
    assert proc_bids[0]["distance_from_midpoint"] == Decimal("0.025")
    assert proc_bids[0]["distance_ticks"] == Decimal("0.5")


# ==============================================================================
# 2. Pure Math Unit Tests: Hand-Calculated Imbalance & Weighted Imbalance
# ==============================================================================

def test_hand_calculated_depth_imbalance():
    """
    Prompt Section M09.02.05 Imbalance:
    Bid Quantity = 8,500, Ask Quantity = 4,500
    I_Q = (8,500 - 4,500) / (8,500 + 4,500) = 4,000 / 13,000 = 0.307692...
    Bid Notional = 849,050, Ask Notional = 450,475
    I_N = (849,050 - 450,475) / (849,050 + 450,475) = 398,575 / 1,299,525 = 0.306708...
    """
    d_b = Decimal("8500")
    d_a = Decimal("4500")
    nd_b = Decimal("849050")
    nd_a = Decimal("450475")

    imb = compute_depth_imbalance(
        bid_quantity=d_b,
        ask_quantity=d_a,
        bid_notional=nd_b,
        ask_notional=nd_a,
    )

    expected_q_imb = (d_b - d_a) / (d_b + d_a)
    expected_n_imb = (nd_b - nd_a) / (nd_b + nd_a)

    assert imb["quantity_imbalance"] is not None
    assert abs(imb["quantity_imbalance"] - expected_q_imb) < Decimal("1e-6")
    assert abs(imb["notional_imbalance"] - expected_n_imb) < Decimal("1e-6")
    assert abs(imb["quantity_imbalance_percentage"] - (expected_q_imb * Decimal("100"))) < Decimal("1e-4")

    # Zero-denominator guardrail
    zero_imb = compute_depth_imbalance(
        bid_quantity=Decimal("0"),
        ask_quantity=Decimal("0"),
        bid_notional=Decimal("0"),
        ask_notional=Decimal("0"),
    )
    assert zero_imb["quantity_imbalance"] is None
    assert zero_imb["notional_imbalance"] is None


# ==============================================================================
# 3. Pure Math Unit Tests: Price-Band Depth
# ==============================================================================

def test_price_band_depth_aggregation():
    """
    Tests aggregation into bps distance bands.
    """
    # Midpoint = 100.00
    # Level 1: Bid 99.98 -> dist = 0.02 -> 0.02 / 100.00 * 10,000 = 2 bps (Band 0-5 bps)
    # Level 2: Bid 99.92 -> dist = 0.08 -> 8 bps (Band 5-10 bps)
    # Level 1: Ask 100.03 -> dist = 0.03 -> 3 bps (Band 0-5 bps)
    # Level 2: Ask 100.09 -> dist = 0.09 -> 9 bps (Band 5-10 bps)
    bid_levels = [
        {"price": Decimal("99.98"), "quantity": Decimal("1000"), "distance_bps": Decimal("2.0")},
        {"price": Decimal("99.92"), "quantity": Decimal("2000"), "distance_bps": Decimal("8.0")},
    ]
    ask_levels = [
        {"price": Decimal("100.03"), "quantity": Decimal("1200"), "distance_bps": Decimal("3.0")},
        {"price": Decimal("100.09"), "quantity": Decimal("1500"), "distance_bps": Decimal("9.0")},
    ]

    bands = [
        (0.0, 5.0, "BAND_0_5_BPS"),
        (5.0, 10.0, "BAND_5_10_BPS"),
    ]

    res = compute_price_band_depth(bid_levels, ask_levels, bands)
    assert len(res) == 2

    band1 = res[0]
    assert band1["band_id"] == "BAND_0_5_BPS"
    assert band1["bid_quantity"] == Decimal("1000")
    assert band1["ask_quantity"] == Decimal("1200")
    assert band1["bid_level_count"] == 1
    assert band1["ask_level_count"] == 1

    band2 = res[1]
    assert band2["band_id"] == "BAND_5_10_BPS"
    assert band2["bid_quantity"] == Decimal("2000")
    assert band2["ask_quantity"] == Decimal("1500")


# ==============================================================================
# 4. Pure Math Unit Tests: Time-Weighted Depth Persistence & Stability
# ==============================================================================

def test_hand_calculated_depth_persistence():
    """
    Tests time-weighted average depth, variance, and threshold persistence:
    State 1: Duration 30s, Bid Depth = 5,000
    State 2: Duration 60s, Bid Depth = 8,000
    Total valid time = 90s
    Expected D_TW = (5,000 * 30 + 8,000 * 60) / 90 = (150,000 + 480,000) / 90 = 630,000 / 90 = 7,000.0
    Minimum threshold = 6,000 -> State 2 meets threshold (60s out of 90s = 66.6667%)
    """
    t0 = datetime(2026, 2, 2, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=30)
    t2 = t1 + timedelta(seconds=60)

    observations = [
        {
            "timestamp": t0,
            "bid_depth": Decimal("5000"),
            "ask_depth": Decimal("4000"),
            "quality_status": "VALID",
        },
        {
            "timestamp": t1,
            "bid_depth": Decimal("8000"),
            "ask_depth": Decimal("6000"),
            "quality_status": "VALID",
        },
    ]

    res = compute_depth_persistence(
        observations=observations,
        session_start=t0,
        session_end=t2,
        minimum_depth_threshold=Decimal("6000"),
    )

    assert res["bid_time_weighted_mean"] == 7000.0
    assert res["valid_duration_seconds"] == 90.0
    assert res["coverage_percentage"] == 100.0
    # Threshold persistence: 60s / 90s = 66.6667%
    assert abs(res["bid_threshold_persistence"] - 66.6667) < 0.01
    assert res["bid_depth_cv"] is not None
    assert res["depth_stability_score"] is not None


# ==============================================================================
# 5. End-to-End FastAPI Integration Test
# ==============================================================================

@pytest.mark.asyncio
async def test_order_book_depth_api_full_lifecycle():
    """
    Full end-to-end integration test:
    1. POST /depth/configurations: Create custom 5-level configuration.
    2. POST /depth/calculate: Calculate direct depth, verify per-level ladder, cumulative metrics, and bands.
    3. Seed M02 OrderBookSnapshotRecord and verify fallback via GET /depth/{id}/current.
    4. GET /depth/{id}/levels: Verify bid/ask side filtering.
    5. GET /depth/{id}/cumulative: Verify cumulative liquidity curves.
    6. GET /depth/{id}/imbalance: Verify quantity and notional imbalance.
    7. GET /depth/{id}/bands: Verify price-band aggregation.
    8. GET /depth/{id}/persistence: Verify time-weighted persistence statistics.
    9. GET /depth/{id}/history: Query historical depth snapshots.
    """
    await init_db()

    inst_id = f"INST_DP_{uuid.uuid4().hex[:8].upper()}"
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Step 1: Create custom depth configuration
        cfg_code = f"CFG_DEPTH_{inst_id[:8]}"
        cfg_payload = {
            "config_code": cfg_code,
            "name": "Institutional 5-Level Depth Policy",
            "level_count": 5,
            "aggregation_mode": "LEVEL_BASED",
            "distance_unit": "BPS",
            "weighting_parameter": 0.05,
            "minimum_depth_threshold": "1000.0",
        }
        resp = await client.post("/api/v1/market-microstructure/depth/configurations", json=cfg_payload)
        assert resp.status_code == 201, resp.text
        cfg_data = resp.json()
        assert cfg_data["config_code"] == cfg_code

        # Step 2: Directly calculate depth on 5 bid and 5 ask levels
        bids_in = [
            {"price": "100.00", "quantity": "1200", "order_count": 10},
            {"price": "99.95", "quantity": "1500", "order_count": 8},
            {"price": "99.90", "quantity": "2000", "order_count": 12},
            {"price": "99.85", "quantity": "1700", "order_count": 5},
            {"price": "99.80", "quantity": "2100", "order_count": 14},
        ]
        asks_in = [
            {"price": "100.05", "quantity": "1100", "order_count": 9},
            {"price": "100.10", "quantity": "1800", "order_count": 11},
            {"price": "100.15", "quantity": "1600", "order_count": 7},
            {"price": "100.20", "quantity": "1400", "order_count": 6},
            {"price": "100.25", "quantity": "1900", "order_count": 15},
        ]
        calc_payload = {
            "instrument_id": inst_id,
            "exchange": "NSE",
            "venue": "NSE",
            "source_feed_id": "FEED_DIRECT",
            "bids": bids_in,
            "asks": asks_in,
            "config_code": cfg_code,
            "tick_size": "0.05",
            "persist_snapshot": True,
        }
        resp = await client.post("/api/v1/market-microstructure/depth/calculate", json=calc_payload)
        assert resp.status_code == 200, resp.text
        snap = resp.json()
        assert snap["depth_quality_status"] == "VALID"
        assert float(snap["bid_total_quantity"]) == 8500.0
        assert float(snap["ask_total_quantity"]) == 7800.0
        assert float(snap["midpoint_price"]) == 100.025
        assert len(snap["levels"]) == 10
        assert len(snap["bands"]) >= 1

        # Step 3: Seed M02 OrderBookSnapshotRecord for fallback query
        inst_m02 = f"INST_M02_{uuid.uuid4().hex[:8].upper()}"
        async with AsyncSessionLocal() as session:
            record = OrderBookSnapshotRecord(
                event_id=f"EVT_{uuid.uuid4().hex[:8]}",
                feed_id="FEED_M02",
                instrument_id=inst_m02,
                exchange="NSE",
                sequence_number=101,
                snapshot_timestamp=datetime.now(timezone.utc),
                bid_levels=[{"price": "250.00", "quantity": "500", "level": 1}],
                ask_levels=[{"price": "250.10", "quantity": "600", "level": 1}],
            )
            session.add(record)
            await session.commit()

        # Query GET /depth/{id}/current which resolves from M02
        resp = await client.get(f"/api/v1/market-microstructure/depth/{inst_m02}/current")
        assert resp.status_code == 200, resp.text
        curr_m02 = resp.json()
        assert float(curr_m02["best_bid_price"]) == 250.00
        assert float(curr_m02["best_ask_price"]) == 250.10

        # Step 4: GET /depth/{id}/levels
        resp = await client.get(f"/api/v1/market-microstructure/depth/{inst_id}/levels?side=BID")
        assert resp.status_code == 200, resp.text
        bids_resp = resp.json()
        assert len(bids_resp) == 5
        assert bids_resp[0]["side"] == "BID"

        # Step 5: GET /depth/{id}/cumulative
        resp = await client.get(f"/api/v1/market-microstructure/depth/{inst_id}/cumulative?level_count=3")
        assert resp.status_code == 200, resp.text
        cum_resp = resp.json()
        assert cum_resp["levels_requested"] == 3
        assert float(cum_resp["bid_cumulative_quantity"]) == 4700.0  # 1200 + 1500 + 2000

        # Step 6: GET /depth/{id}/imbalance
        resp = await client.get(f"/api/v1/market-microstructure/depth/{inst_id}/imbalance")
        assert resp.status_code == 200, resp.text
        imb_resp = resp.json()
        assert imb_resp["quantity_imbalance"] is not None
        assert float(imb_resp["quantity_imbalance"]) > 0  # 8500 > 7800

        # Step 7: GET /depth/{id}/bands
        resp = await client.get(f"/api/v1/market-microstructure/depth/{inst_id}/bands")
        assert resp.status_code == 200, resp.text
        bands_resp = resp.json()
        assert len(bands_resp) >= 1

        # Step 8: GET /depth/{id}/persistence
        now = datetime.now(timezone.utc)
        t_start = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        t_end = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        resp = await client.get(
            f"/api/v1/market-microstructure/depth/{inst_id}/persistence",
            params={"start_time": t_start, "end_time": t_end},
        )
        assert resp.status_code == 200, resp.text
        pers_resp = resp.json()
        assert pers_resp["valid_state_count"] >= 1
        assert pers_resp["bid_time_weighted_mean"] is not None

        # Step 9: GET /depth/{id}/history
        resp = await client.get(f"/api/v1/market-microstructure/depth/{inst_id}/history")
        assert resp.status_code == 200, resp.text
        hist_resp = resp.json()
        assert len(hist_resp) >= 1
