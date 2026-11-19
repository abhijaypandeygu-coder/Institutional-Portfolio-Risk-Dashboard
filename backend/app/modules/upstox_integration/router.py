import asyncio
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.core.security import UserRole, require_role
from backend.app.modules.external_data.service import ProviderError
from .service import broker, DEFAULT_LIMITS, normalize_quote, now
from .stream import stream

router = APIRouter(prefix='/api/v1/broker/upstox', tags=['Upstox integrated analytics'],
                   dependencies=[Depends(require_role(UserRole.OPERATOR))])


class Query(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    instrument_keys: list[str] = Field(default_factory=list, max_length=20)

    @field_validator('instrument_keys')
    @classmethod
    def valid_keys(cls, keys):
        if len(set(keys)) != len(keys): raise ValueError('Duplicate instrument keys')
        for key in keys:
            if '|' not in key or len(key) > 100 or any(c in key for c in '/?#&,\r\n'):
                raise ValueError('Use Upstox instrument keys, e.g. NSE_EQ|INE002A01018')
        return keys


class StressQuery(Query):
    from_date: date = Field(default_factory=lambda: date.today() - timedelta(days=120))
    to_date: date = Field(default_factory=date.today)
    shock_pct: float = Field(default=-10, ge=-100, le=100)
    quantities: dict[str, float] = Field(default_factory=dict, max_length=20)

    @model_validator(mode='after')
    def check(self):
        if self.to_date < self.from_date or (self.to_date-self.from_date).days > 366 or self.to_date > date.today():
            raise ValueError('History must be an ordered range of at most 366 days, ending today or earlier')
        if set(self.quantities) - set(self.instrument_keys): raise ValueError('Quantities require matching instrument keys')
        if any(abs(v) > 1_000_000_000 for v in self.quantities.values()): raise ValueError('Quantity magnitude exceeds supported range')
        return self


class Limits(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    movement_pct: float = Field(default=5, gt=0, le=100)
    spread_bps: float = Field(default=25, gt=0, le=10000)
    depth_drop_pct: float = Field(default=50, gt=0, le=100)
    annualized_volatility: float = Field(default=.40, gt=0, le=10)
    gross_exposure_inr: float = Field(default=1_000_000, gt=0)
    loss_inr: float = Field(default=10_000, gt=0)
    stale_seconds: float = Field(default=120, ge=10, le=3600)


class RiskQuery(StressQuery):
    limits: Limits = Field(default_factory=Limits)


class StreamQuery(Query):
    mode: Literal['full', 'full_d30'] = 'full'


def fail(exc):
    raise HTTPException(exc.status, detail={'code': exc.code}) from None


@router.get('/status')
async def status():
    return {**broker.status(), 'websocket': stream.status(), 'monitor': monitor.status()}


@router.post('/account')
async def account():
    return await broker.account()


@router.post('/liquidity')
async def liquidity(q: Query):
    if not q.instrument_keys: raise HTTPException(422, 'At least one instrument key is required')
    try:
        if stream.state == 'CONNECTED' and all(k in stream.quotes for k in q.instrument_keys):
            return {'source': 'UPSTOX_WEBSOCKET', 'transport': 'WEBSOCKET', 'retrieved_at': now(),
                    'quotes': [normalize_quote(k, stream.quotes[k]) for k in q.instrument_keys],
                    'missing_instruments': [], 'depth_changes': [], 'depth_limit': 30 if stream.mode == 'full_d30' else 5}
        return await broker.liquidity(q.instrument_keys)
    except ProviderError as e: fail(e)


@router.post('/stress')
async def stress(q: StressQuery):
    if not q.instrument_keys: raise HTTPException(422, 'At least one instrument key is required')
    try: return await broker.stress(q.instrument_keys, str(q.from_date), str(q.to_date), q.shock_pct, q.quantities)
    except ProviderError as e: fail(e)


@router.post('/risk')
async def risk(q: RiskQuery):
    if not q.instrument_keys: raise HTTPException(422, 'At least one instrument key is required')
    return await broker.risk(q.instrument_keys, q.limits.model_dump(), str(q.from_date), str(q.to_date), stream.status())


@router.post('/stream/start')
async def start(q: StreamQuery):
    if not q.instrument_keys: raise HTTPException(422, 'At least one instrument key is required')
    try: return await stream.start(q.instrument_keys, q.mode)
    except ProviderError as e: fail(e)


@router.post('/stream/stop')
async def stop():
    return await stream.stop()


class Monitor:
    def __init__(self): self.task, self.latest, self.error = None, None, None
    def status(self): return {'running': bool(self.task and not self.task.done()), 'interval_seconds': 30, 'latest': self.latest, 'error': self.error, 'persistence': 'PROCESS_LOCAL'}
    async def run(self, q):
        while True:
            try:
                self.latest = await broker.risk(q.instrument_keys, q.limits.model_dump(), str(q.from_date), str(q.to_date), stream.status())
                self.error = None
            except Exception: self.error = 'MONITOR_EVALUATION_FAILED'
            await asyncio.sleep(30)
    async def stop(self):
        if self.task:
            self.task.cancel()
            try: await self.task
            except asyncio.CancelledError: pass
        self.task = None


monitor = Monitor()


@router.post('/monitor/start')
async def monitor_start(q: RiskQuery):
    if not q.instrument_keys: raise HTTPException(422, 'At least one instrument key is required')
    await monitor.stop()
    monitor.task = asyncio.create_task(monitor.run(q))
    return monitor.status()


@router.post('/monitor/stop')
async def monitor_stop():
    await monitor.stop()
    return monitor.status()
