"""
Integration, statistical, and operational test suite for M13.06 — Liquidity Dashboard.

Validates:
1. Spread intelligence & quotes (absolute, relative, bps, ticks, locked/crossed state detection).
2. Order-book depth ladders (bids descending, asks ascending, cumulative notional, imbalance).
3. Composite liquidity scoring (components: spread, depth, turnover, impact, slippage).
4. Position liquidation modeling (long sale vs short covering, multi-target scenarios 10%-100%, cost decomposition).
5. Portfolio liquidity overview aggregation (weighted scores, weighted spread bps, total liquidation cost).
6. User preferences, saved views, and investigation note persistence.
7. REST API endpoint contracts.
"""

from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.main import app
from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument
from backend.app.modules.portfolio_management.portfolio_creation.models import (
    Portfolio,
    PortfolioLifecycleStatus,
    PortfolioTypeEnum,
    CreationSourceEnum,
    MarketScopeEnum,
)
from backend.app.modules.portfolio_management.position_management.models import (
    PositionBook,
    PositionStatus,
    PositionSide,
)
from backend.app.modules.portfolio_management.position_valuation.models import (
    PositionValuation,
    ValuationStatus,
    MarkPriceType,
)
from backend.app.modules.market_microstructure.bid_ask_spread.models import SpreadObservation
from backend.app.modules.market_microstructure.order_book_depth.models import (
    OrderBookDepthSnapshot,
    OrderBookDepthLevel,
)
from backend.app.modules.market_microstructure.liquidity_estimation.models import (
    LiquidityScoreSnapshot,
    LiquidityVolumeAggregate,
    LiquidityTurnoverAggregate,
)
from backend.app.modules.dashboard_visualization.liquidity_dashboard.services.liquidity_dashboard_service import (
    LiquidityDashboardService,
)
from backend.app.modules.dashboard_visualization.liquidity_dashboard.schemas.liquidity_dashboard_schemas import (
    PreferenceCreateRequest,
    SavedViewCreateRequest,
    InvestigationCreateRequest,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()
    yield


@pytest.mark.asyncio
async def test_liquidity_dashboard_services_and_analytics():
    """Verifies spread, depth, scoring, liquidation, and portfolio overview services."""
    suffix = uuid.uuid4().hex[:6]
    inst_id = f"INST_LIQ_{suffix}"
    symbol = f"LQ{suffix[:4].upper()}"
    port_id = f"PORT_LIQ_{suffix}"

    async with AsyncSessionLocal() as session:
        # 1. Create instrument
        inst = Instrument(
            instrument_id=inst_id,
            canonical_name=f"Liquidity Test Asset {suffix}",
            short_name=symbol,
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            issue_currency="USD",
        )
        session.add(inst)

        # 2. Create Portfolio
        portfolio = Portfolio(
            portfolio_id=port_id,
            portfolio_code=port_id,
            portfolio_name="Institutional Liquidity Test Fund",
            short_name="Liq Fund",
            base_currency="USD",
            lifecycle_status=PortfolioLifecycleStatus.ACTIVE,
            portfolio_type=PortfolioTypeEnum.DISCRETIONARY,
            creation_source=CreationSourceEnum.MANUAL_ADMINISTRATION,
            market_scope=MarketScopeEnum.UNITED_STATES,
            created_by="TEST_ADMIN",
        )
        session.add(portfolio)

        # 3. Add position in portfolio (Long 20,000 shares)
        pos = PositionBook(
            position_id=f"POS_{suffix}",
            portfolio_id=port_id,
            account_id="ACC_01",
            instrument_id=inst_id,
            position_side=PositionSide.LONG,
            position_status=PositionStatus.ACTIVE,
            current_snapshot_version=1,
        )
        session.add(pos)

        pos_val = PositionValuation(
            valuation_id=f"VAL_{suffix}",
            calculation_id=f"CALC_{suffix}",
            portfolio_id=port_id,
            account_id="ACC_01",
            instrument_id=inst_id,
            position_side=PositionSide.LONG,
            signed_quantity=Decimal("20000.0"),
            mark_price=Decimal("150.00"),
            mark_price_type=MarkPriceType.MID_PRICE,
            price_currency="USD",
            fx_rate_to_base=Decimal("1.0"),
            signed_market_value_native=Decimal("3000000.00"),
            signed_market_value_base=Decimal("3000000.00"),
            signed_cost_basis_native=Decimal("2900000.00"),
            signed_cost_basis_base=Decimal("2900000.00"),
            unrealized_pnl_native=Decimal("100000.00"),
            unrealized_pnl_base=Decimal("100000.00"),
            valuation_status=ValuationStatus.VALUED,
            effective_at=datetime.utcnow(),
            calculated_at=datetime.utcnow(),
        )
        session.add(pos_val)

        # 4. Add Spread Observations (Recent and Historical)
        now = utc_now()
        obs_current = SpreadObservation(
            observation_id=f"SO_{suffix}_1",
            instrument_id=inst_id,
            exchange="NASDAQ",
            venue="NASDAQ",
            source_feed_id="FEED_01",
            book_timestamp=now,
            bid_price=Decimal("150.00"),
            ask_price=Decimal("150.05"),
            midpoint_price=Decimal("150.025"),
            absolute_spread=Decimal("0.05"),
            relative_spread_decimal=Decimal("0.000333"),
            relative_spread_bps=Decimal("3.33"),
            spread_ticks=Decimal("5.0"),
            tick_size_reference=Decimal("0.01"),
            bid_timestamp=now,
            ask_timestamp=now,
            calculation_config_id="CFG_01",
        )
        obs_historical = SpreadObservation(
            observation_id=f"SO_{suffix}_2",
            instrument_id=inst_id,
            exchange="NASDAQ",
            venue="NASDAQ",
            source_feed_id="FEED_01",
            book_timestamp=now - timedelta(days=5),
            bid_price=Decimal("148.00"),
            ask_price=Decimal("148.10"),
            midpoint_price=Decimal("148.05"),
            absolute_spread=Decimal("0.10"),
            relative_spread_decimal=Decimal("0.000675"),
            relative_spread_bps=Decimal("6.75"),
            spread_ticks=Decimal("10.0"),
            tick_size_reference=Decimal("0.01"),
            bid_timestamp=now - timedelta(days=5),
            ask_timestamp=now - timedelta(days=5),
            calculation_config_id="CFG_01",
        )
        session.add_all([obs_current, obs_historical])

        # 5. Add Order Book Depth Snapshot with Levels
        snap_id = f"SNAP_{suffix}"
        snap = OrderBookDepthSnapshot(
            depth_snapshot_id=snap_id,
            instrument_id=inst_id,
            exchange="NASDAQ",
            venue="NASDAQ",
            source_feed_id="FEED_01",
            event_timestamp=now,
            best_bid_price=Decimal("150.00"),
            best_ask_price=Decimal("150.05"),
            midpoint_price=Decimal("150.025"),
            bid_total_quantity=Decimal("3500.0"),
            ask_total_quantity=Decimal("4000.0"),
            bid_total_notional=Decimal("525000.0"),
            ask_total_notional=Decimal("600200.0"),
            quantity_imbalance=Decimal("-0.0667"),
            calculation_config_id="CFG_01",
        )
        session.add(snap)

        levels = [
            # Bids
            OrderBookDepthLevel(
                level_id=f"LVL_{suffix}_B1",
                depth_snapshot_id=snap_id,
                side="BID",
                level_index=1,
                price=Decimal("150.00"),
                displayed_quantity=Decimal("1000.0"),
                displayed_notional=Decimal("150000.0"),
                cumulative_quantity=Decimal("1000.0"),
                cumulative_notional=Decimal("150000.0"),
                distance_bps=Decimal("1.67"),
                order_count=5,
            ),
            OrderBookDepthLevel(
                level_id=f"LVL_{suffix}_B2",
                depth_snapshot_id=snap_id,
                side="BID",
                level_index=2,
                price=Decimal("149.95"),
                displayed_quantity=Decimal("2500.0"),
                displayed_notional=Decimal("374875.0"),
                cumulative_quantity=Decimal("3500.0"),
                cumulative_notional=Decimal("524875.0"),
                distance_bps=Decimal("5.0"),
                order_count=8,
            ),
            # Asks
            OrderBookDepthLevel(
                level_id=f"LVL_{suffix}_A1",
                depth_snapshot_id=snap_id,
                side="ASK",
                level_index=1,
                price=Decimal("150.05"),
                displayed_quantity=Decimal("1500.0"),
                displayed_notional=Decimal("225075.0"),
                cumulative_quantity=Decimal("1500.0"),
                cumulative_notional=Decimal("225075.0"),
                distance_bps=Decimal("1.67"),
                order_count=6,
            ),
            OrderBookDepthLevel(
                level_id=f"LVL_{suffix}_A2",
                depth_snapshot_id=snap_id,
                side="ASK",
                level_index=2,
                price=Decimal("150.10"),
                displayed_quantity=Decimal("2500.0"),
                displayed_notional=Decimal("375250.0"),
                cumulative_quantity=Decimal("4000.0"),
                cumulative_notional=Decimal("600325.0"),
                distance_bps=Decimal("5.0"),
                order_count=10,
            ),
        ]
        session.add_all(levels)

        # 6. Add Liquidity Score Snapshot & Aggregates
        score_snap = LiquidityScoreSnapshot(
            snapshot_id=f"LSS_{suffix}",
            instrument_id=inst_id,
            exchange="NASDAQ",
            venue="NASDAQ",
            as_of_timestamp=now,
            score_config_code="STANDARD",
            composite_liquidity_score=82.5,
            spread_subscore=88.0,
            depth_subscore=80.0,
            turnover_subscore=85.0,
            availability_subscore=82.0,
            spread_coverage=1.0,
        )
        vol_agg = LiquidityVolumeAggregate(
            aggregate_id=f"LVA_{suffix}",
            instrument_id=inst_id,
            exchange="NASDAQ",
            venue="NASDAQ",
            aggregation_start=now - timedelta(days=1),
            aggregation_end=now,
            aggregation_interval="1d",
            traded_volume=Decimal("500000.0"),
            eligible_trade_count=1200,
        )
        to_agg = LiquidityTurnoverAggregate(
            aggregate_id=f"LTA_{suffix}",
            instrument_id=inst_id,
            exchange="NASDAQ",
            venue="NASDAQ",
            aggregation_start=now - timedelta(days=1),
            aggregation_end=now,
            aggregation_interval="1d",
            turnover_amount=Decimal("75000000.0"),
            currency="USD",
            eligible_trade_count=1200,
        )
        session.add_all([score_snap, vol_agg, to_agg])
        await session.commit()

    # --- Run Verification Services ---
    async with AsyncSessionLocal() as session:
        service = LiquidityDashboardService(session)

        # --- Test 1: Spread & Quote Retrieval ---
        quote = await service.get_current_quote(inst_id)
        assert quote.instrument_id == inst_id
        assert quote.symbol == symbol
        assert quote.best_bid == Decimal("150.00")
        assert quote.best_ask == Decimal("150.05")
        assert quote.spread_abs == Decimal("0.05")
        assert quote.spread_bps == Decimal("3.33")
        assert quote.quote_condition == "NORMAL"

        spread_detail = await service.get_instrument_spread_detail(inst_id, lookback_days=30)
        assert len(spread_detail.historical_series) == 2
        assert spread_detail.avg_spread_bps_30d is not None
        assert spread_detail.min_spread_bps_30d == Decimal("3.33")
        assert spread_detail.max_spread_bps_30d == Decimal("6.75")

        # --- Test 2: Order Book Depth Ladder ---
        ladder = await service.get_order_book_depth_ladder(inst_id, levels_count=5)
        assert ladder.instrument_id == inst_id
        assert len(ladder.bids) == 2
        assert len(ladder.asks) == 2
        assert ladder.bids[0].price == Decimal("150.00")
        assert ladder.bids[1].price == Decimal("149.95")
        assert ladder.asks[0].price == Decimal("150.05")
        assert ladder.asks[1].price == Decimal("150.10")
        assert ladder.total_bid_quantity == Decimal("3500.0")
        assert ladder.total_ask_quantity == Decimal("4000.0")
        assert len(ladder.cumulative_bid_notional) == 2
        assert ladder.depth_imbalance is not None
        assert ladder.depth_imbalance < Decimal("0")  # Asks > Bids

        # --- Test 3: Composite Liquidity Score & Decomposition ---
        score = await service.get_instrument_liquidity_score(inst_id)
        assert score.instrument_id == inst_id
        assert score.composite_score == Decimal("82.5")
        assert score.liquidity_bucket == "TIER_1_HIGH"
        assert len(score.components) == 5

        # --- Test 4: Position Liquidation Scenarios ---
        liq_prof = await service.get_instrument_liquidation_profile(
            inst_id, portfolio_id=port_id, participation_rate=Decimal("0.10")
        )
        assert liq_prof.instrument_id == inst_id
        assert liq_prof.position_direction == "LONG"
        assert liq_prof.liquidation_direction == "SELL"
        assert len(liq_prof.scenarios) == 6
        full_scen = liq_prof.scenarios[-1]
        assert full_scen.target_percentage == Decimal("1.00")
        assert full_scen.shares_to_liquidate == Decimal("20000.0")
        assert full_scen.spread_cost_bps > Decimal("0")
        assert full_scen.market_impact_cost_bps > Decimal("0")
        assert full_scen.slippage_cost_bps > Decimal("0")
        assert full_scen.total_cost_bps == (
            full_scen.spread_cost_bps + full_scen.market_impact_cost_bps + full_scen.slippage_cost_bps
        )
        assert full_scen.total_cost_usd > Decimal("0")
        assert full_scen.estimated_duration_minutes > Decimal("0")

        # --- Test 5: Portfolio Overview Summary ---
        port_summary = await service.get_portfolio_liquidity_overview(port_id)
        assert port_summary.portfolio_id == port_id
        assert port_summary.holdings_count >= 1
        assert port_summary.total_nav > Decimal("0")
        assert port_summary.weighted_composite_score > Decimal("0")
        assert port_summary.weighted_spread_bps > Decimal("0")
        assert port_summary.portfolio_liquidation_cost_bps > Decimal("0")


@pytest.mark.asyncio
async def test_liquidity_dashboard_persistence_and_api():
    """Verifies preferences, saved views, investigations, and API router endpoints."""
    user_id = f"user_{uuid.uuid4().hex[:6]}"
    inst_id = f"INST_API_{uuid.uuid4().hex[:6]}"

    async with AsyncSessionLocal() as session:
        inst = Instrument(
            instrument_id=inst_id,
            canonical_name="API Test Stock",
            short_name="APITEST",
            instrument_type="COMMON_STOCK",
            asset_class="EQUITY",
            issue_currency="USD",
        )
        session.add(inst)
        await session.commit()

    async with AsyncSessionLocal() as session:
        service = LiquidityDashboardService(session)

        # 1. Preferences persistence
        pref_req = PreferenceCreateRequest(
            dashboard_name="Trading Desk Liquidity",
            spread_unit="BPS",
            depth_levels_count=10,
            default_lookback_days=45,
            default_participation_rate=Decimal("0.15"),
        )
        pref = await service.update_user_preferences(user_id=user_id, req=pref_req)
        assert pref.depth_levels_count == 10
        assert pref.default_lookback_days == 45
        assert pref.default_participation_rate == Decimal("0.15")

        # 2. Saved View persistence
        view_req = SavedViewCreateRequest(
            view_name="High Spread Watchlist",
            description="Monitoring large spreads",
            filters={"min_spread_bps": 20.0},
            selected_instrument_ids=[inst_id],
            is_public=True,
        )
        view = await service.create_saved_view(user_id=user_id, req=view_req)
        assert view.id.startswith("lview_")
        assert view.view_name == "High Spread Watchlist"

        views = await service.list_saved_views(user_id=user_id)
        assert len(views) >= 1

        # 3. Investigation note persistence
        inv_req = InvestigationCreateRequest(
            instrument_id=inst_id,
            investigation_type="SPREAD_BLOWOUT",
            severity="HIGH",
            title="Unexpected Spread Widening",
            notes="Spread jumped to 35 bps around market open.",
            metrics_snapshot={"spread_bps": 35.0},
        )
        inv = await service.create_investigation(user_id=user_id, req=inv_req)
        assert inv.id.startswith("linv_")
        assert inv.status == "OPEN"
        assert inv.severity == "HIGH"

        invs = await service.list_investigations(instrument_id=inst_id)
        assert len(invs) == 1

    # 4. HTTP API Endpoints via AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Quote endpoint
        resp = await ac.get(f"/api/v1/dashboard/liquidity/instrument/{inst_id}/quote")
        assert resp.status_code == 200
        quote_data = resp.json()
        assert quote_data["instrument_id"] == inst_id

        # Spread endpoint
        resp = await ac.get(f"/api/v1/dashboard/liquidity/instrument/{inst_id}/spread?lookback_days=15")
        assert resp.status_code == 200
        spread_data = resp.json()
        assert spread_data["instrument_id"] == inst_id

        # Depth endpoint
        resp = await ac.get(f"/api/v1/dashboard/liquidity/instrument/{inst_id}/depth?levels=5")
        assert resp.status_code == 200
        depth_data = resp.json()
        assert depth_data["instrument_id"] == inst_id

        # Score endpoint
        resp = await ac.get(f"/api/v1/dashboard/liquidity/instrument/{inst_id}/score")
        assert resp.status_code == 200
        score_data = resp.json()
        assert "composite_score" in score_data

        # Liquidation endpoint
        resp = await ac.get(
            f"/api/v1/dashboard/liquidity/instrument/{inst_id}/liquidation?participation_rate=0.10"
        )
        assert resp.status_code == 200
        liq_data = resp.json()
        assert len(liq_data["scenarios"]) == 6

        # Preferences API
        resp = await ac.get(f"/api/v1/dashboard/liquidity/preferences?user_id={user_id}&dashboard_name=Trading Desk Liquidity")
        assert resp.status_code == 200
        assert resp.json()["depth_levels_count"] == 10

        # Saved Views API
        resp = await ac.get(f"/api/v1/dashboard/liquidity/saved-views?user_id={user_id}")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

        # Investigations API
        resp = await ac.get(f"/api/v1/dashboard/liquidity/investigations?instrument_id={inst_id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
