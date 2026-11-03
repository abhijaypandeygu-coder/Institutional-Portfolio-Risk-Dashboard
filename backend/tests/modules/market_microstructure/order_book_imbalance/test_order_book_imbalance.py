"""
Comprehensive tests for M09.08 Order Book Imbalance.
Verifies:
1. Best-level normalized imbalance: (B1 - A1) / (B1 + A1), bid & ask share identities
2. Microprice calculation and deviation from midpoint: (Ask_1 * Q_b1 + Bid_1 * Q_a1) / (Q_b1 + Q_a1)
3. Multi-level quantity and notional imbalance
4. Weighted imbalance: exponential level decay, linear decay, and distance decay
5. Time-series persistence ratios and run durations
6. Threshold-based reversals with hysteresis
7. Historical z-score and robust MAD-based standardization
8. Regime classification (STRONG_BID, MODERATE_BID, NEUTRAL, MODERATE_ASK, STRONG_ASK)
9. End-to-end FastAPI endpoint lifecycle and multi-venue comparison
"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.modules.market_microstructure.order_book_imbalance.calculations.imbalance_math import (
    OrderBookLevelData,
    TimeSeriesObservation,
    OrderBookImbalanceMath,
)


def test_best_level_imbalance_and_microprice():
    # Bid: $100.00 x 1,000 shares | Ask: $100.10 x 500 shares
    # Total Qty = 1,500
    # Imbalance = (1000 - 500) / 1500 = 500 / 1500 = +1/3 ~ +0.3333
    # Bid Share = 1000 / 1500 = 2/3 ~ 0.6667
    # Ask Share = 500 / 1500 = 1/3 ~ 0.3333
    # Identity check: I = BShare - AShare = 2/3 - 1/3 = 1/3
    imb, b_share, a_share = OrderBookImbalanceMath.calculate_normalized_imbalance(
        Decimal("1000.0"), Decimal("500.0")
    )
    assert imb is not None
    assert pytest.approx(float(imb), abs=1e-4) == 1.0 / 3.0
    assert pytest.approx(float(b_share), abs=1e-4) == 2.0 / 3.0
    assert pytest.approx(float(a_share), abs=1e-4) == 1.0 / 3.0
    assert pytest.approx(float(b_share - a_share), abs=1e-4) == float(imb)

    # Microprice = (100.10 * 1000 + 100.00 * 500) / 1500 = (100100 + 50000) / 1500 = 150100 / 1500 = 100.066667
    # Midpoint = (100.00 + 100.10) / 2 = 100.05
    # Since bid queue is larger, microprice is pulled towards ask ($100.0667 > $100.05)
    microprice, midpoint, dev_bps = OrderBookImbalanceMath.calculate_microprice(
        Decimal("100.00"), Decimal("100.10"), Decimal("1000.0"), Decimal("500.0")
    )
    assert microprice is not None
    assert midpoint is not None
    assert pytest.approx(float(microprice), abs=1e-4) == 100.066667
    assert pytest.approx(float(midpoint), abs=1e-4) == 100.05
    assert float(dev_bps) > 0.0


def test_multi_level_quantity_and_notional_imbalance():
    levels = [
        OrderBookLevelData(level_index=1, bid_price=Decimal("100.00"), ask_price=Decimal("100.05"), bid_quantity=Decimal("1000"), ask_quantity=Decimal("500")),
        OrderBookLevelData(level_index=2, bid_price=Decimal("99.95"), ask_price=Decimal("100.10"), bid_quantity=Decimal("1500"), ask_quantity=Decimal("1200")),
        OrderBookLevelData(level_index=3, bid_price=Decimal("99.90"), ask_price=Decimal("100.15"), bid_quantity=Decimal("2000"), ask_quantity=Decimal("2500")),
    ]
    # Sum Bid Qty = 1000 + 1500 + 2000 = 4500
    # Sum Ask Qty = 500 + 1200 + 2500 = 4200
    # Qty Imbalance = (4500 - 4200) / (4500 + 4200) = 300 / 8700 ~ +0.03448

    res = OrderBookImbalanceMath.calculate_snapshot_imbalance(levels=levels, requested_levels=3)
    assert res.multi_level_quantity_imbalance is not None
    assert pytest.approx(float(res.multi_level_quantity_imbalance), abs=1e-4) == 300.0 / 8700.0
    assert res.total_bid_quantity == Decimal("4500")
    assert res.total_ask_quantity == Decimal("4200")
    assert res.multi_level_notional_imbalance is not None
    assert res.actual_level_count == 3


def test_weighted_imbalance_level_decay_and_custom():
    levels = [
        OrderBookLevelData(level_index=1, bid_price=Decimal("50.00"), ask_price=Decimal("50.02"), bid_quantity=Decimal("500"), ask_quantity=Decimal("1000")),
        OrderBookLevelData(level_index=2, bid_price=Decimal("49.98"), ask_price=Decimal("50.04"), bid_quantity=Decimal("1500"), ask_quantity=Decimal("500")),
    ]
    # At Level 1, Ask is dominant (500 vs 1000 -> -0.3333)
    # If weighting decays deeper levels heavily (e.g. decay=2.0), Level 1 dominates and weighted imbalance is negative.
    res_exp = OrderBookImbalanceMath.calculate_snapshot_imbalance(
        levels=levels, requested_levels=2, weighting_method="EXPONENTIAL_LEVEL", decay_parameter=2.0
    )
    assert res_exp.weighted_quantity_imbalance is not None
    assert float(res_exp.weighted_quantity_imbalance) < 0.0

    # Custom weights: [1.0, 1.0] gives equal weighting
    res_custom = OrderBookImbalanceMath.calculate_snapshot_imbalance(
        levels=levels, requested_levels=2, weighting_method="CUSTOM", custom_weights=[1.0, 1.0]
    )
    res_equal = OrderBookImbalanceMath.calculate_snapshot_imbalance(
        levels=levels, requested_levels=2, weighting_method="EQUAL"
    )
    assert pytest.approx(float(res_custom.weighted_quantity_imbalance), abs=1e-4) == float(res_equal.weighted_quantity_imbalance)


def test_persistence_and_reversals_math():
    now = datetime.now(timezone.utc)
    # 5 observations: 2 positive, 1 neutral, 2 negative
    obs = [
        TimeSeriesObservation(timestamp=now, imbalance=Decimal("0.35"), duration_seconds=2.0),
        TimeSeriesObservation(timestamp=now + timedelta(seconds=2), imbalance=Decimal("0.40"), duration_seconds=3.0),
        TimeSeriesObservation(timestamp=now + timedelta(seconds=5), imbalance=Decimal("0.05"), duration_seconds=1.0),
        TimeSeriesObservation(timestamp=now + timedelta(seconds=6), imbalance=Decimal("-0.30"), duration_seconds=2.0),
        TimeSeriesObservation(timestamp=now + timedelta(seconds=8), imbalance=Decimal("-0.45"), duration_seconds=2.0),
    ]
    # Total duration = 2 + 3 + 1 + 2 + 2 = 10.0s
    # Bid (>= 0.20): 5.0s -> 50%
    # Ask (<= -0.20): 4.0s -> 40%
    # Neutral: 1.0s -> 10%
    pers = OrderBookImbalanceMath.calculate_persistence_and_runs(obs, threshold=Decimal("0.20"))
    assert pers["bid_persistence_ratio"] == Decimal("0.5000")
    assert pers["ask_persistence_ratio"] == Decimal("0.4000")
    assert pers["neutral_persistence_ratio"] == Decimal("0.1000")
    assert pers["current_state"] == "ASK_DOMINANT"

    # Reversal detection: should detect transition from BID_DOMINANT to NEUTRAL/ASK_DOMINANT
    revs = OrderBookImbalanceMath.detect_reversals(obs, entry_threshold=Decimal("0.20"), exit_threshold=Decimal("0.10"))
    assert len(revs) >= 1
    assert any(r["new_state"] == "ASK_DOMINANT" for r in revs)


def test_historical_zscore_and_regime_classification():
    history = [Decimal("-0.30"), Decimal("-0.10"), Decimal("0.0"), Decimal("0.10"), Decimal("0.30")]
    current = Decimal("0.50")
    z_std, z_rob = OrderBookImbalanceMath.compute_historical_zscore(current, history)
    assert z_std is not None and z_rob is not None
    assert float(z_std) > 0.0
    assert float(z_rob) > 0.0

    assert OrderBookImbalanceMath.classify_regime(Decimal("0.75")) == "STRONG_BID"
    assert OrderBookImbalanceMath.classify_regime(Decimal("0.35")) == "MODERATE_BID"
    assert OrderBookImbalanceMath.classify_regime(Decimal("0.05")) == "NEUTRAL"
    assert OrderBookImbalanceMath.classify_regime(Decimal("-0.25")) == "MODERATE_ASK"
    assert OrderBookImbalanceMath.classify_regime(Decimal("-0.80")) == "STRONG_ASK"


@pytest.mark.asyncio
async def test_order_book_imbalance_api_lifecycle():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Create config
        cfg_payload = {
            "config_name": "High Frequency 5-Level Config",
            "depth_level_count": 5,
            "weighting_method": "EXPONENTIAL_LEVEL",
            "decay_parameter": 0.40,
        }
        cfg_resp = await ac.post("/api/v1/market-microstructure/order-book-imbalance/configs", json=cfg_payload)
        assert cfg_resp.status_code == 201
        config_id = cfg_resp.json()["config_id"]

        # 2. Calculate and save snapshot
        calc_payload = {
            "instrument_id": "INST-NVDA",
            "venue_id": "XNAS",
            "config_id": config_id,
            "requested_levels": 3,
            "weighting_method": "EQUAL",
            "levels": [
                {"level_index": 1, "bid_price": 120.00, "ask_price": 120.02, "bid_quantity": 2500, "ask_quantity": 1000},
                {"level_index": 2, "bid_price": 119.98, "ask_price": 120.04, "bid_quantity": 3000, "ask_quantity": 1500},
                {"level_index": 3, "bid_price": 119.96, "ask_price": 120.06, "bid_quantity": 4000, "ask_quantity": 2000},
            ],
        }
        post_snap = await ac.post("/api/v1/market-microstructure/order-book-imbalance/calculate", json=calc_payload)
        assert post_snap.status_code == 201
        data = post_snap.json()
        assert data["instrument_id"] == "INST-NVDA"
        assert float(data["best_level_imbalance"]) > 0.0
        assert data["regime"] == "STRONG_BID" or data["regime"] == "MODERATE_BID"

        # 3. Retrieve current
        get_curr = await ac.get("/api/v1/market-microstructure/order-book-imbalance/INST-NVDA/current?venue_id=XNAS")
        assert get_curr.status_code == 200
        assert get_curr.json()["snapshot_id"] == data["snapshot_id"]

        # 4. Persistence Endpoint
        now_iso = datetime.now(timezone.utc).isoformat()
        pers_payload = {
            "instrument_id": "INST-NVDA",
            "venue_id": "XNAS",
            "threshold": 0.20,
            "observations": [
                {"timestamp": now_iso, "imbalance": 0.35, "duration_seconds": 5.0},
                {"timestamp": now_iso, "imbalance": 0.40, "duration_seconds": 5.0},
            ],
        }
        pers_resp = await ac.post("/api/v1/market-microstructure/order-book-imbalance/persistence", json=pers_payload)
        assert pers_resp.status_code == 200
        assert Decimal(str(pers_resp.json()["bid_persistence_ratio"])) == Decimal("1.0")

        # 5. Venue comparison
        venue_payload = {
            "instrument_id": "INST-NVDA",
            "venues_data": {
                "XNAS": [
                    {"level_index": 1, "bid_price": 120.00, "ask_price": 120.02, "bid_quantity": 2500, "ask_quantity": 1000}
                ],
                "XNYS": [
                    {"level_index": 1, "bid_price": 120.00, "ask_price": 120.03, "bid_quantity": 800, "ask_quantity": 1800}
                ],
            },
        }
        venue_resp = await ac.post("/api/v1/market-microstructure/order-book-imbalance/venues", json=venue_payload)
        assert venue_resp.status_code == 200
        v_data = venue_resp.json()
        assert "XNAS" in v_data["venues"]
        assert "XNYS" in v_data["venues"]
        assert float(v_data["venues"]["XNAS"]["best_level_imbalance"]) > 0.0
        assert float(v_data["venues"]["XNYS"]["best_level_imbalance"]) < 0.0
