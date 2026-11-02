"""
Unit and Integration tests for M07.04: Drawdown Analytics.
Verifies:
1. Mathematical unit test:
   - Running High-Water Mark calculation.
   - Signed vs positive drawdown percentages.
   - Peak-to-trough, trough-to-recovery, and underwater duration tracking.
   - Distinct episode segmentation (recovery closes episode; partial recovery keeps it open).
   - Recovery summary statistics calculation.
2. End-to-end integration test:
   - Canonical instrument setup and portfolio valuation snapshots.
   - Current Drawdown endpoint.
   - Maximum Drawdown endpoint.
   - Drawdown Episodes drill-down.
   - Lookback-window comparisons.
   - Recovery statistics and executive summary.
"""
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db, AsyncSessionLocal
from backend.app.modules.market_risk.drawdown_analytics.models import (
    DrawdownScopeType,
    DrawdownEpisodeStatus,
    CurrentDrawdownStatus,
)
from backend.app.modules.market_risk.drawdown_analytics.calculations.drawdown_math import (
    calculate_drawdown_series,
    calculate_recovery_summary_statistics,
)
from backend.app.modules.portfolio_management.portfolio_history.models import PortfolioBookSnapshot
from backend.app.modules.instrument_reference_data.instrument_master.services.service import (
    InstrumentMasterService,
)
from backend.app.modules.instrument_reference_data.instrument_master.schemas import InstrumentCreateRequest


def test_drawdown_mathematical_units():
    """
    Test synthetic value path:
    Day 0: 100 (HWM 100, DD 0)
    Day 1: 90  (HWM 100, DD 10%, trough)
    Day 2: 95  (HWM 100, DD 5%, partial recovery)
    Day 3: 105 (HWM 105, DD 0%, recovered Episode 1)
    Day 4: 84  (HWM 105, DD 20%, trough Episode 2)
    Day 5: 100 (HWM 105, DD 4.76%, ongoing Episode 2)
    """
    base_dt = datetime(2026, 1, 1, 16, 0, tzinfo=timezone.utc)
    obs = [
        (base_dt + timedelta(days=0), Decimal("100.00")),
        (base_dt + timedelta(days=1), Decimal("90.00")),
        (base_dt + timedelta(days=2), Decimal("95.00")),
        (base_dt + timedelta(days=3), Decimal("105.00")),
        (base_dt + timedelta(days=4), Decimal("84.00")),
        (base_dt + timedelta(days=5), Decimal("100.00")),
    ]

    pts, episodes, mdd = calculate_drawdown_series(observations=obs)

    # 1. Total points
    assert len(pts) == 6

    # Point 1 (Day 1): 10% drawdown
    assert pts[1]["running_high_water_mark"] == Decimal("100.00")
    assert pts[1]["drawdown_percentage"] == Decimal("10.000000")
    assert pts[1]["signed_drawdown"] == Decimal("-0.10000000")
    assert pts[1]["absolute_drawdown_amount"] == Decimal("10.00")

    # Point 3 (Day 3): New High-Water Mark 105
    assert pts[3]["running_high_water_mark"] == Decimal("105.00")
    assert pts[3]["drawdown_percentage"] == Decimal("0.0")

    # 2. Episode segmentation
    assert len(episodes) == 2

    # Episode 1: Recovered
    ep1 = episodes[0]
    assert ep1["episode_status"] == DrawdownEpisodeStatus.RECOVERED
    assert ep1["peak_value"] == Decimal("100.00")
    assert ep1["trough_value"] == Decimal("90.00")
    assert ep1["drawdown_percentage"] == Decimal("10.000000")
    assert ep1["recovery_value"] == Decimal("105.00")
    assert ep1["peak_to_trough_days"] == 1
    assert ep1["trough_to_recovery_days"] == 2
    assert ep1["underwater_duration_days"] == 3

    # Episode 2: Ongoing (right-censored)
    ep2 = episodes[1]
    assert ep2["episode_status"] == DrawdownEpisodeStatus.ONGOING
    assert ep2["peak_value"] == Decimal("105.00")
    assert ep2["trough_value"] == Decimal("84.00")
    assert ep2["drawdown_percentage"] == Decimal("20.000000")
    assert ep2["recovery_timestamp"] is None
    assert ep2["trough_to_recovery_days"] is None
    assert ep2["underwater_duration_days"] == 2

    # 3. Maximum Drawdown
    assert mdd["maximum_drawdown_percentage"] == Decimal("20.000000")
    assert mdd["maximum_drawdown_amount"] == Decimal("21.00")  # 105 - 84
    assert mdd["trough_value"] == Decimal("84.00")

    # 4. Recovery summary statistics
    stats = calculate_recovery_summary_statistics(episodes=episodes, as_of_dt=date(2026, 1, 6))
    assert stats["total_episodes_count"] == 2
    assert stats["completed_episodes_count"] == 1
    assert stats["ongoing_episodes_count"] == 1
    assert stats["longest_recovery_days"] == 2
    assert stats["average_recovery_days"] == Decimal("2.00")


@pytest.mark.asyncio
async def test_portfolio_drawdown_analytics_integration():
    """
    End-to-end integration test:
    1. Initialize database and seed PortfolioBookSnapshot records.
    2. Query GET /portfolios/{portfolio_id}/risk/drawdown (Executive Summary).
    3. Query GET /market-risk/drawdown/current.
    4. Query GET /market-risk/drawdown/maximum.
    5. Query GET /market-risk/drawdown/episodes.
    6. Query GET /market-risk/drawdown/comparison (Lookback windows).
    """
    await init_db()
    ts = datetime.utcnow().timestamp()
    port_id = f"port-drawdown-test-{ts}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Seed historical portfolio book snapshots
        async with AsyncSessionLocal() as session:
            base_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
            navs = [
                100000, 98000, 92000, 88000, 94000, 102000,
                101000, 95000, 85000, 89000, 96000, 105000,
                103000, 99000
            ]
            for idx, nav_val in enumerate(navs):
                snap = PortfolioBookSnapshot(
                    snapshot_id=f"SNAP_DD_{ts}_{idx}",
                    portfolio_id=port_id,
                    effective_as_of=base_date + timedelta(days=idx),
                    knowledge_as_of=base_date + timedelta(days=idx),
                    base_currency="USD",
                    total_positions_count=2,
                    total_market_value_base=Decimal(str(nav_val)),
                    total_cash_value_base=Decimal("0.0"),
                    total_nav_base=Decimal(str(nav_val)),
                    snapshot_hash=f"dd_hash_{idx}",
                )
                session.add(snap)
            await session.commit()

        # 2. Executive Summary endpoint
        r_sum = await client.get(f"/api/v1/portfolios/{port_id}/risk/drawdown")
        assert r_sum.status_code == 200, r_sum.text
        sum_data = r_sum.json()
        assert sum_data["portfolio_id"] == port_id
        assert Decimal(sum_data["maximum_drawdown_percentage"]) > Decimal("10.0")
        assert Decimal(sum_data["current_drawdown_percentage"]) > Decimal("0.0")
        assert sum_data["current_status"] == "CURRENTLY_UNDERWATER"
        assert sum_data["total_episodes_count"] >= 2

        # 3. Current Drawdown endpoint
        r_curr = await client.get(
            f"/api/v1/market-risk/drawdown/current?scope_type=PORTFOLIO&portfolio_id={port_id}"
        )
        assert r_curr.status_code == 200, r_curr.text
        curr_data = r_curr.json()
        assert curr_data["portfolio_id"] == port_id
        assert Decimal(curr_data["latest_value"]) == Decimal("99000.00")
        assert Decimal(curr_data["running_high_water_mark"]) == Decimal("105000.00")
        # (105000 - 99000) / 105000 = 6000 / 105000 = 5.714286%
        assert abs(Decimal(curr_data["current_drawdown_percentage"]) - Decimal("5.714286")) < Decimal("0.001")

        # 4. Maximum Drawdown endpoint
        r_mdd = await client.get(
            f"/api/v1/market-risk/drawdown/maximum?scope_type=PORTFOLIO&portfolio_id={port_id}"
        )
        assert r_mdd.status_code == 200, r_mdd.text
        mdd_data = r_mdd.json()
        assert mdd_data["portfolio_id"] == port_id
        # Peak 102k -> Trough 85k = 17k / 102k = 16.666667%
        assert Decimal(mdd_data["maximum_drawdown_percentage"]) >= Decimal("16.0")
        assert Decimal(mdd_data["maximum_drawdown_amount"]) >= Decimal("17000.00")

        # 5. Episodes endpoint
        r_ep = await client.get(
            f"/api/v1/market-risk/drawdown/episodes?scope_type=PORTFOLIO&portfolio_id={port_id}"
        )
        assert r_ep.status_code == 200, r_ep.text
        ep_list = r_ep.json()
        assert len(ep_list) >= 2
        # Check that first ranked episode has deepest drawdown
        assert Decimal(ep_list[0]["drawdown_percentage"]) >= Decimal(ep_list[1]["drawdown_percentage"])

        # 6. Lookback comparison endpoint
        r_comp = await client.get(
            f"/api/v1/market-risk/drawdown/comparison?scope_type=PORTFOLIO&portfolio_id={port_id}"
        )
        assert r_comp.status_code == 200, r_comp.text
        comp_data = r_comp.json()
        assert len(comp_data["windows"]) >= 4
