"""
Historical Scenarios Repository (M10.01).
Provides persistence and queries for historical events, observations, replay runs, and warnings.
"""

from typing import List, Optional, Dict
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.scenario_models import (
    HistoricalScenarioEvent,
    HistoricalScenarioEventVersion,
    HistoricalScenarioObservation,
    HistoricalShockMappingRule,
    HistoricalScenarioReplayRun,
    HistoricalShockMappingResult,
    HistoricalScenarioReplayPosition,
    HistoricalScenarioReplayWarning,
    HistoricalScenarioReplayPath
)


class HistoricalScenariosRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(self, event: HistoricalScenarioEvent) -> HistoricalScenarioEvent:
        self.db.add(event)
        await self.db.flush()
        return event

    async def get_event_by_id(self, event_id: str) -> Optional[HistoricalScenarioEvent]:
        stmt = select(HistoricalScenarioEvent).where(HistoricalScenarioEvent.id == event_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_event_by_code(self, event_code: str) -> Optional[HistoricalScenarioEvent]:
        stmt = select(HistoricalScenarioEvent).where(HistoricalScenarioEvent.event_code == event_code)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_events(
        self,
        category: Optional[str] = None,
        region: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[HistoricalScenarioEvent]:
        stmt = select(HistoricalScenarioEvent)
        if category:
            stmt = stmt.where(HistoricalScenarioEvent.category == category)
        if region:
            stmt = stmt.where(HistoricalScenarioEvent.affected_regions == region)
        if status:
            stmt = stmt.where(HistoricalScenarioEvent.event_status == status)
        stmt = stmt.order_by(desc(HistoricalScenarioEvent.created_at)).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_observation(self, obs: HistoricalScenarioObservation) -> HistoricalScenarioObservation:
        self.db.add(obs)
        await self.db.flush()
        return obs

    async def get_event_observations(
        self,
        event_id: str,
        instrument_id: Optional[str] = None
    ) -> List[HistoricalScenarioObservation]:
        stmt = select(HistoricalScenarioObservation).where(
            HistoricalScenarioObservation.event_id == event_id
        )
        if instrument_id:
            stmt = stmt.where(HistoricalScenarioObservation.instrument_id == instrument_id)
        stmt = stmt.order_by(HistoricalScenarioObservation.observation_date)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_replay_run(self, run: HistoricalScenarioReplayRun) -> HistoricalScenarioReplayRun:
        self.db.add(run)
        await self.db.flush()
        return run

    async def get_replay_run_by_id(self, replay_id: str) -> Optional[HistoricalScenarioReplayRun]:
        stmt = select(HistoricalScenarioReplayRun).where(HistoricalScenarioReplayRun.id == replay_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_replay_runs(
        self,
        portfolio_id: Optional[str] = None,
        limit: int = 50
    ) -> List[HistoricalScenarioReplayRun]:
        stmt = select(HistoricalScenarioReplayRun)
        if portfolio_id:
            stmt = stmt.where(HistoricalScenarioReplayRun.portfolio_id == portfolio_id)
        stmt = stmt.order_by(desc(HistoricalScenarioReplayRun.started_at)).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_replay_positions(self, positions: List[HistoricalScenarioReplayPosition]):
        self.db.add_all(positions)
        await self.db.flush()

    async def get_replay_positions(self, replay_id: str) -> List[HistoricalScenarioReplayPosition]:
        stmt = select(HistoricalScenarioReplayPosition).where(
            HistoricalScenarioReplayPosition.replay_id == replay_id
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_replay_warnings(self, warnings: List[HistoricalScenarioReplayWarning]):
        self.db.add_all(warnings)
        await self.db.flush()

    async def get_replay_warnings(self, replay_id: str) -> List[HistoricalScenarioReplayWarning]:
        stmt = select(HistoricalScenarioReplayWarning).where(
            HistoricalScenarioReplayWarning.replay_id == replay_id
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_replay_paths(self, paths: List[HistoricalScenarioReplayPath]):
        self.db.add_all(paths)
        await self.db.flush()

    async def get_replay_paths(self, replay_id: str) -> List[HistoricalScenarioReplayPath]:
        stmt = select(HistoricalScenarioReplayPath).where(
            HistoricalScenarioReplayPath.replay_id == replay_id
        ).order_by(HistoricalScenarioReplayPath.observation_date)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

