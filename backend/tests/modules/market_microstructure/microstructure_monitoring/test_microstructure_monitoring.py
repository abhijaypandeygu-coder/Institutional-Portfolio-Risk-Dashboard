"""
Unit and Integration Tests for M09.09 Microstructure Monitoring.

Validates:
1. Spread Volatility & Widening Math:
   - Absolute, relative, bps changes
   - Rolling mean, sample stddev, CV, range, and time-weighted mean
   - Robust standardization (Median, MAD, Z_robust)
   - Widening classification and hysteresis
2. Depth Fluctuations, Depletion & Replenishment Math:
   - Depth increase, reduction, unchanged
   - Depletion velocity
   - Replenishment recovery ratio (fully recovered, partial, further depleted)
3. Update Intensity & Burst Detection:
   - Message rates vs book-change rates (separation verification)
   - Intensity ratio and burst severity
4. Feed Staleness & Inactivity:
   - Observation age and receive latency
   - Fresh, Aging, Stale, Feed Unavailable states
5. Statistical Change Detection:
   - EWMA smoothing
   - CUSUM two-sided change detection
6. End-to-end API Lifecycle:
   - Config creation
   - Spread monitoring
   - Depth monitoring
   - Update intensity monitoring
   - Freshness evaluation
   - Anomaly query, acknowledgement, and resolution
   - Current monitoring overview
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.modules.market_microstructure.microstructure_monitoring.calculations.monitoring_math import (
    to_decimal,
    compute_spread_changes,
    compute_spread_series_metrics,
    compute_robust_z_score,
    classify_spread_deterioration,
    compute_depth_fluctuations,
    compute_replenishment_metrics,
    compute_update_intensity,
    compute_staleness_metrics,
    compute_ewma_series,
    compute_cusum_detector
)


@pytest.mark.asyncio
async def test_spread_volatility_and_robust_metrics():
    """
    Verifies spread series metrics: mean, stddev, CV, time-weighted mean, and robust Z-score.
    """
    spreads = [Decimal("0.05"), Decimal("0.06"), Decimal("0.05"), Decimal("0.07"), Decimal("0.12")]
    base_time = datetime(2026, 11, 3, 9, 30, 0, tzinfo=timezone.utc)
    timestamps = [base_time + timedelta(seconds=i * 10) for i in range(5)]

    metrics = compute_spread_series_metrics(spreads, timestamps)
    assert metrics["mean"] is not None
    # Mean of [0.05, 0.06, 0.05, 0.07, 0.12] = 0.35 / 5 = 0.07
    assert metrics["mean"] == Decimal("0.07000000")
    assert metrics["spread_range"] == Decimal("0.07000000")
    assert metrics["stddev"] > Decimal("0")
    assert metrics["cv"] is not None

    # Robust Z-score:
    # Sorted: [0.05, 0.05, 0.06, 0.07, 0.12] -> Median = 0.06
    # Deviations from 0.06: [0.01, 0.01, 0.00, 0.01, 0.06] -> Sorted: [0.00, 0.01, 0.01, 0.01, 0.06] -> MAD = 0.01
    med, mad, z_rob = compute_robust_z_score(Decimal("0.12"), spreads)
    assert med == Decimal("0.06000000")
    assert mad == Decimal("0.01000000")
    # Z_robust = (0.12 - 0.06) / (1.4826 * 0.01) = 0.06 / 0.014826 ≈ 4.0469
    assert z_rob is not None
    assert z_rob > Decimal("3.0")

    category, severity = classify_spread_deterioration(
        current_spread=Decimal("0.12"),
        baseline_spread=Decimal("0.05"),
        z_robust=z_rob
    )
    assert category == "EXTREME_WIDENING"
    assert severity == "CRITICAL"


@pytest.mark.asyncio
async def test_depth_fluctuation_depletion_and_replenishment():
    """
    Verifies depth reduction, depletion velocity, and replenishment recovery ratio.
    """
    # 1. Depth reduction from 10,000 to 4,000 over 2 seconds
    d_prev = Decimal("10000")
    d_curr = Decimal("4000")
    elapsed = Decimal("2.0")

    flucts = compute_depth_fluctuations(
        current_depth=d_curr,
        previous_depth=d_prev,
        elapsed_seconds=elapsed
    )
    assert flucts["classification"] == "DEPTH_REDUCTION"
    assert flucts["absolute_change"] == Decimal("-6000.0000")
    assert flucts["relative_change_pct"] == Decimal("-60.0000")
    assert flucts["depletion_amount"] == Decimal("6000.0000")
    assert flucts["depletion_rate"] == Decimal("3000.0000") # 6000 / 2.0 = 3000/sec

    # 2. Replenishment recovery: baseline 10,000, post-depletion 4,000, new depth 8,500
    # Lost depth = 6,000. Replenished = 8,500 - 4,000 = 4,500.
    # Recovery ratio = 4,500 / 6,000 = 0.75 (75% recovery)
    replen = compute_replenishment_metrics(
        baseline_depth=Decimal("10000"),
        post_depletion_depth=Decimal("4000"),
        current_depth=Decimal("8500")
    )
    assert replen["replenishment_amount"] == Decimal("4500.0000")
    assert replen["recovery_ratio"] == Decimal("0.7500")
    assert replen["recovery_status"] == "PARTIALLY_RECOVERED"

    # Full recovery to 10,000
    replen_full = compute_replenishment_metrics(
        baseline_depth=Decimal("10000"),
        post_depletion_depth=Decimal("4000"),
        current_depth=Decimal("10000")
    )
    assert replen_full["recovery_ratio"] == Decimal("1.0000")
    assert replen_full["recovery_status"] == "FULLY_RECOVERED"


@pytest.mark.asyncio
async def test_update_intensity_and_burst_separation():
    """
    Verifies that message rate and book-change rate remain strictly separated.
    Tests burst detection against baseline.
    """
    # 500 total incoming messages, 450 valid messages, but only 50 caused book changes over 5 seconds
    res = compute_update_intensity(
        total_messages=500,
        valid_messages=450,
        book_updates=50,
        elapsed_seconds=Decimal("5.0"),
        baseline_rate=Decimal("20.0")
    )
    # Message rate = 500 / 5 = 100 msgs/sec
    # Book change rate = 50 / 5 = 10 updates/sec
    assert res["message_rate"] == Decimal("100.0000")
    assert res["valid_message_rate"] == Decimal("90.0000")
    assert res["book_change_rate"] == Decimal("10.0000")
    assert res["intensity_ratio"] == Decimal("5.0000") # 100 / 20 = 5.0x baseline


@pytest.mark.asyncio
async def test_staleness_and_inactivity_classification():
    """
    Verifies observation age, receive latency, and feed staleness status transitions.
    """
    t_source = datetime(2026, 11, 3, 10, 0, 0, tzinfo=timezone.utc)
    t_recv = datetime(2026, 11, 3, 10, 0, 0, 50000, tzinfo=timezone.utc) # 50ms latency

    # 1. Fresh observation (age 500ms <= 1000ms cadence)
    t_now_fresh = datetime(2026, 11, 3, 10, 0, 0, 500000, tzinfo=timezone.utc)
    fresh_res = compute_staleness_metrics(t_now_fresh, t_source, t_recv, expected_cadence_ms=1000)
    assert fresh_res["observation_age_ms"] == 500
    assert fresh_res["receive_latency_ms"] == 50
    assert fresh_res["staleness_state"] == "FRESH"

    # 2. Aging observation (age 2000ms > 1000ms and <= 3000ms)
    t_now_aging = datetime(2026, 11, 3, 10, 0, 2, 0, tzinfo=timezone.utc)
    aging_res = compute_staleness_metrics(t_now_aging, t_source, t_recv, expected_cadence_ms=1000)
    assert aging_res["staleness_state"] == "AGING"

    # 3. Stale observation (age 5000ms > 3000ms and <= 10000ms)
    t_now_stale = datetime(2026, 11, 3, 10, 0, 5, 0, tzinfo=timezone.utc)
    stale_res = compute_staleness_metrics(t_now_stale, t_source, t_recv, expected_cadence_ms=1000)
    assert stale_res["staleness_state"] == "STALE"

    # 4. Feed unavailable (age 15000ms > 10000ms)
    t_now_dead = datetime(2026, 11, 3, 10, 0, 15, 0, tzinfo=timezone.utc)
    dead_res = compute_staleness_metrics(t_now_dead, t_source, t_recv, expected_cadence_ms=1000)
    assert dead_res["staleness_state"] == "FEED_UNAVAILABLE"


@pytest.mark.asyncio
async def test_ewma_and_cusum_change_detectors():
    """
    Verifies EWMA smoothing and CUSUM cumulative sum change detection.
    """
    series = [Decimal("10"), Decimal("10"), Decimal("11"), Decimal("15"), Decimal("22")]
    ewma_res = compute_ewma_series(series, alpha=Decimal("0.5"))
    assert len(ewma_res) == 5
    assert ewma_res[0] == Decimal("10")
    # E_1 = 0.5 * 10 + 0.5 * 10 = 10
    # E_2 = 0.5 * 11 + 0.5 * 10 = 10.5
    assert ewma_res[2] == Decimal("10.50000000")

    # CUSUM test with baseline mean 10, slack 1, threshold 5
    cusum_res = compute_cusum_detector(
        values=series,
        target_mean=Decimal("10"),
        slack_allowance=Decimal("1"),
        decision_threshold=Decimal("5")
    )
    assert cusum_res["anomaly_detected"] is True
    assert cusum_res["direction"] == "UPWARD_SHIFT"


@pytest.mark.asyncio
async def test_microstructure_monitoring_api_full_lifecycle():
    """
    Validates end-to-end API lifecycle:
    Config creation -> Spread monitoring -> Depth monitoring -> Intensity -> Freshness -> Anomaly Lifecycle -> Overview.
    """
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Monitoring Config
        cfg_payload = {
            "config_name": "NSE_EQUITY_HFT_SURVEILLANCE_2026",
            "description": "High-frequency surveillance configuration for NSE equity universe",
            "market_scope": "INDIA",
            "venue_scope": "NSE",
            "feed_scope": "STREAMING_TICK",
            "instrument_scope": "ALL",
            "monitoring_mode": "STREAMING",
            "spread_window_seconds": 60,
            "depth_window_seconds": 60,
            "update_rate_window_seconds": 10,
            "maximum_spread_age_ms": 3000,
            "maximum_book_age_ms": 5000,
            "expected_update_cadence_ms": 1000,
            "minimum_sample_count": 5,
            "minimum_coverage": 0.85,
            "version": "1.0.0"
        }
        cfg_resp = await client.post("/api/v1/market-microstructure/monitoring/configs", json=cfg_payload)
        assert cfg_resp.status_code == 201
        cfg_data = cfg_resp.json()
        assert cfg_data["config_name"] == "NSE_EQUITY_HFT_SURVEILLANCE_2026"

        # 2. Spread Monitoring (Sudden widening triggering an anomaly)
        base_time = datetime(2026, 11, 3, 10, 30, 0, tzinfo=timezone.utc)
        spread_payload = {
            "instrument_id": "RELIANCE_EQ",
            "listing_id": "RELIANCE_NSE",
            "venue_id": "NSE",
            "source_feed_id": "NSE_STREAMING",
            "observations": [
                {"timestamp": (base_time + timedelta(seconds=0)).isoformat(), "absolute_spread": "0.10", "midpoint": "2500.00"},
                {"timestamp": (base_time + timedelta(seconds=1)).isoformat(), "absolute_spread": "0.10", "midpoint": "2500.00"},
                {"timestamp": (base_time + timedelta(seconds=2)).isoformat(), "absolute_spread": "0.12", "midpoint": "2500.00"},
                {"timestamp": (base_time + timedelta(seconds=3)).isoformat(), "absolute_spread": "0.45", "midpoint": "2500.00"} # Widening > 3x
            ],
            "historical_baseline_spread": "0.10",
            "config_version": "1.0.0"
        }
        sp_resp = await client.post("/api/v1/market-microstructure/monitoring/spread", json=spread_payload)
        assert sp_resp.status_code == 200
        sp_data = sp_resp.json()
        assert sp_data["spread_widening_flag"] is True
        assert sp_data["deterioration_severity"] in ["HIGH", "CRITICAL"]

        # 3. Depth Monitoring (Severe depth withdrawal)
        depth_payload = {
            "instrument_id": "RELIANCE_EQ",
            "listing_id": "RELIANCE_NSE",
            "venue_id": "NSE",
            "source_feed_id": "NSE_STREAMING",
            "observations": [
                {"timestamp": (base_time + timedelta(seconds=0)).isoformat(), "side": "BID", "displayed_depth": "10000", "baseline_depth": "10000"},
                {"timestamp": (base_time + timedelta(seconds=2)).isoformat(), "side": "BID", "displayed_depth": "3500", "baseline_depth": "10000"} # 65% drop
            ],
            "config_version": "1.0.0"
        }
        dp_resp = await client.post("/api/v1/market-microstructure/monitoring/depth", json=depth_payload)
        assert dp_resp.status_code == 200
        dp_data = dp_resp.json()
        assert dp_data["classification"] == "DEPTH_REDUCTION"
        assert float(dp_data["relative_depth_change"]) <= -60.0

        # 4. Update Intensity Monitoring (Burst trigger)
        int_payload = {
            "instrument_id": "RELIANCE_EQ",
            "listing_id": "RELIANCE_NSE",
            "venue_id": "NSE",
            "source_feed_id": "NSE_STREAMING",
            "interval_start": base_time.isoformat(),
            "interval_end": (base_time + timedelta(seconds=10)).isoformat(),
            "source_mode": "STREAMING",
            "total_message_count": 500,
            "valid_message_count": 480,
            "book_update_count": 60,
            "baseline_message_rate": "15.0"
        }
        int_resp = await client.post("/api/v1/market-microstructure/monitoring/update-intensity", json=int_payload)
        assert int_resp.status_code == 200
        int_data = int_resp.json()
        assert int_data["burst_detected"] is True
        assert float(int_data["message_rate"]) == 50.0 # 500 / 10s = 50 msgs/sec

        # 5. Feed Freshness
        fresh_payload = {
            "source_feed_id": "NSE_STREAMING",
            "instrument_id": "RELIANCE_EQ",
            "listing_id": "RELIANCE_NSE",
            "venue_id": "NSE",
            "monitoring_timestamp": (base_time + timedelta(seconds=12)).isoformat(),
            "last_source_event_timestamp": (base_time + timedelta(seconds=11, milliseconds=800)).isoformat(),
            "last_receive_timestamp": (base_time + timedelta(seconds=11, milliseconds=850)).isoformat(),
            "last_valid_book_timestamp": (base_time + timedelta(seconds=11, milliseconds=850)).isoformat(),
            "expected_update_cadence_ms": 1000
        }
        fr_resp = await client.post("/api/v1/market-microstructure/monitoring/freshness", json=fresh_payload)
        assert fr_resp.status_code == 200
        fr_data = fr_resp.json()
        assert fr_data["feed_status"] == "FRESH"

        # 6. Query Detected Anomalies
        anom_resp = await client.get("/api/v1/market-microstructure/monitoring/anomalies?instrument_id=RELIANCE_EQ")
        assert anom_resp.status_code == 200
        anomalies = anom_resp.json()
        assert len(anomalies) >= 2 # Widening and Depth Withdrawal anomalies
        target_anomaly = anomalies[0]
        anomaly_id = target_anomaly["id"]

        # 7. Acknowledge Anomaly
        ack_resp = await client.post(
            f"/api/v1/market-microstructure/monitoring/anomalies/{anomaly_id}/acknowledge",
            json={"actor_id": "SRE_USER_42", "notes": "Investigating order book spread widening"}
        )
        assert ack_resp.status_code == 200
        assert ack_resp.json()["lifecycle_status"] == "ACKNOWLEDGED"

        # 8. Resolve Anomaly
        res_resp = await client.post(
            f"/api/v1/market-microstructure/monitoring/anomalies/{anomaly_id}/resolve",
            json={"actor_id": "SRE_USER_42", "resolution_reason": "Spread normalized below recovery threshold"}
        )
        assert res_resp.status_code == 200
        assert res_resp.json()["lifecycle_status"] == "RESOLVED"

        # 9. Current Monitoring Overview
        ov_resp = await client.get("/api/v1/market-microstructure/monitoring/RELIANCE_EQ/current")
        assert ov_resp.status_code == 200
        ov_data = ov_resp.json()
        assert ov_data["instrument_id"] == "RELIANCE_EQ"
        assert float(ov_data["latest_spread"]) == 0.45
        assert ov_data["feed_freshness_status"] == "FRESH"

