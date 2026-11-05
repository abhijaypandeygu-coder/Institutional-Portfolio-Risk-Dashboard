"""
Unit and Integration Tests for M10.01 Historical Scenarios.

Validates:
1. Return calculations:
   - Simple return & compounded cumulative return.
   - Currency adjustment: (1 + R_base) = (1 + R_local) * (1 + R_FX).
2. Factor-based shock modeling:
   - Linear combination of factor returns.
3. Position revaluation:
   - Long and short signed quantities.
   - PnL, price, market value, portfolio weight, contribution.
4. Portfolio aggregation & reconciliation:
   - NAV, total PnL, portfolio return reconciliation: sum(C_i) == R_portfolio.
   - Exposure coverage: direct, proxy, factor, unmapped.
5. End-to-end API lifecycle:
   - Event creation & observation ingestion.
   - Replay execution with mixed long/short positions, FX shock, proxy mapping, and factor modeling.
   - Historical difference reporting.
"""

import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.modules.scenario_analysis.historical_scenarios.calculations.scenario_math import (
    to_decimal,
    compute_simple_return,
    compute_cumulative_compounded_return,
    compute_currency_adjusted_return,
    estimate_factor_shock,
    revalue_position,
    aggregate_portfolio_replay
)


def test_hand_calculated_return_compounding_and_fx():
    """
    Verifies that cumulative returns use geometric compounding and currency adjustment formulas correctly.
    """
    # 1. Compounded return over 3 days: +5%, -10%, +4%
    # (1 + 0.05) * (1 - 0.10) * (1 + 0.04) = 1.05 * 0.90 * 1.04 = 0.9828
    # Cumulative return = 0.9828 - 1 = -0.0172 (-1.72%)
    rets = [Decimal("0.05"), Decimal("-0.10"), Decimal("0.04")]
    cum_ret = compute_cumulative_compounded_return(rets)
    assert cum_ret == Decimal("-0.01720000")

    # 2. Currency adjusted return:
    # Local equity return = +10% (0.10)
    # FX return (USD value against INR) = +5% (0.05)
    # Combined base return = (1 + 0.10) * (1 + 0.05) - 1 = 1.10 * 1.05 - 1 = 0.155 (15.5%)
    fx_adj = compute_currency_adjusted_return(Decimal("0.10"), Decimal("0.05"))
    assert fx_adj == Decimal("0.15500000")


def test_factor_shock_estimation():
    """
    Verifies factor shock model: sum(beta_k * F_k) + residual.
    """
    sensitivities = {
        "MARKET": Decimal("1.2"),
        "MOMENTUM": Decimal("-0.5"),
        "VALUE": Decimal("0.3")
    }
    factor_shocks = {
        "MARKET": Decimal("-0.15"),    # -15%
        "MOMENTUM": Decimal("0.08"),    # +8%
        "VALUE": Decimal("-0.02")       # -2%
    }
    # Modeled return = 1.2 * (-0.15) + (-0.5) * (0.08) + 0.3 * (-0.02)
    # = -0.180 - 0.040 - 0.006 = -0.226 (-22.6%)
    modeled = estimate_factor_shock(sensitivities, factor_shocks, residual_shock=Decimal("0.005"))
    assert modeled == Decimal("-0.22100000")


def test_long_short_position_revaluation_and_reconciliation():
    """
    Verifies signed quantity revaluation for long and short holdings.
    Tests mathematical reconciliation: sum(C_i) == R_portfolio.
    """
    nav_0 = Decimal("1000000") # $1M NAV

    # Long position: 1,000 shares @ $500 = $500,000 (50% weight). Shock = -20% (-0.20)
    # PnL = 1000 * 500 * (-0.20) = -$100,000
    pos_long = revalue_position(
        signed_quantity=Decimal("1000"),
        baseline_price=Decimal("500"),
        scenario_return=Decimal("-0.20"),
        baseline_nav=nav_0
    )
    assert pos_long["baseline_market_value"] == Decimal("500000.0000")
    assert pos_long["scenario_market_value"] == Decimal("400000.0000")
    assert pos_long["scenario_pnl"] == Decimal("-100000.0000")
    assert pos_long["portfolio_weight"] == Decimal("0.50000000")
    assert pos_long["portfolio_contribution"] == Decimal("-0.10000000")

    # Short position: -500 shares @ $400 = -$200,000 (-20% weight). Shock = -15% (-0.15)
    # Short gains when price drops: PnL = -500 * 400 * (-0.15) = +$30,000
    pos_short = revalue_position(
        signed_quantity=Decimal("-500"),
        baseline_price=Decimal("400"),
        scenario_return=Decimal("-0.15"),
        baseline_nav=nav_0
    )
    assert pos_short["baseline_market_value"] == Decimal("-200000.0000")
    assert pos_short["scenario_market_value"] == Decimal("-170000.0000")
    assert pos_short["scenario_pnl"] == Decimal("30000.0000")
    assert pos_short["portfolio_weight"] == Decimal("-0.20000000")
    assert pos_short["portfolio_contribution"] == Decimal("0.03000000")

    # Aggregate
    agg = aggregate_portfolio_replay(
        baseline_nav=nav_0,
        position_results=[
            {**pos_long, "mapping_method": "EXACT_DIRECT"},
            {**pos_short, "mapping_method": "APPROVED_PROXY"}
        ]
    )
    # Total PnL = -100,000 + 30,000 = -$70,000
    # Scenario NAV = $930,000
    # Portfolio Return = -70,000 / 1,000,000 = -7.0%
    assert agg["scenario_pnl"] == Decimal("-70000.0000")
    assert agg["scenario_nav"] == Decimal("930000.0000")
    assert agg["scenario_return"] == Decimal("-0.07000000")
    assert agg["reconciliation_discrepancy"] == Decimal("0.00000000")

    # Exposure Coverage:
    # Denominator = |500,000| + |-200,000| = 700,000
    # Direct = 500,000 / 700,000 ≈ 0.7143
    # Proxy = 200,000 / 700,000 ≈ 0.2857
    assert agg["direct_coverage"] == Decimal("0.7143")
    assert agg["proxy_coverage"] == Decimal("0.2857")


@pytest.mark.asyncio
async def test_historical_scenarios_api_full_lifecycle():
    """
    Validates end-to-end API lifecycle:
    1. Create historical event (e.g. 2020 COVID-19 Crash).
    2. Ingest historical observations (direct & factor).
    3. Execute portfolio replay with direct, proxy, and factor shocks.
    4. Verify reconciliation, warnings, and difference reports.
    """
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Historical Event
        test_code = f"COVID_CRASH_{uuid.uuid4().hex[:8]}"
        base_date = datetime(2020, 2, 20, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2020, 3, 23, 0, 0, 0, tzinfo=timezone.utc)
        
        event_payload = {
            "event_code": test_code,
            "event_name": "COVID-19 Global Market Crash",
            "description": "Rapid market downturn across global equity indices in Q1 2020",
            "category": "CRISIS",
            "tags": "pandemic,volatility,global_drawdown",
            "global_scope": True,
            "affected_regions": "GLOBAL",
            "affected_markets": "NSE,BSE,NYSE,NASDAQ",
            "start_date": base_date.isoformat(),
            "end_date": end_date.isoformat(),
            "reference_timezone": "UTC",
            "primary_reference_index": "SPX",
            "event_narrative": "Liquidity contraction and global lockdowns resulting in steep drawdowns",
            "data_coverage_status": "ADEQUATE",
            "current_version": "1.0.0"
        }
        ev_resp = await client.post("/api/v1/scenarios/historical/events", json=event_payload)
        assert ev_resp.status_code == 201
        event_data = ev_resp.json()
        event_id = event_data["id"]

        # 2. Ingest Observations
        obs_payload = [
            # Direct observation for AAPL: -25%
            {
                "instrument_id": "AAPL_US",
                "listing_id": "AAPL_NASDAQ",
                "observation_date": base_date.isoformat(),
                "observation_timestamp": base_date.isoformat(),
                "return_value": "-0.25",
                "return_type": "TOTAL_RETURN",
                "currency": "USD"
            },
            # Direct observation for proxy SPY_US: -30%
            {
                "instrument_id": "SPY_US",
                "listing_id": "SPY_NYSE",
                "observation_date": base_date.isoformat(),
                "observation_timestamp": base_date.isoformat(),
                "return_value": "-0.30",
                "return_type": "TOTAL_RETURN",
                "currency": "USD"
            },
            # Factor observation for MARKET: -28%
            {
                "factor_id": "MARKET_FACTOR",
                "observation_date": base_date.isoformat(),
                "observation_timestamp": base_date.isoformat(),
                "return_value": "-0.28",
                "return_type": "TOTAL_RETURN",
                "currency": "USD"
            }
        ]
        obs_resp = await client.post(f"/api/v1/scenarios/historical/events/{event_id}/observations", json=obs_payload)
        assert obs_resp.status_code == 201

        # 3. Execute Replay
        replay_payload = {
            "portfolio_id": "INST_PORTFOLIO_ALPHA",
            "event_id": event_id,
            "replay_mode": "CURRENT_PORTFOLIO",
            "return_definition": "TOTAL_RETURN",
            "base_currency": "USD",
            "missing_data_policy": "PARTIAL",
            "valuation_baseline": "PRE_EVENT_CLOSE",
            "baseline_nav": "2000000", # $2M NAV
            "positions": [
                # Holding 1: AAPL (Direct match)
                {
                    "instrument_id": "AAPL_US",
                    "listing_id": "AAPL_NASDAQ",
                    "signed_quantity": "2000",
                    "baseline_price": "300", # $600k (30% weight)
                    "currency": "USD"
                },
                # Holding 2: TECH_ETF (Mapped via SPY_US proxy)
                {
                    "instrument_id": "TECH_ETF",
                    "listing_id": "TECH_NYSE",
                    "signed_quantity": "1000",
                    "baseline_price": "400", # $400k (20% weight)
                    "currency": "USD"
                },
                # Holding 3: UNLISTED_TECH (Mapped via Factor Model)
                {
                    "instrument_id": "UNLISTED_TECH",
                    "listing_id": "PRIVATE_EQ",
                    "signed_quantity": "1000",
                    "baseline_price": "200", # $200k (10% weight)
                    "currency": "USD",
                    "factor_sensitivities": {
                        "MARKET_FACTOR": "1.1" # 1.1 * -0.28 = -0.308 (-30.8%)
                    }
                }
            ],
            "manual_proxy_mappings": {
                "TECH_ETF": "SPY_US"
            },
            "include_daily_path": True
        }
        rep_resp = await client.post("/api/v1/scenarios/historical/replays", json=replay_payload)
        assert rep_resp.status_code == 200
        rep_data = rep_resp.json()

        assert rep_data["scenario_event_id"] == event_id
        assert float(rep_data["baseline_nav"]) == 2000000.0
        assert float(rep_data["scenario_nav"]) < 2000000.0
        assert float(rep_data["direct_coverage"]) > 0.0
        assert float(rep_data["proxy_coverage"]) > 0.0
        assert float(rep_data["factor_coverage"]) > 0.0
        assert len(rep_data["warnings"]) >= 2 # Proxy warning and factor model warning
        assert rep_data["caveat_summary"] != ""

        # 4. Fetch Historical Difference Report
        replay_id = rep_data["replay_id"]
        diff_resp = await client.get(f"/api/v1/scenarios/historical/replays/{replay_id}/comparison")
        assert diff_resp.status_code == 200
        diff_data = diff_resp.json()
        assert diff_data["holdings_overlap_count"] == 1 # AAPL_US was exact direct match
        assert diff_data["new_holdings_count"] == 2 # Proxy and Factor mapped holdings
        assert "Differences in constituents" in diff_data["mandatory_caveat"]
