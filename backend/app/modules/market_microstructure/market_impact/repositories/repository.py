"""
M09.04 Market Impact - Repository Layer.
Async database operations for scenarios, configurations, depth walks, estimates, and models.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_microstructure.market_impact.models import (
    MarketImpactConfig,
    MarketImpactScenario,
    MarketImpactDepthWalk,
    MarketImpactDepthWalkLevel,
    MarketImpactEstimate,
    MarketImpactModelConfig,
    MarketImpactModelValidationRun,
)


class MarketImpactRepository:
    """Async repository for M09.04 Market Impact."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # 1. Configs
    async def create_impact_config(self, cfg: MarketImpactConfig) -> MarketImpactConfig:
        self.db.add(cfg)
        await self.db.flush()
        return cfg

    async def get_active_impact_config(self, config_code: str) -> Optional[MarketImpactConfig]:
        stmt = (
            select(MarketImpactConfig)
            .where(MarketImpactConfig.config_code == config_code)
            .order_by(desc(MarketImpactConfig.version))
        )
        res = await self.db.execute(stmt)
        return res.scalars().first()

    # 2. Scenarios
    async def create_scenario(self, scen: MarketImpactScenario) -> MarketImpactScenario:
        self.db.add(scen)
        await self.db.flush()
        return scen

    async def get_scenario(self, scenario_id: str) -> Optional[MarketImpactScenario]:
        stmt = select(MarketImpactScenario).where(MarketImpactScenario.scenario_id == scenario_id)
        res = await self.db.execute(stmt)
        return res.scalars().first()

    # 3. Depth Walk
    async def save_depth_walk(
        self, walk: MarketImpactDepthWalk, levels: List[MarketImpactDepthWalkLevel]
    ) -> MarketImpactDepthWalk:
        self.db.add(walk)
        for lvl in levels:
            self.db.add(lvl)
        await self.db.flush()
        return walk

    async def get_depth_walk(self, depth_walk_id: str) -> Optional[MarketImpactDepthWalk]:
        stmt = select(MarketImpactDepthWalk).where(MarketImpactDepthWalk.depth_walk_id == depth_walk_id)
        res = await self.db.execute(stmt)
        return res.scalars().first()

    async def get_depth_walk_levels(self, depth_walk_id: str) -> List[MarketImpactDepthWalkLevel]:
        stmt = (
            select(MarketImpactDepthWalkLevel)
            .where(MarketImpactDepthWalkLevel.depth_walk_id == depth_walk_id)
            .order_by(MarketImpactDepthWalkLevel.level_index.asc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # 4. Impact Estimates
    async def save_estimate(self, est: MarketImpactEstimate) -> MarketImpactEstimate:
        self.db.add(est)
        await self.db.flush()
        return est

    async def get_latest_estimate(self, scenario_id: str) -> Optional[MarketImpactEstimate]:
        stmt = (
            select(MarketImpactEstimate)
            .where(MarketImpactEstimate.scenario_id == scenario_id)
            .order_by(desc(MarketImpactEstimate.created_at))
        )
        res = await self.db.execute(stmt)
        return res.scalars().first()

    # 5. Model Registry
    async def create_model_config(self, cfg: MarketImpactModelConfig) -> MarketImpactModelConfig:
        self.db.add(cfg)
        await self.db.flush()
        return cfg

    async def get_active_model_config(self, model_code: str) -> Optional[MarketImpactModelConfig]:
        stmt = (
            select(MarketImpactModelConfig)
            .where(MarketImpactModelConfig.model_code == model_code)
            .order_by(desc(MarketImpactModelConfig.version))
        )
        res = await self.db.execute(stmt)
        return res.scalars().first()

    # 6. Validation Runs
    async def save_validation_run(self, run: MarketImpactModelValidationRun) -> MarketImpactModelValidationRun:
        self.db.add(run)
        await self.db.flush()
        return run
