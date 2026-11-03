"""
M09.03 Liquidity Estimation - Service Layer.
Coordinates:
- Trade execution aggregation from M02 or direct payloads
- Volume and turnover calculation
- Rolling statistics (ADV, ADTV, stddev, percentiles)
- Authoritative M09.01 and M09.02 metrics resolution
- Normalization and Composite Liquidity Scoring
- Liquidity Bucket Classification and Transition Tracking
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_data_ingestion.persistence.models import MarketTradeEvent
from backend.app.modules.market_microstructure.bid_ask_spread.models import SpreadObservation
from backend.app.modules.market_microstructure.order_book_depth.models import OrderBookDepthSnapshot

from backend.app.modules.market_microstructure.liquidity_estimation.models import (
    LiquidityMetricConfig,
    LiquidityVolumeAggregate,
    LiquidityTurnoverAggregate,
    LiquidityRollingStatistics,
    LiquidityScoreConfig,
    LiquidityScoreSnapshot,
    LiquidityBucketPolicy,
    LiquidityBucketSnapshot,
    LiquidityBucketTransition,
)
from backend.app.modules.market_microstructure.liquidity_estimation.repositories.repository import LiquidityRepository
from backend.app.modules.market_microstructure.liquidity_estimation.calculations.liquidity_math import (
    compute_traded_volume_and_turnover,
    compute_series_statistics,
    compute_intraday_pace,
    compute_subscores,
    compute_data_availability_score,
    compute_composite_liquidity_score,
    classify_liquidity_bucket,
    _normalize_tz,
)


class LiquidityEstimationService:
    """Institutional service layer for M09.03 Liquidity Estimation."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = LiquidityRepository(db)

    # 1. Config management
    async def create_metric_config(self, req: Dict[str, Any]) -> LiquidityMetricConfig:
        existing = await self.repo.get_active_metric_config(req["config_code"])
        new_version = (existing.version + 1) if existing else 1
        cfg = LiquidityMetricConfig(
            config_id=f"LMC_{uuid.uuid4().hex[:12]}",
            config_code=req["config_code"],
            version=new_version,
            name=req["name"],
            market=req.get("market", "ALL"),
            currency=req.get("currency", "USD"),
            volume_aggregation_interval=req.get("volume_aggregation_interval", "1d"),
            turnover_aggregation_interval=req.get("turnover_aggregation_interval", "1d"),
            volume_lookback_sessions=req.get("volume_lookback_sessions", 20),
            turnover_lookback_sessions=req.get("turnover_lookback_sessions", 20),
            minimum_coverage=req.get("minimum_coverage", 0.50),
            is_active=True,
            created_at=datetime.now(timezone.utc),
            created_by="SYSTEM"
        )
        return await self.repo.create_metric_config(cfg)

    async def create_score_profile(self, req: Dict[str, Any]) -> LiquidityScoreConfig:
        existing = await self.repo.get_active_score_config(req["profile_code"])
        new_version = (existing.version + 1) if existing else 1
        cfg = LiquidityScoreConfig(
            profile_id=f"LSP_{uuid.uuid4().hex[:12]}",
            profile_code=req["profile_code"],
            version=new_version,
            name=req["name"],
            market_scope=req.get("market_scope", "ALL"),
            currency=req.get("currency", "USD"),
            peer_group_definition=req.get("peer_group_definition", "DEFAULT_PEERS"),
            spread_weight=req.get("spread_weight", 0.25),
            depth_weight=req.get("depth_weight", 0.30),
            turnover_weight=req.get("turnover_weight", 0.30),
            availability_weight=req.get("availability_weight", 0.15),
            minimum_spread_coverage=req.get("minimum_spread_coverage", 0.50),
            minimum_depth_coverage=req.get("minimum_depth_coverage", 0.50),
            minimum_turnover_coverage=req.get("minimum_turnover_coverage", 0.50),
            minimum_reference_sample_size=req.get("minimum_reference_sample_size", 5),
            winsorization_enabled=req.get("winsorization_enabled", False),
            winsor_lower_percentile=req.get("winsor_lower_percentile", 1.0),
            winsor_upper_percentile=req.get("winsor_upper_percentile", 99.0),
            is_active=True,
            created_at=datetime.now(timezone.utc),
            created_by="SYSTEM"
        )
        return await self.repo.create_score_config(cfg)

    async def create_bucket_policy(self, req: Dict[str, Any]) -> LiquidityBucketPolicy:
        existing = await self.repo.get_active_bucket_policy(req["policy_code"])
        new_version = (existing.version + 1) if existing else 1
        pol = LiquidityBucketPolicy(
            policy_id=f"LBP_{uuid.uuid4().hex[:12]}",
            policy_code=req["policy_code"],
            version=new_version,
            name=req["name"],
            classification_method=req.get("classification_method", "SCORE_THRESHOLD"),
            market_scope=req.get("market_scope", "ALL"),
            threshold_definitions=req["threshold_definitions"],
            is_active=True,
            created_at=datetime.now(timezone.utc),
            created_by="SYSTEM"
        )
        return await self.repo.create_bucket_policy(pol)

    # 2. Volume & Turnover Processing
    async def aggregate_trades(
        self,
        instrument_id: str,
        exchange: str,
        venue: str,
        start_time: datetime,
        end_time: datetime,
        currency: str = "USD",
        direct_trades: Optional[List[Dict[str, Any]]] = None,
        instrument_multiplier: Decimal = Decimal("1.0")
    ) -> Tuple[LiquidityVolumeAggregate, LiquidityTurnoverAggregate]:
        """
        Aggregates trades over [start_time, end_time].
        Uses direct_trades if provided, else queries canonical M02 MarketTradeEvent.
        """
        start_time = _normalize_tz(start_time)
        end_time = _normalize_tz(end_time)

        trades_to_process = []
        if direct_trades is not None:
            trades_to_process = direct_trades
        else:
            # Query M02 MarketTradeEvent
            stmt = (
                select(MarketTradeEvent)
                .where(
                    MarketTradeEvent.instrument_id == instrument_id,
                    MarketTradeEvent.trade_timestamp >= start_time,
                    MarketTradeEvent.trade_timestamp <= end_time,
                )
            )
            res = await self.db.execute(stmt)
            m02_trades = res.scalars().all()
            for t in m02_trades:
                trades_to_process.append({
                    "trade_id": t.event_id,
                    "price": t.price,
                    "quantity": t.quantity,
                    "timestamp": t.trade_timestamp,
                    "status": "ACTIVE"
                })

        agg = compute_traded_volume_and_turnover(trades_to_process, instrument_multiplier)

        vol_record = LiquidityVolumeAggregate(
            aggregate_id=f"LVA_{uuid.uuid4().hex[:12]}",
            instrument_id=instrument_id,
            exchange=exchange,
            venue=venue,
            aggregation_start=start_time,
            aggregation_end=end_time,
            aggregation_interval="interval",
            traded_volume=agg["traded_volume"],
            eligible_trade_count=agg["eligible_trade_count"],
            valid_coverage_ratio=1.0,
            source_scope="VENUE_SPECIFIC",
            quality_status="ELIGIBLE",
            calculation_version="1.0.0",
            created_at=datetime.now(timezone.utc)
        )
        await self.repo.save_volume_aggregate(vol_record)

        tov_record = LiquidityTurnoverAggregate(
            aggregate_id=f"LTA_{uuid.uuid4().hex[:12]}",
            instrument_id=instrument_id,
            exchange=exchange,
            venue=venue,
            aggregation_start=start_time,
            aggregation_end=end_time,
            aggregation_interval="interval",
            turnover_amount=agg["turnover"],
            currency=currency,
            eligible_trade_count=agg["eligible_trade_count"],
            valid_coverage_ratio=1.0,
            source_scope="VENUE_SPECIFIC",
            quality_status="ELIGIBLE",
            calculation_version="1.0.0",
            created_at=datetime.now(timezone.utc)
        )
        await self.repo.save_turnover_aggregate(tov_record)

        return vol_record, tov_record

    # 3. Rolling Statistics
    async def compute_rolling_statistics(
        self,
        instrument_id: str,
        venue: str,
        as_of: datetime,
        lookback_sessions: int = 20,
        currency: str = "USD"
    ) -> LiquidityRollingStatistics:
        as_of = _normalize_tz(as_of)

        # Pull past aggregates
        stmt_vol = (
            select(LiquidityVolumeAggregate)
            .where(
                LiquidityVolumeAggregate.instrument_id == instrument_id,
                LiquidityVolumeAggregate.aggregation_end <= as_of
            )
            .order_by(LiquidityVolumeAggregate.aggregation_end.desc())
            .limit(lookback_sessions)
        )
        res_vol = await self.db.execute(stmt_vol)
        vols = [float(v.traded_volume) for v in res_vol.scalars().all()]

        stmt_tov = (
            select(LiquidityTurnoverAggregate)
            .where(
                LiquidityTurnoverAggregate.instrument_id == instrument_id,
                LiquidityTurnoverAggregate.aggregation_end <= as_of
            )
            .order_by(LiquidityTurnoverAggregate.aggregation_end.desc())
            .limit(lookback_sessions)
        )
        res_tov = await self.db.execute(stmt_tov)
        tovs = [float(t.turnover_amount) for t in res_tov.scalars().all()]

        v_stats = compute_series_statistics(vols)
        t_stats = compute_series_statistics(tovs)

        stat = LiquidityRollingStatistics(
            stat_id=f"LRS_{uuid.uuid4().hex[:12]}",
            instrument_id=instrument_id,
            venue=venue,
            as_of_timestamp=as_of,
            lookback_sessions=lookback_sessions,
            eligible_session_count=len(vols),
            coverage_ratio=1.0 if vols else 0.0,
            average_daily_volume=Decimal(str(round(v_stats["mean"], 4))) if v_stats["mean"] is not None else None,
            median_daily_volume=Decimal(str(round(v_stats["median"], 4))) if v_stats["median"] is not None else None,
            volume_stddev=Decimal(str(round(v_stats["std_dev"], 4))) if v_stats["std_dev"] is not None else None,
            volume_cv=v_stats["cv"],
            volume_percentiles={k: v_stats[k] for k in ["p10", "p25", "p50", "p75", "p90", "p95"] if v_stats[k] is not None},
            average_daily_turnover=Decimal(str(round(t_stats["mean"], 4))) if t_stats["mean"] is not None else None,
            median_daily_turnover=Decimal(str(round(t_stats["median"], 4))) if t_stats["median"] is not None else None,
            turnover_stddev=Decimal(str(round(t_stats["std_dev"], 4))) if t_stats["std_dev"] is not None else None,
            turnover_cv=t_stats["cv"],
            turnover_percentiles={k: t_stats[k] for k in ["p10", "p25", "p50", "p75", "p90", "p95"] if t_stats[k] is not None},
            currency=currency,
            quality_status="NORMAL",
            calculation_version="1.0.0",
            created_at=datetime.now(timezone.utc)
        )
        return await self.repo.save_rolling_statistics(stat)

    # 4. Composite Scoring & Bucketing
    async def evaluate_liquidity_score_and_bucket(
        self,
        instrument_id: str,
        exchange: str,
        venue: str,
        as_of: datetime,
        score_config_code: str = "DEFAULT_SCORE_PROFILE",
        bucket_policy_code: str = "DEFAULT_BUCKET_POLICY",
        currency: str = "USD",
        # Optional manual metric overrides
        override_spread_bps: Optional[float] = None,
        override_depth_notional: Optional[Decimal] = None,
        override_turnover: Optional[Decimal] = None,
        override_peer_spreads: Optional[List[float]] = None,
        override_peer_depths: Optional[List[float]] = None,
        override_peer_turnovers: Optional[List[float]] = None,
    ) -> Tuple[LiquidityScoreSnapshot, LiquidityBucketSnapshot]:
        as_of = _normalize_tz(as_of)

        # 1. Resolve active score configuration
        score_cfg = await self.repo.get_active_score_config(score_config_code)
        if not score_cfg:
            # Fallback default configuration
            score_cfg = LiquidityScoreConfig(
                profile_id="LSP_DEFAULT",
                profile_code=score_config_code,
                version=1,
                name="Default Scoring Profile",
                spread_weight=0.25,
                depth_weight=0.30,
                turnover_weight=0.30,
                availability_weight=0.15,
                minimum_spread_coverage=0.50,
                minimum_depth_coverage=0.50,
                minimum_turnover_coverage=0.50,
                minimum_reference_sample_size=3
            )

        # 2. Resolve metrics
        # Spread from M09.01 or override
        spread_bps = override_spread_bps
        spread_cov = 1.0
        if spread_bps is None:
            stmt_sp = (
                select(SpreadObservation)
                .where(SpreadObservation.instrument_id == instrument_id)
                .order_by(SpreadObservation.observation_id.desc())
                .limit(1)
            )
            res_sp = await self.db.execute(stmt_sp)
            sp_row = res_sp.scalars().first()
            if sp_row and sp_row.relative_spread_bps is not None:
                spread_bps = float(sp_row.relative_spread_bps)

        # Depth from M09.02 or override
        depth_notional = override_depth_notional
        depth_cov = 1.0
        if depth_notional is None:
            stmt_dp = (
                select(OrderBookDepthSnapshot)
                .where(OrderBookDepthSnapshot.instrument_id == instrument_id)
                .order_by(OrderBookDepthSnapshot.snapshot_id.desc())
                .limit(1)
            )
            res_dp = await self.db.execute(stmt_dp)
            dp_row = res_dp.scalars().first()
            if dp_row:
                bid_n = dp_row.bid_notional_top5 or Decimal("0.0")
                ask_n = dp_row.ask_notional_top5 or Decimal("0.0")
                depth_notional = (bid_n + ask_n) / Decimal("2.0")

        # Turnover from M09.03 aggregates or override
        turnover_val = override_turnover
        turnover_cov = 1.0
        if turnover_val is None:
            rolling_stat = await self.repo.get_latest_rolling_statistics(instrument_id)
            if rolling_stat and rolling_stat.average_daily_turnover is not None:
                turnover_val = rolling_stat.average_daily_turnover
            else:
                # Fallback to latest interval aggregate
                stmt_t = (
                    select(LiquidityTurnoverAggregate)
                    .where(LiquidityTurnoverAggregate.instrument_id == instrument_id)
                    .order_by(LiquidityTurnoverAggregate.aggregation_end.desc())
                    .limit(1)
                )
                res_t = await self.db.execute(stmt_t)
                t_row = res_t.scalars().first()
                if t_row:
                    turnover_val = t_row.turnover_amount

        # 3. Peer populations
        peer_spreads = override_peer_spreads or ([spread_bps, spread_bps * 1.5, spread_bps * 0.8] if spread_bps else [])
        peer_depths = override_peer_depths or ([float(depth_notional), float(depth_notional) * 0.8, float(depth_notional) * 1.2] if depth_notional else [])
        peer_turnovers = override_peer_turnovers or ([float(turnover_val), float(turnover_val) * 0.7, float(turnover_val) * 1.4] if turnover_val else [])

        # 4. Subscores
        subscores = compute_subscores(
            spread_bps=spread_bps,
            depth_notional=float(depth_notional) if depth_notional is not None else None,
            turnover_val=float(turnover_val) if turnover_val is not None else None,
            peer_spreads=peer_spreads,
            peer_depths=peer_depths,
            peer_turnovers=peer_turnovers
        )

        s_avail, _ = compute_data_availability_score(
            spread_coverage=spread_cov,
            depth_coverage=depth_cov,
            turnover_coverage=turnover_cov
        )

        # 5. Composite score
        weights = {
            "spread_weight": score_cfg.spread_weight,
            "depth_weight": score_cfg.depth_weight,
            "turnover_weight": score_cfg.turnover_weight,
            "availability_weight": score_cfg.availability_weight
        }
        score_eval = compute_composite_liquidity_score(
            spread_subscore=subscores["spread_subscore"],
            depth_subscore=subscores["depth_subscore"],
            turnover_subscore=subscores["turnover_subscore"],
            availability_subscore=s_avail,
            weights=weights,
            min_spread_coverage=score_cfg.minimum_spread_coverage,
            min_depth_coverage=score_cfg.minimum_depth_coverage,
            min_turnover_coverage=score_cfg.minimum_turnover_coverage,
            actual_spread_cov=spread_cov,
            actual_depth_cov=depth_cov,
            actual_turnover_cov=turnover_cov
        )

        score_snap = LiquidityScoreSnapshot(
            snapshot_id=f"LSS_{uuid.uuid4().hex[:12]}",
            instrument_id=instrument_id,
            exchange=exchange,
            venue=venue,
            currency=currency,
            as_of_timestamp=as_of,
            score_config_code=score_cfg.profile_code,
            score_config_version=score_cfg.version,
            peer_group_id=score_cfg.peer_group_definition,
            spread_raw_value=spread_bps,
            depth_raw_value=depth_notional,
            turnover_raw_value=turnover_val,
            spread_subscore=score_eval["spread_subscore"],
            depth_subscore=score_eval["depth_subscore"],
            turnover_subscore=score_eval["turnover_subscore"],
            availability_subscore=score_eval["availability_subscore"],
            spread_contribution=score_eval["spread_contribution"],
            depth_contribution=score_eval["depth_contribution"],
            turnover_contribution=score_eval["turnover_contribution"],
            availability_contribution=score_eval["availability_contribution"],
            spread_coverage=spread_cov,
            depth_coverage=depth_cov,
            turnover_coverage=turnover_cov,
            composite_liquidity_score=score_eval["composite_score"],
            scoring_status=score_eval["status"],
            status_reason=score_eval["reason"],
            calculation_version="1.0.0",
            created_at=datetime.now(timezone.utc)
        )
        await self.repo.save_score_snapshot(score_snap)

        # 6. Classification into Liquidity Bucket
        bucket_policy = await self.repo.get_active_bucket_policy(bucket_policy_code)
        thresholds = bucket_policy.threshold_definitions if bucket_policy else None
        bucket_res = classify_liquidity_bucket(
            composite_score=score_eval["composite_score"],
            scoring_status=score_eval["status"],
            thresholds=thresholds,
            method="SCORE_THRESHOLD"
        )

        prev_bucket = await self.repo.get_latest_bucket_snapshot(instrument_id)

        bucket_snap = LiquidityBucketSnapshot(
            snapshot_id=f"LBS_{uuid.uuid4().hex[:12]}",
            instrument_id=instrument_id,
            venue=venue,
            as_of_timestamp=as_of,
            liquidity_score_snapshot_id=score_snap.snapshot_id,
            bucket_policy_code=bucket_policy.policy_code if bucket_policy else bucket_policy_code,
            bucket_policy_version=bucket_policy.version if bucket_policy else 1,
            bucket_name=bucket_res["bucket_name"],
            bucket_rank=bucket_res["bucket_rank"],
            underlying_score=score_eval["composite_score"],
            peer_group_percentile=score_eval["composite_score"],
            classification_status=score_eval["status"],
            classification_reason=bucket_res["classification_reason"],
            created_at=datetime.now(timezone.utc)
        )
        await self.repo.save_bucket_snapshot(bucket_snap)

        # 7. Check Transition
        if prev_bucket and prev_bucket.bucket_name != bucket_res["bucket_name"]:
            transition = LiquidityBucketTransition(
                transition_id=f"LBT_{uuid.uuid4().hex[:12]}",
                instrument_id=instrument_id,
                previous_bucket=prev_bucket.bucket_name,
                new_bucket=bucket_res["bucket_name"],
                previous_score=prev_bucket.underlying_score,
                new_score=score_eval["composite_score"],
                previous_snapshot_id=prev_bucket.snapshot_id,
                new_snapshot_id=bucket_snap.snapshot_id,
                bucket_policy_version=bucket_snap.bucket_policy_version,
                transition_timestamp=as_of,
                transition_reason=f"Shift from {prev_bucket.bucket_name} to {bucket_res['bucket_name']}",
                created_at=datetime.now(timezone.utc)
            )
            await self.repo.save_bucket_transition(transition)

        return score_snap, bucket_snap

