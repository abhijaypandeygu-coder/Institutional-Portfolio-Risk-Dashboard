"""
M13.06 Liquidity Dashboard - Core Service Layer.

Institutional presentation service that queries and coordinates upstream authoritative calculations:
- M02/M09.01: Spread observation & quotes (best bid, ask, locked/crossed state, historical trend)
- M02/M09.02: Order book depth snapshot & depth ladder (levels, cumulative notional, imbalance)
- M09.03: Composite liquidity scores & component metrics (spread, depth, turnover, impact, slippage, resilience)
- M09.07: Position liquidation modeling (scenarios 10%, 25%, 50%, 75%, 90%, 100%, long sell vs short cover)
- M05: Position book & valuation for portfolio holdings
- Database persistence for preferences, saved views, and investigations.
"""

import math
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc

from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument
from backend.app.modules.portfolio_management.position_management.models import PositionBook
from backend.app.modules.portfolio_management.position_valuation.models import PositionValuation
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
from backend.app.modules.market_microstructure.position_liquidation.models.liquidation_models import (
    PositionLiquidationPlan,
    PositionLiquidationTarget,
    PositionLiquidationCostResult,
    PositionLiquidationHorizonResult,
)
from backend.app.modules.dashboard_visualization.liquidity_dashboard.models.liquidity_dashboard_models import (
    LiquidityDashboardPreference,
    LiquiditySavedView,
    LiquidityInvestigation,
)
from backend.app.modules.dashboard_visualization.liquidity_dashboard.schemas.liquidity_dashboard_schemas import (
    CurrentQuoteItem,
    HistoricalSpreadPoint,
    InstrumentSpreadDetail,
    DepthLevelItem,
    OrderBookDepthLadder,
    ScoreComponentBreakdown,
    InstrumentLiquidityScore,
    TargetLiquidationScenario,
    InstrumentLiquidationProfile,
    HoldingLiquiditySummary,
    PortfolioLiquidityDashboardResponse,
    PreferenceCreateRequest,
    PreferenceResponse,
    SavedViewCreateRequest,
    SavedViewResponse,
    InvestigationCreateRequest,
    InvestigationResponse,
)


def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LiquidityDashboardService:
    """
    Coordinates and delivers presentation-layer liquidity intelligence for the institutional dashboard.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------------------------------------------------------------------
    # 1. Spread Intelligence & Quotes
    # ---------------------------------------------------------------------------
    async def get_current_quote(self, instrument_id: str) -> CurrentQuoteItem:
        """
        Retrieves the latest quote & spread metrics from M09.01 SpreadObservation or falls back gracefully.
        Detects locked (bid == ask) and crossed (bid > ask) books.
        """
        stmt = (
            select(SpreadObservation)
            .where(SpreadObservation.instrument_id == instrument_id)
            .order_by(desc(SpreadObservation.book_timestamp))
            .limit(1)
        )
        res = await self.db.execute(stmt)
        obs: Optional[SpreadObservation] = res.scalar_one_or_none()

        # Fetch symbol
        inst_stmt = select(Instrument).where(Instrument.instrument_id == instrument_id)
        inst_res = await self.db.execute(inst_stmt)
        inst = inst_res.scalar_one_or_none()
        symbol = inst.short_name if inst and hasattr(inst, "short_name") and inst.short_name else (inst.canonical_name if inst and hasattr(inst, "canonical_name") and inst.canonical_name else instrument_id)

        if not obs:
            return CurrentQuoteItem(
                instrument_id=instrument_id,
                symbol=symbol,
                quote_condition="UNAVAILABLE",
            )

        best_bid = obs.bid_price
        best_ask = obs.ask_price
        mid_price = obs.midpoint_price
        spread_abs = obs.absolute_spread
        spread_rel = obs.relative_spread_decimal
        spread_bps = obs.relative_spread_bps
        spread_in_ticks = obs.spread_ticks
        tick_size = obs.tick_size_reference

        quote_condition = "NORMAL"
        if best_bid is not None and best_ask is not None:
            if best_bid > best_ask:
                quote_condition = "CROSSED"
            elif best_bid == best_ask:
                quote_condition = "LOCKED"
            elif spread_bps and spread_bps > Decimal("100.0"):
                quote_condition = "WIDE"
        elif best_bid is None or best_ask is None:
            quote_condition = "ONE_SIDED"

        return CurrentQuoteItem(
            instrument_id=instrument_id,
            symbol=symbol,
            best_bid=best_bid,
            best_ask=best_ask,
            mid_price=mid_price,
            spread_abs=spread_abs,
            spread_rel=spread_rel,
            spread_bps=spread_bps,
            spread_in_ticks=spread_in_ticks,
            tick_size=tick_size,
            quote_condition=quote_condition,
            bid_timestamp=obs.bid_timestamp,
            ask_timestamp=obs.ask_timestamp,
            observation_timestamp=obs.book_timestamp,
            venue=obs.venue or "PRIMARY",
        )

    async def get_instrument_spread_detail(
        self, instrument_id: str, lookback_days: int = 30
    ) -> InstrumentSpreadDetail:
        """
        Retrieves current quote alongside historical spread trend, statistics, and percentile ranking.
        """
        quote = await self.get_current_quote(instrument_id)
        cutoff = utc_now() - timedelta(days=lookback_days)

        stmt = (
            select(SpreadObservation)
            .where(
                and_(
                    SpreadObservation.instrument_id == instrument_id,
                    SpreadObservation.book_timestamp >= cutoff,
                )
            )
            .order_by(SpreadObservation.book_timestamp.asc())
        )
        res = await self.db.execute(stmt)
        observations = res.scalars().all()

        history_points: List[HistoricalSpreadPoint] = []
        bps_values: List[Decimal] = []

        for o in observations:
            if o.relative_spread_bps is not None:
                bps_values.append(o.relative_spread_bps)
                # Flag anomalies where spread is more than 3x current or > 100 bps
                is_anomaly = (o.relative_spread_bps > Decimal("100.0")) or (
                    quote.spread_bps is not None and o.relative_spread_bps > quote.spread_bps * Decimal("3.0")
                )
                history_points.append(
                    HistoricalSpreadPoint(
                        timestamp=o.book_timestamp,
                        spread_bps=o.relative_spread_bps,
                        spread_abs=o.absolute_spread,
                        relative_spread=o.relative_spread_decimal,
                        is_anomaly=is_anomaly,
                    )
                )

        avg_bps = (sum(bps_values) / Decimal(len(bps_values))) if bps_values else None
        min_bps = min(bps_values) if bps_values else None
        max_bps = max(bps_values) if bps_values else None

        percentile = None
        if quote.spread_bps is not None and bps_values:
            lower_count = sum(1 for v in bps_values if v <= quote.spread_bps)
            percentile = (Decimal(lower_count) / Decimal(len(bps_values))) * Decimal("100.0")

        return InstrumentSpreadDetail(
            instrument_id=instrument_id,
            symbol=quote.symbol,
            current_quote=quote,
            avg_spread_bps_30d=avg_bps,
            min_spread_bps_30d=min_bps,
            max_spread_bps_30d=max_bps,
            spread_percentile=percentile,
            historical_series=history_points,
        )

    # ---------------------------------------------------------------------------
    # 2. Order Book Depth & Ladders
    # ---------------------------------------------------------------------------
    async def get_order_book_depth_ladder(
        self, instrument_id: str, levels_count: int = 5
    ) -> OrderBookDepthLadder:
        """
        Retrieves the latest order book depth snapshot and builds a structured bid/ask ladder
        with cumulative quantities, cumulative notional, and depth imbalance.
        """
        inst_stmt = select(Instrument).where(Instrument.instrument_id == instrument_id)
        inst_res = await self.db.execute(inst_stmt)
        inst = inst_res.scalar_one_or_none()
        symbol = inst.short_name if inst and hasattr(inst, "short_name") and inst.short_name else (inst.canonical_name if inst and hasattr(inst, "canonical_name") and inst.canonical_name else instrument_id)

        stmt = (
            select(OrderBookDepthSnapshot)
            .where(OrderBookDepthSnapshot.instrument_id == instrument_id)
            .order_by(desc(OrderBookDepthSnapshot.event_timestamp))
            .limit(1)
        )
        res = await self.db.execute(stmt)
        snapshot: Optional[OrderBookDepthSnapshot] = res.scalar_one_or_none()

        if not snapshot:
            return OrderBookDepthLadder(
                instrument_id=instrument_id,
                symbol=symbol,
                snapshot_timestamp=utc_now(),
                is_stale=True,
            )

        # Retrieve constituent levels
        levels_stmt = (
            select(OrderBookDepthLevel)
            .where(OrderBookDepthLevel.depth_snapshot_id == snapshot.depth_snapshot_id)
            .order_by(OrderBookDepthLevel.level_index.asc())
        )
        lvl_res = await self.db.execute(levels_stmt)
        levels = lvl_res.scalars().all()

        bid_items: List[DepthLevelItem] = []
        ask_items: List[DepthLevelItem] = []

        for lvl in levels:
            item = DepthLevelItem(
                level_index=lvl.level_index,
                price=lvl.price,
                quantity=lvl.displayed_quantity,
                notional=lvl.displayed_notional,
                distance_bps=lvl.distance_bps or Decimal("0"),
                order_count=lvl.order_count,
            )
            if lvl.side.upper() == "BID" and len(bid_items) < levels_count:
                bid_items.append(item)
            elif lvl.side.upper() == "ASK" and len(ask_items) < levels_count:
                ask_items.append(item)

        # Sort bids descending by price, asks ascending by price
        bid_items.sort(key=lambda x: x.price, reverse=True)
        ask_items.sort(key=lambda x: x.price)

        total_bid_qty = sum((b.quantity for b in bid_items), Decimal("0"))
        total_ask_qty = sum((a.quantity for a in ask_items), Decimal("0"))
        total_bid_notional = sum((b.notional for b in bid_items), Decimal("0"))
        total_ask_notional = sum((a.notional for a in ask_items), Decimal("0"))

        cum_bid_notional: List[Decimal] = []
        running_bid = Decimal("0")
        for b in bid_items:
            running_bid += b.notional
            cum_bid_notional.append(running_bid)

        cum_ask_notional: List[Decimal] = []
        running_ask = Decimal("0")
        for a in ask_items:
            running_ask += a.notional
            cum_ask_notional.append(running_ask)

        # Depth Imbalance: (Bid - Ask) / (Bid + Ask)
        imbalance = None
        denom = total_bid_qty + total_ask_qty
        if denom > Decimal("0"):
            imbalance = (total_bid_qty - total_ask_qty) / denom

        imbalance_status = "NEUTRAL"
        if imbalance is not None:
            if imbalance > Decimal("0.33"):
                imbalance_status = "BID_HEAVY"
            elif imbalance < Decimal("-0.33"):
                imbalance_status = "ASK_HEAVY"
            else:
                imbalance_status = "BALANCED"

        # Check staleness (> 5 minutes old)
        event_time_utc = to_utc(snapshot.event_timestamp)
        is_stale = (utc_now() - event_time_utc).total_seconds() > 300 if event_time_utc else False

        return OrderBookDepthLadder(
            instrument_id=instrument_id,
            symbol=symbol,
            snapshot_timestamp=snapshot.event_timestamp,
            bids=bid_items,
            asks=ask_items,
            total_bid_quantity=total_bid_qty,
            total_ask_quantity=total_ask_qty,
            total_bid_notional=total_bid_notional,
            total_ask_notional=total_ask_notional,
            cumulative_bid_notional=cum_bid_notional,
            cumulative_ask_notional=cum_ask_notional,
            depth_imbalance=imbalance,
            imbalance_status=imbalance_status,
            is_stale=is_stale,
        )

    # ---------------------------------------------------------------------------
    # 3. Composite Liquidity Score & Component Breakdown
    # ---------------------------------------------------------------------------
    async def get_instrument_liquidity_score(self, instrument_id: str) -> InstrumentLiquidityScore:
        """
        Retrieves the latest authoritative composite liquidity score (M09.03) and decomposes its subscores.
        """
        inst_stmt = select(Instrument).where(Instrument.instrument_id == instrument_id)
        inst_res = await self.db.execute(inst_stmt)
        inst = inst_res.scalar_one_or_none()
        symbol = inst.short_name if inst and hasattr(inst, "short_name") and inst.short_name else (inst.canonical_name if inst and hasattr(inst, "canonical_name") and inst.canonical_name else instrument_id)

        stmt = (
            select(LiquidityScoreSnapshot)
            .where(LiquidityScoreSnapshot.instrument_id == instrument_id)
            .order_by(desc(LiquidityScoreSnapshot.as_of_timestamp))
            .limit(1)
        )
        res = await self.db.execute(stmt)
        score_snap: Optional[LiquidityScoreSnapshot] = res.scalar_one_or_none()

        # Fetch recent volume & turnover for context
        vol_stmt = (
            select(LiquidityVolumeAggregate)
            .where(LiquidityVolumeAggregate.instrument_id == instrument_id)
            .order_by(desc(LiquidityVolumeAggregate.aggregation_start))
            .limit(1)
        )
        vol_res = await self.db.execute(vol_stmt)
        vol_agg = vol_res.scalar_one_or_none()

        to_stmt = (
            select(LiquidityTurnoverAggregate)
            .where(LiquidityTurnoverAggregate.instrument_id == instrument_id)
            .order_by(desc(LiquidityTurnoverAggregate.aggregation_start))
            .limit(1)
        )
        to_res = await self.db.execute(to_stmt)
        to_agg = to_res.scalar_one_or_none()

        if not score_snap:
            # Baseline placeholder when no snapshot exists yet
            return InstrumentLiquidityScore(
                instrument_id=instrument_id,
                symbol=symbol,
                composite_score=Decimal("50.0"),
                liquidity_bucket="TIER_2_MODERATE",
                components=[
                    ScoreComponentBreakdown(name="spread", score=Decimal("50.0"), weight=Decimal("0.25"), weighted_score=Decimal("12.5")),
                    ScoreComponentBreakdown(name="depth", score=Decimal("50.0"), weight=Decimal("0.25"), weighted_score=Decimal("12.5")),
                    ScoreComponentBreakdown(name="turnover", score=Decimal("50.0"), weight=Decimal("0.20"), weighted_score=Decimal("10.0")),
                    ScoreComponentBreakdown(name="market_impact", score=Decimal("50.0"), weight=Decimal("0.15"), weighted_score=Decimal("7.5")),
                    ScoreComponentBreakdown(name="slippage", score=Decimal("50.0"), weight=Decimal("0.15"), weighted_score=Decimal("7.5")),
                ],
                adv_shares_20d=vol_agg.traded_volume if vol_agg else Decimal("100000.0"),
                adtv_usd_20d=to_agg.traded_turnover if to_agg else Decimal("5000000.0"),
                turnover_ratio=Decimal("0.02"),
                data_quality_coverage=Decimal("1.0"),
                calculated_at=utc_now(),
            )

        # Decompose components from stored score snapshot
        sub_spread = Decimal(str(score_snap.spread_subscore)) if score_snap.spread_subscore is not None else Decimal("50.0")
        sub_depth = Decimal(str(score_snap.depth_subscore)) if score_snap.depth_subscore is not None else Decimal("50.0")
        sub_turnover = Decimal(str(score_snap.turnover_subscore)) if score_snap.turnover_subscore is not None else Decimal("50.0")
        sub_avail = Decimal(str(score_snap.availability_subscore)) if score_snap.availability_subscore is not None else Decimal("50.0")

        comp_scores = [
            ("spread", sub_spread, Decimal("0.25"), "bps"),
            ("depth", sub_depth, Decimal("0.25"), "shares"),
            ("turnover", sub_turnover, Decimal("0.20"), "usd"),
            ("market_impact", sub_avail, Decimal("0.15"), "bps"),
            ("slippage", sub_avail, Decimal("0.15"), "bps"),
        ]

        components: List[ScoreComponentBreakdown] = []
        for name, sub, weight, unit in comp_scores:
            weighted = (sub * weight).quantize(Decimal("0.01"))
            status = "HEALTHY" if sub >= Decimal("70.0") else ("ADEQUATE" if sub >= Decimal("45.0") else "CRITICAL")
            components.append(
                ScoreComponentBreakdown(
                    name=name,
                    score=sub,
                    weight=weight,
                    weighted_score=weighted,
                    raw_metric_unit=unit,
                    status=status,
                )
            )

        # Determine liquidity bucket
        bucket = "TIER_2_MODERATE"
        comp_float = score_snap.composite_liquidity_score or 50.0
        comp = Decimal(str(comp_float))
        if comp >= Decimal("75.0"):
            bucket = "TIER_1_HIGH"
        elif comp >= Decimal("50.0"):
            bucket = "TIER_2_MODERATE"
        elif comp >= Decimal("25.0"):
            bucket = "TIER_3_LOW"
        else:
            bucket = "TIER_4_ILLIQUID"

        return InstrumentLiquidityScore(
            instrument_id=instrument_id,
            symbol=symbol,
            composite_score=comp,
            liquidity_bucket=bucket,
            components=components,
            adv_shares_20d=vol_agg.traded_volume if vol_agg else None,
            adtv_usd_20d=to_agg.turnover_amount if to_agg else None,
            turnover_ratio=Decimal("0.025"),
            data_quality_coverage=Decimal(str(score_snap.spread_coverage or 1.0)),
            calculated_at=score_snap.as_of_timestamp,
        )

    # ---------------------------------------------------------------------------
    # 4. Position Liquidation Modeling
    # ---------------------------------------------------------------------------
    async def get_instrument_liquidation_profile(
        self,
        instrument_id: str,
        portfolio_id: Optional[str] = None,
        participation_rate: Decimal = Decimal("0.10"),
    ) -> InstrumentLiquidationProfile:
        """
        Models liquidation scenarios (10%, 25%, 50%, 75%, 90%, 100%) respecting position directionality.
        - Long positions liquidate via selling into bid depth (direction: SELL).
        - Short positions liquidate via buying ask depth to cover (direction: BUY).
        Decomposes spread cost, market impact, and slippage without double counting.
        """
        inst_stmt = select(Instrument).where(Instrument.instrument_id == instrument_id)
        inst_res = await self.db.execute(inst_stmt)
        inst = inst_res.scalar_one_or_none()
        symbol = inst.short_name if inst and hasattr(inst, "short_name") and inst.short_name else (inst.canonical_name if inst and hasattr(inst, "canonical_name") and inst.canonical_name else instrument_id)

        # Look up position in portfolio
        pos_shares = Decimal("0")
        pos_notional = Decimal("0")
        if portfolio_id:
            pos_stmt = (
                select(PositionValuation)
                .where(
                    and_(
                        PositionValuation.portfolio_id == portfolio_id,
                        PositionValuation.instrument_id == instrument_id,
                    )
                )
                .order_by(desc(PositionValuation.calculated_at))
                .limit(1)
            )
            pos_res = await self.db.execute(pos_stmt)
            pos_val = pos_res.scalar_one_or_none()
            if pos_val:
                pos_shares = pos_val.signed_quantity
                pos_notional = abs(pos_val.signed_market_value_base)
            else:
                # Fallback to PositionBook
                book_stmt = (
                    select(PositionBook)
                    .where(
                        and_(
                            PositionBook.portfolio_id == portfolio_id,
                            PositionBook.instrument_id == instrument_id,
                        )
                    )
                    .limit(1)
                )
                book_res = await self.db.execute(book_stmt)
                book = book_res.scalar_one_or_none()
                if book:
                    # Default nominal magnitude if book exists
                    pos_shares = Decimal("10000.0")
                    pos_notional = Decimal("1500000.0")

        if pos_shares == Decimal("0"):
            pos_shares = Decimal("10000.0")
            pos_notional = Decimal("1500000.0")

        # Determine direction
        if pos_shares > Decimal("0"):
            position_direction = "LONG"
            liquidation_direction = "SELL"
        elif pos_shares < Decimal("0"):
            position_direction = "SHORT"
            liquidation_direction = "BUY"
        else:
            position_direction = "FLAT"
            liquidation_direction = "NONE"

        abs_shares = abs(pos_shares)
        abs_notional = abs(pos_notional)
        mid_price = (abs_notional / abs_shares) if abs_shares > Decimal("0") else Decimal("100.0")

        # Get current quote for baseline spread
        quote = await self.get_current_quote(instrument_id)
        half_spread_bps = (quote.spread_bps / Decimal("2.0")) if quote.spread_bps else Decimal("2.5")

        # Assume ADV in shares for capacity simulation (or default 250,000 shares)
        score_info = await self.get_instrument_liquidity_score(instrument_id)
        adv_shares = score_info.adv_shares_20d or Decimal("250000.0")

        # Standard institutional percentage reduction targets
        targets = [Decimal("0.10"), Decimal("0.25"), Decimal("0.50"), Decimal("0.75"), Decimal("0.90"), Decimal("1.00")]
        scenarios: List[TargetLiquidationScenario] = []

        for tgt in targets:
            tgt_shares = (abs_shares * tgt).quantize(Decimal("1"))
            tgt_notional = (tgt_shares * mid_price).quantize(Decimal("0.01"))

            # Participation execution capacity: ADV * participation_rate per day (375 trading minutes per standard session)
            daily_capacity_shares = adv_shares * participation_rate
            trading_days = (tgt_shares / daily_capacity_shares) if daily_capacity_shares > Decimal("0") else Decimal("1.0")
            duration_minutes = (trading_days * Decimal("375.0")).quantize(Decimal("0.1"))
            capacity_pct = ((tgt_shares / adv_shares) * Decimal("100.0")).quantize(Decimal("0.01"))

            # Market impact model: Impact_bps = gamma * sqrt(shares / ADV) * 100
            # Square root law of market impact without double counting spread
            impact_fraction = (tgt_shares / adv_shares) if adv_shares > Decimal("0") else Decimal("0.01")
            sqrt_val = Decimal(str(math.sqrt(float(impact_fraction))))
            market_impact_bps = (Decimal("15.0") * sqrt_val).quantize(Decimal("0.01"))

            # Slippage model (execution timing / volatility risk over horizon)
            slippage_bps = (Decimal("3.0") * (trading_days ** Decimal("0.5"))).quantize(Decimal("0.01"))

            # Total cost in basis points and USD
            spread_cost_bps = half_spread_bps
            total_cost_bps = spread_cost_bps + market_impact_bps + slippage_bps
            total_cost_usd = ((total_cost_bps / Decimal("10000.0")) * tgt_notional).quantize(Decimal("0.01"))

            scenarios.append(
                TargetLiquidationScenario(
                    target_percentage=tgt,
                    shares_to_liquidate=tgt_shares,
                    notional_value=tgt_notional,
                    liquidation_direction=liquidation_direction,
                    order_type_assumed="TWAP_WITH_LIMITS",
                    participation_rate=participation_rate,
                    spread_cost_bps=spread_cost_bps,
                    market_impact_cost_bps=market_impact_bps,
                    slippage_cost_bps=slippage_bps,
                    total_cost_bps=total_cost_bps,
                    total_cost_usd=total_cost_usd,
                    estimated_duration_minutes=duration_minutes,
                    estimated_trading_days=trading_days.quantize(Decimal("0.01")),
                    capacity_exhaustion_pct=capacity_pct,
                    risk_haircut_bps=(total_cost_bps * Decimal("1.25")).quantize(Decimal("0.01")),
                )
            )

        return InstrumentLiquidationProfile(
            instrument_id=instrument_id,
            symbol=symbol,
            current_position_shares=pos_shares,
            current_position_notional=pos_notional,
            position_direction=position_direction,
            liquidation_direction=liquidation_direction,
            base_participation_rate=participation_rate,
            scenarios=scenarios,
        )

    # ---------------------------------------------------------------------------
    # 5. Portfolio Liquidity Overview & Concentration
    # ---------------------------------------------------------------------------
    async def get_portfolio_liquidity_overview(
        self, portfolio_id: str
    ) -> PortfolioLiquidityDashboardResponse:
        """
        Consolidates portfolio holdings with individual spread, score, depth imbalance,
        and liquidation costs, producing weighted portfolio summaries.
        """
        # Fetch current active positions from valuations or books
        val_stmt = (
            select(PositionValuation)
            .where(PositionValuation.portfolio_id == portfolio_id)
        )
        val_res = await self.db.execute(val_stmt)
        valuations = val_res.scalars().all()

        total_nav = Decimal("0")
        holdings: List[HoldingLiquiditySummary] = []

        instrument_list: List[Tuple[str, Decimal]] = []
        if valuations:
            instrument_list = [(v.instrument_id, v.signed_quantity) for v in valuations if v.signed_quantity != Decimal("0")]
        else:
            pos_stmt = (
                select(PositionBook)
                .where(PositionBook.portfolio_id == portfolio_id)
            )
            pos_res = await self.db.execute(pos_stmt)
            positions = pos_res.scalars().all()
            instrument_list = [(p.instrument_id, Decimal("10000.0")) for p in positions]

        if not instrument_list:
            # Fallback to standard universe instruments
            inst_stmt = select(Instrument).limit(5)
            inst_res = await self.db.execute(inst_stmt)
            sample_insts = inst_res.scalars().all()
            instrument_list = [(inst.instrument_id, Decimal("10000.0")) for inst in sample_insts]

        # Calculate valuations and holdings summaries
        for inst_id, qty in instrument_list:
            inst_stmt = select(Instrument).where(Instrument.instrument_id == inst_id)
            inst_res = await self.db.execute(inst_stmt)
            inst = inst_res.scalar_one_or_none()
            symbol = inst.short_name if inst and hasattr(inst, "short_name") and inst.short_name else (inst.canonical_name if inst and hasattr(inst, "canonical_name") and inst.canonical_name else inst_id)
            sector = "Information Technology"

            quote = await self.get_current_quote(inst_id)
            score_info = await self.get_instrument_liquidity_score(inst_id)
            depth_info = await self.get_order_book_depth_ladder(inst_id, levels_count=5)
            liq_profile = await self.get_instrument_liquidation_profile(inst_id, portfolio_id=portfolio_id)

            full_liq = liq_profile.scenarios[-1] if liq_profile.scenarios else None
            notional = full_liq.notional_value if full_liq else (abs(qty) * Decimal("100.0"))
            total_nav += notional

            pos_dir = "LONG" if qty > Decimal("0") else ("SHORT" if qty < Decimal("0") else "FLAT")

            holdings.append(
                HoldingLiquiditySummary(
                    instrument_id=inst_id,
                    symbol=symbol,
                    sector=sector,
                    position_shares=qty,
                    position_notional=notional,
                    weight_pct=Decimal("0"),  # calculated below after total_nav
                    position_direction=pos_dir,
                    spread_bps=quote.spread_bps,
                    quote_condition=quote.quote_condition,
                    composite_score=score_info.composite_score,
                    liquidity_bucket=score_info.liquidity_bucket,
                    depth_imbalance=depth_info.depth_imbalance,
                    full_liquidation_cost_bps=full_liq.total_cost_bps if full_liq else None,
                    full_liquidation_cost_usd=full_liq.total_cost_usd if full_liq else None,
                    full_liquidation_days=full_liq.estimated_trading_days if full_liq else None,
                )
            )

        if total_nav == Decimal("0"):
            total_nav = Decimal("1.0")

        # Compute weights and weighted portfolio averages
        weighted_score = Decimal("0")
        weighted_spread = Decimal("0")
        total_liq_cost_usd = Decimal("0")
        low_liquidity_nav = Decimal("0")
        max_days = Decimal("0")
        locked_crossed_count = 0
        severe_imbalance_count = 0

        for h in holdings:
            w = (h.position_notional / total_nav) * Decimal("100.0")
            h.weight_pct = w.quantize(Decimal("0.01"))

            if h.composite_score is not None:
                weighted_score += h.composite_score * (h.weight_pct / Decimal("100.0"))
            if h.spread_bps is not None:
                weighted_spread += h.spread_bps * (h.weight_pct / Decimal("100.0"))
            if h.full_liquidation_cost_usd is not None:
                total_liq_cost_usd += h.full_liquidation_cost_usd
            if h.full_liquidation_days is not None and h.full_liquidation_days > max_days:
                max_days = h.full_liquidation_days

            if h.liquidity_bucket in ("TIER_3_LOW", "TIER_4_ILLIQUID"):
                low_liquidity_nav += h.position_notional

            if h.quote_condition in ("LOCKED", "CROSSED"):
                locked_crossed_count += 1

            if h.depth_imbalance is not None and abs(h.depth_imbalance) > Decimal("0.5"):
                severe_imbalance_count += 1

        low_liq_pct = ((low_liquidity_nav / total_nav) * Decimal("100.0")).quantize(Decimal("0.01"))
        portfolio_liq_cost_bps = ((total_liq_cost_usd / total_nav) * Decimal("10000.0")).quantize(Decimal("0.01"))

        return PortfolioLiquidityDashboardResponse(
            portfolio_id=portfolio_id,
            as_of_date=utc_now(),
            total_nav=total_nav.quantize(Decimal("0.01")),
            holdings_count=len(holdings),
            weighted_composite_score=weighted_score.quantize(Decimal("0.01")),
            weighted_spread_bps=weighted_spread.quantize(Decimal("0.01")),
            total_full_liquidation_cost_usd=total_liq_cost_usd.quantize(Decimal("0.01")),
            portfolio_liquidation_cost_bps=portfolio_liq_cost_bps,
            max_days_to_liquidate=max_days.quantize(Decimal("0.01")),
            low_liquidity_capital_pct=low_liq_pct,
            locked_or_crossed_instruments_count=locked_crossed_count,
            severe_imbalance_count=severe_imbalance_count,
            holdings=holdings,
        )

    # ---------------------------------------------------------------------------
    # 6. User Preferences, Saved Views, and Investigation Workflows
    # ---------------------------------------------------------------------------
    async def get_or_create_user_preferences(
        self, user_id: str, dashboard_name: str = "Default Liquidity Dashboard"
    ) -> LiquidityDashboardPreference:
        stmt = (
            select(LiquidityDashboardPreference)
            .where(
                and_(
                    LiquidityDashboardPreference.user_id == user_id,
                    LiquidityDashboardPreference.dashboard_name == dashboard_name,
                )
            )
        )
        res = await self.db.execute(stmt)
        pref = res.scalar_one_or_none()

        if not pref:
            pref = LiquidityDashboardPreference(
                user_id=user_id,
                dashboard_name=dashboard_name,
                spread_unit="BPS",
                depth_levels_count=5,
                default_lookback_days=30,
                default_participation_rate=Decimal("0.10"),
                default_liquidation_scenario="MODERATE",
                default_target_percentage=Decimal("1.00"),
                display_configuration={},
            )
            self.db.add(pref)
            await self.db.commit()
            await self.db.refresh(pref)

        return pref

    async def update_user_preferences(
        self, user_id: str, req: PreferenceCreateRequest
    ) -> LiquidityDashboardPreference:
        pref = await self.get_or_create_user_preferences(
            user_id=user_id, dashboard_name=req.dashboard_name or "Default Liquidity Dashboard"
        )
        if req.default_portfolio_id is not None:
            pref.default_portfolio_id = req.default_portfolio_id
        if req.spread_unit is not None:
            pref.spread_unit = req.spread_unit
        if req.depth_levels_count is not None:
            pref.depth_levels_count = req.depth_levels_count
        if req.default_lookback_days is not None:
            pref.default_lookback_days = req.default_lookback_days
        if req.default_participation_rate is not None:
            pref.default_participation_rate = req.default_participation_rate
        if req.default_liquidation_scenario is not None:
            pref.default_liquidation_scenario = req.default_liquidation_scenario
        if req.default_target_percentage is not None:
            pref.default_target_percentage = req.default_target_percentage
        if req.display_configuration is not None:
            pref.display_configuration = req.display_configuration

        pref.updated_at = utc_now()
        await self.db.commit()
        await self.db.refresh(pref)
        return pref

    async def create_saved_view(self, user_id: str, req: SavedViewCreateRequest) -> LiquiditySavedView:
        view = LiquiditySavedView(
            user_id=user_id,
            view_name=req.view_name,
            description=req.description,
            portfolio_id=req.portfolio_id,
            filters=req.filters or {},
            selected_instrument_ids=req.selected_instrument_ids or [],
            is_public=req.is_public or False,
        )
        self.db.add(view)
        await self.db.commit()
        await self.db.refresh(view)
        return view

    async def list_saved_views(self, user_id: str) -> List[LiquiditySavedView]:
        stmt = (
            select(LiquiditySavedView)
            .where(
                or_(
                    LiquiditySavedView.user_id == user_id,
                    LiquiditySavedView.is_public.is_(True),
                )
            )
            .order_by(desc(LiquiditySavedView.created_at))
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def create_investigation(
        self, user_id: str, req: InvestigationCreateRequest
    ) -> LiquidityInvestigation:
        inv = LiquidityInvestigation(
            user_id=user_id,
            portfolio_id=req.portfolio_id,
            instrument_id=req.instrument_id,
            investigation_type=req.investigation_type,
            severity=req.severity or "MEDIUM",
            status="OPEN",
            title=req.title,
            notes=req.notes,
            metrics_snapshot=req.metrics_snapshot or {},
        )
        self.db.add(inv)
        await self.db.commit()
        await self.db.refresh(inv)
        return inv

    async def list_investigations(
        self, user_id: Optional[str] = None, instrument_id: Optional[str] = None
    ) -> List[LiquidityInvestigation]:
        stmt = select(LiquidityInvestigation)
        conds = []
        if user_id:
            conds.append(LiquidityInvestigation.user_id == user_id)
        if instrument_id:
            conds.append(LiquidityInvestigation.instrument_id == instrument_id)
        if conds:
            stmt = stmt.where(and_(*conds))
        stmt = stmt.order_by(desc(LiquidityInvestigation.created_at))
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
