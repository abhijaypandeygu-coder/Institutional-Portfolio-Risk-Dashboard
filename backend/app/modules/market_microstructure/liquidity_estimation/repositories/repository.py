"""
M09.03 Liquidity Estimation - Repository Layer.
Async database operations for metrics, volumes, turnovers, scores, and bucket snapshots.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

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


class LiquidityRepository:
    """Async repository for M09.03 Liquidity Estimation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # Configurations
    async def create_metric_config(self, cfg: LiquidityMetricConfig) -> LiquidityMetricConfig:
        self.db.add(cfg)
        await self.db.flush()
        return cfg

    async def get_active_metric_config(self, config_code: str) -> Optional[LiquidityMetricConfig]:
        stmt = (
            select(LiquidityMetricConfig)
            .where(LiquidityMetricConfig.config_code == config_code)
            .order_by(desc(LiquidityMetricConfig.version))
        )
        res = await self.db.execute(stmt)
        return res.scalars().first()

    async def create_score_config(self, cfg: LiquidityScoreConfig) -> LiquidityScoreConfig:
        self.db.add(cfg)
        await self.db.flush()
        return cfg

    async def get_active_score_config(self, profile_code: str) -> Optional[LiquidityScoreConfig]:
        stmt = (
            select(LiquidityScoreConfig)
            .where(LiquidityScoreConfig.profile_code == profile_code)
            .order_by(desc(LiquidityScoreConfig.version))
        )
        res = await self.db.execute(stmt)
        return res.scalars().first()

    async def create_bucket_policy(self, pol: LiquidityBucketPolicy) -> LiquidityBucketPolicy:
        self.db.add(pol)
        await self.db.flush()
        return pol

    async def get_active_bucket_policy(self, policy_code: str) -> Optional[LiquidityBucketPolicy]:
        stmt = (
            select(LiquidityBucketPolicy)
            .where(LiquidityBucketPolicy.policy_code == policy_code)
            .order_by(desc(LiquidityBucketPolicy.version))
        )
        res = await self.db.execute(stmt)
        return res.scalars().first()

    # Volume & Turnover Aggregates
    async def save_volume_aggregate(self, vol: LiquidityVolumeAggregate) -> LiquidityVolumeAggregate:
        self.db.add(vol)
        await self.db.flush()
        return vol

    async def save_turnover_aggregate(self, tov: LiquidityTurnoverAggregate) -> LiquidityTurnoverAggregate:
        self.db.add(tov)
        await self.db.flush()
        return tov

    async def get_volume_aggregates(
        self, instrument_id: str, start_time: datetime, end_time: datetime
    ) -> List[LiquidityVolumeAggregate]:
        stmt = (
            select(LiquidityVolumeAggregate)
            .where(
                and_(
                    LiquidityVolumeAggregate.instrument_id == instrument_id,
                    LiquidityVolumeAggregate.aggregation_start >= start_time,
                    LiquidityVolumeAggregate.aggregation_end <= end_time,
                )
            )
            .order_by(LiquidityVolumeAggregate.aggregation_start.asc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_turnover_aggregates(
        self, instrument_id: str, start_time: datetime, end_time: datetime
    ) -> List[LiquidityTurnoverAggregate]:
        stmt = (
            select(LiquidityTurnoverAggregate)
            .where(
                and_(
                    LiquidityTurnoverAggregate.instrument_id == instrument_id,
                    LiquidityTurnoverAggregate.aggregation_start >= start_time,
                    LiquidityTurnoverAggregate.aggregation_end <= end_time,
                )
            )
            .order_by(LiquidityTurnoverAggregate.aggregation_start.asc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # Rolling Stats
    async def save_rolling_statistics(self, stats: LiquidityRollingStatistics) -> LiquidityRollingStatistics:
        self.db.add(stats)
        await self.db.flush()
        return stats

    async def get_latest_rolling_statistics(self, instrument_id: str) -> Optional[LiquidityRollingStatistics]:
        stmt = (
            select(LiquidityRollingStatistics)
            .where(LiquidityRollingStatistics.instrument_id == instrument_id)
            .order_by(desc(LiquidityRollingStatistics.as_of_timestamp))
        )
        res = await self.db.execute(stmt)
        return res.scalars().first()

    # Scores & Snapshots
    async def save_score_snapshot(self, score: LiquidityScoreSnapshot) -> LiquidityScoreSnapshot:
        self.db.add(score)
        await self.db.flush()
        return score

    async def get_latest_score_snapshot(self, instrument_id: str) -> Optional[LiquidityScoreSnapshot]:
        stmt = (
            select(LiquidityScoreSnapshot)
            .where(LiquidityScoreSnapshot.instrument_id == instrument_id)
            .order_by(desc(LiquidityScoreSnapshot.as_of_timestamp))
        )
        res = await self.db.execute(stmt)
        return res.scalars().first()

    # Buckets & Transitions
    async def save_bucket_snapshot(self, bucket: LiquidityBucketSnapshot) -> LiquidityBucketSnapshot:
        self.db.add(bucket)
        await self.db.flush()
        return bucket

    async def save_bucket_transition(self, trans: LiquidityBucketTransition) -> LiquidityBucketTransition:
        self.db.add(trans)
        await self.db.flush()
        return trans

    async def get_latest_bucket_snapshot(self, instrument_id: str) -> Optional[LiquidityBucketSnapshot]:
        stmt = (
            select(LiquidityBucketSnapshot)
            .where(LiquidityBucketSnapshot.instrument_id == instrument_id)
            .order_by(desc(LiquidityBucketSnapshot.as_of_timestamp))
        )
        res = await self.db.execute(stmt)
        return res.scalars().first()

    # Screening Query
    async def screen_instruments(
        self,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        bucket: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Screens latest score and bucket snapshots."""
        stmt = (
            select(
                LiquidityScoreSnapshot.instrument_id,
                LiquidityScoreSnapshot.exchange,
                LiquidityScoreSnapshot.venue,
                LiquidityScoreSnapshot.currency,
                LiquidityScoreSnapshot.composite_liquidity_score,
                LiquidityScoreSnapshot.scoring_status,
                LiquidityScoreSnapshot.as_of_timestamp,
                LiquidityBucketSnapshot.bucket_name,
                LiquidityBucketSnapshot.bucket_rank
            )
            .outerjoin(
                LiquidityBucketSnapshot,
                and_(
                    LiquidityBucketSnapshot.instrument_id == LiquidityScoreSnapshot.instrument_id,
                    LiquidityBucketSnapshot.as_of_timestamp == LiquidityScoreSnapshot.as_of_timestamp
                )
            )
        )
        conds = []
        if min_score is not None:
            conds.append(LiquidityScoreSnapshot.composite_liquidity_score >= min_score)
        if max_score is not None:
            conds.append(LiquidityScoreSnapshot.composite_liquidity_score <= max_score)
        if bucket is not None:
            conds.append(LiquidityBucketSnapshot.bucket_name == bucket)

        if conds:
            stmt = stmt.where(and_(*conds))

        stmt = stmt.order_by(desc(LiquidityScoreSnapshot.composite_liquidity_score)).offset(offset).limit(limit)
        res = await self.db.execute(stmt)
        rows = res.all()

        results = []
        for r in rows:
            results.append({
                "instrument_id": r[0],
                "exchange": r[1],
                "venue": r[2],
                "currency": r[3],
                "composite_score": r[4],
                "scoring_status": r[5],
                "as_of_timestamp": r[6],
                "liquidity_bucket": r[7] or "INSUFFICIENT_DATA",
                "bucket_rank": r[8] or 6
            })
        return results

