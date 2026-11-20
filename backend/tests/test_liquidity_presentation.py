from datetime import datetime, timezone, timedelta, date
from decimal import Decimal as D
from types import SimpleNamespace
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from backend.app.main import app  # registers related models
from backend.app.core.database import Base
from backend.app.modules.dashboard_visualization.liquidity_dashboard.services.presentation import summarize_daily_bars, regular_session
from backend.app.modules.dashboard_visualization.liquidity_dashboard.services.liquidity_dashboard_service import LiquidityDashboardService
from backend.app.modules.dashboard_visualization.liquidity_dashboard.schemas.liquidity_dashboard_schemas import CurrentQuoteItem, InstrumentLiquidityScore
from backend.app.modules.market_microstructure.order_book_depth.models import OrderBookDepthSnapshot, OrderBookDepthLevel


@pytest.fixture
async def session():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


def test_daily_turnover_is_native_currency_average_not_total():
    result = summarize_daily_bars([(date(2026,1,1),10,100),(date(2026,1,2),20,300)],'INR','test')
    assert result['adv_shares'] == D(200)
    assert result['adtv_native'] == D(3500)
    assert result['currency'] == 'INR'
    assert result['observation_count'] == 2


def test_absent_volume_is_not_replaced_with_assumed_adv():
    assert summarize_daily_bars([], 'USD', 'test')['adv_shares'] is None


def test_calendar_assumptions_distinguish_india_and_us_without_inventing_status():
    assert regular_session('JPL.NS')['session_minutes'] == 375
    assert regular_session('AAPL')['session_minutes'] == 390
    assert regular_session('AAPL')['session_status'] == 'UNKNOWN'


async def profile_service(session, monkeypatch, symbol, member=True, adv=D(1000)):
    svc=LiquidityDashboardService(session)
    async def quote(_): return CurrentQuoteItem(instrument_id=symbol,symbol=symbol,mid_price=D(100),spread_bps=D(2),currency='INR' if symbol.endswith('.NS') else 'USD')
    async def context(_): return regular_session(symbol)
    async def score(_): return InstrumentLiquidityScore(instrument_id=symbol,symbol=symbol,composite_score=D(75),liquidity_bucket='TIER_1_HIGH',calculated_at=datetime.now(timezone.utc),adv_shares_20d=adv)
    async def vals(_): return [SimpleNamespace(instrument_id=symbol,signed_quantity=D(100),signed_market_value_base=D(10000))] if member else []
    monkeypatch.setattr(svc,'get_current_quote',quote);monkeypatch.setattr(svc,'get_market_context',context);monkeypatch.setattr(svc,'get_instrument_liquidity_score',score);monkeypatch.setattr(svc,'_latest_valuations',vals)
    return svc


@pytest.mark.parametrize('symbol,minutes',[('JPL.NS',375),('AAPL',390)])
async def test_execution_duration_and_cost_reconcile(session,monkeypatch,symbol,minutes):
    svc=await profile_service(session,monkeypatch,symbol)
    p=await svc.get_instrument_liquidation_profile(symbol,'PORT_TEST',D('.1'))
    full=p.scenarios[-1]
    assert full.estimated_duration_minutes == D(minutes)
    assert full.estimated_trading_days == 1
    assert full.total_cost_usd == (full.notional_value*full.total_cost_bps/D(10000)).quantize(D('.01'))
    assert p.currency == ('INR' if symbol.endswith('.NS') else 'USD')


async def test_unknown_instrument_is_not_assumed_to_be_a_holding(session,monkeypatch):
    svc=await profile_service(session,monkeypatch,'JPL.NS',member=False)
    p=await svc.get_instrument_liquidation_profile('JPL.NS','PORT_TEST')
    assert not p.is_portfolio_holding
    assert p.current_position_shares == 0
    assert all(s.total_cost_usd == 0 for s in p.scenarios)


async def test_missing_adv_returns_no_estimate(session,monkeypatch):
    svc=await profile_service(session,monkeypatch,'AAPL',adv=None)
    p=await svc.get_instrument_liquidation_profile('AAPL','PORT_TEST')
    assert p.model_status == 'INSUFFICIENT_ADV'
    assert p.scenarios == []


async def test_configured_calendar_uses_regular_session_duration(session, monkeypatch):
    from backend.app.modules.dashboard_visualization.liquidity_dashboard.services import presentation
    from backend.app.modules.instrument_reference_data.trading_calendar.models import SessionType
    start=datetime(2026,11,19,9,15,tzinfo=timezone.utc)
    occurrence=SimpleNamespace(trade_matching_permitted=True,session_type=SessionType.REGULAR_TRADING,utc_start=start,utc_end=start+timedelta(minutes=210),local_start=start,local_end=start+timedelta(minutes=210))
    async def resolve(self,*args):return SimpleNamespace(resolved_trading_date=date(2026,11,19),scheduled_trading_permitted=True,calendar_id='SPECIAL')
    async def schedule(self,*args):return SimpleNamespace(sessions=[occurrence],timezone_name='Asia/Kolkata')
    monkeypatch.setattr(presentation.TradingCalendarService,'resolve_session',resolve)
    monkeypatch.setattr(presentation.TradingCalendarService,'get_day_schedule',schedule)
    result=await presentation.market_context(session,'JPL.NS','JPL.NS')
    assert result['session_minutes']==210
    assert result['session_status']=='SCHEDULED_OPEN'


async def test_depth_history_uses_only_requested_levels_and_excludes_demo(session,monkeypatch):
    svc=LiquidityDashboardService(session)
    async def quote(_):return CurrentQuoteItem(instrument_id='AAPL',symbol='AAPL',currency='USD')
    monkeypatch.setattr(svc,'get_current_quote',quote)
    now=datetime.now(timezone.utc)
    for i,feed in enumerate(['PROVIDER','PROVIDER','DEMO']):
        key=f'D{i}'
        session.add(OrderBookDepthSnapshot(depth_snapshot_id=key,instrument_id='AAPL',exchange='NASDAQ',venue='NASDAQ',source_feed_id=feed,event_timestamp=now-timedelta(minutes=i+1),calculation_config_id='CFG'))
        for level in range(1,6):
            for side in ['BID','ASK']:
                session.add(OrderBookDepthLevel(level_id=f'{key}-{side}-{level}',depth_snapshot_id=key,side=side,level_index=level,price=D(100),displayed_quantity=D(10),displayed_notional=D(1000),cumulative_quantity=D(10*level),cumulative_notional=D(1000*level)))
    await session.commit()
    result=await svc.get_depth_history('AAPL',levels=3)
    assert len(result['points']) == 2
    assert all(p['bid'] == 3000 and p['ask'] == 3000 for p in result['points'])


async def test_score_does_not_relabel_inr_turnover_as_usd(session,monkeypatch):
    svc=LiquidityDashboardService(session)
    async def score(_):return InstrumentLiquidityScore(instrument_id='JPL.NS',symbol='JPL.NS',composite_score=D(75),liquidity_bucket='TIER_1_HIGH',calculated_at=datetime.now(timezone.utc))
    async def quote(_):return CurrentQuoteItem(instrument_id='JPL.NS',symbol='JPL.NS',currency='INR')
    async def volume(*args):return {'adv_shares':D(200),'adtv_native':D(3500),'observation_count':20,'source':'recorded','as_of':'2026-01-01'}
    monkeypatch.setattr(svc,'_read_instrument_liquidity_score',score);monkeypatch.setattr(svc,'get_current_quote',quote)
    monkeypatch.setattr('backend.app.modules.dashboard_visualization.liquidity_dashboard.services.liquidity_dashboard_service.volume_context',volume)
    result=await svc.get_instrument_liquidity_score('JPL.NS')
    assert result.adtv_native_20d == 3500
    assert result.adtv_usd_20d is None
    assert result.currency == 'INR'


@pytest.mark.parametrize('quantity',[D(0),D(25),D(-12)])
async def test_local_remove_uses_actual_account_and_preserves_ledger(monkeypatch,quantity):
    from backend.app.modules.dashboard_visualization.liquidity_dashboard.router import remove_local_position
    from backend.app.modules.portfolio_management.position_management.services.service import PositionManagementService
    from backend.app.modules.portfolio_management.position_management.models import PositionStatus, PositionEventType
    book=SimpleNamespace(position_id='POS_REAL',account_id='ACTUAL_ACCOUNT',listing_id='NSE_LISTING',position_status=PositionStatus.OPEN)
    snap=SimpleNamespace(net_signed_quantity=quantity,settled_quantity=quantity,unsettled_quantity=D(0),snapshot_version=4)
    class Result:
        def scalars(self):return self
        def all(self):return [book]
        def scalar_one_or_none(self):return snap
    class DB:
        async def execute(self,*args):return Result()
        async def commit(self):pass
    calls=[]
    async def apply(self,req):calls.append(req)
    monkeypatch.setattr(PositionManagementService,'apply_position_event',apply)
    result=await remove_local_position('PORT_TEST','RELIANCE.NS',DB())
    assert result['broker_order_sent'] is False
    assert book.position_status == PositionStatus.CLOSED
    if quantity:
        assert calls[0].account_id == 'ACTUAL_ACCOUNT'
        assert calls[0].listing_id == 'NSE_LISTING'
        assert calls[0].signed_quantity_delta == -quantity
        assert calls[0].event_type == PositionEventType.POSITION_CORRECTION
    else:
        assert calls == []


async def test_local_removal_persists_and_disappears_from_overview(session, monkeypatch):
    from sqlalchemy import select, func
    from backend.app.modules.portfolio_management.portfolio_creation.models import Portfolio
    from backend.app.modules.instrument_reference_data.instrument_master.models import Instrument
    from backend.app.modules.portfolio_management.position_management.models import PositionBook,PositionSnapshot,PositionEvent
    from backend.app.modules.portfolio_management.position_management.schemas import PositionEventRegisterRequest
    from backend.app.modules.portfolio_management.position_management.services.service import PositionManagementService
    from backend.app.modules.dashboard_visualization.liquidity_dashboard.router import remove_local_position
    session.add(Portfolio(portfolio_id='PORT_REMOVE',portfolio_code='PORT_REMOVE',portfolio_name='Removal test',short_name='Test',base_currency='USD',lifecycle_status='ACTIVE',portfolio_type='DISCRETIONARY',creation_source='MANUAL_ADMINISTRATION',market_scope='UNITED_STATES',created_by='TEST'))
    session.add(Instrument(instrument_id='TEST_STOCK',canonical_name='Test stock',short_name='TEST_STOCK',instrument_type='COMMON_STOCK',asset_class='EQUITY',issue_currency='USD'))
    await session.commit()
    service=PositionManagementService(session)
    await service.apply_position_event(PositionEventRegisterRequest(portfolio_id='PORT_REMOVE',account_id='ACTUAL_ACCOUNT',instrument_id='TEST_STOCK',event_type='TRADE_BUY',signed_quantity_delta=D(25),idempotency_key='TEST_OPEN'))
    from backend.app.modules.dashboard_visualization.liquidity_dashboard.schemas.liquidity_dashboard_schemas import OrderBookDepthLadder
    async def quote(self, instrument_id):return CurrentQuoteItem(instrument_id=instrument_id,symbol=instrument_id,mid_price=D(100),spread_bps=D(2),currency='USD')
    async def score(self, instrument_id):return InstrumentLiquidityScore(instrument_id=instrument_id,symbol=instrument_id,composite_score=D(75),liquidity_bucket='TIER_1_HIGH',calculated_at=datetime.now(timezone.utc),adv_shares_20d=D(1000))
    async def depth(self, instrument_id, levels_count=5):return OrderBookDepthLadder(instrument_id=instrument_id,symbol=instrument_id,levels_count=levels_count,snapshot_timestamp=datetime.now(timezone.utc))
    monkeypatch.setattr(LiquidityDashboardService,'get_current_quote',quote)
    monkeypatch.setattr(LiquidityDashboardService,'get_instrument_liquidity_score',score)
    monkeypatch.setattr(LiquidityDashboardService,'get_order_book_depth_ladder',depth)
    first=await LiquidityDashboardService(session).get_portfolio_liquidity_overview('PORT_REMOVE')
    assert first.holdings[0].position_shares == 25
    assert first.total_nav == 2500
    await service.apply_position_event(PositionEventRegisterRequest(portfolio_id='PORT_REMOVE',account_id='SECOND_ACCOUNT',instrument_id='TEST_STOCK',event_type='TRADE_BUY',signed_quantity_delta=D(10),idempotency_key='TEST_ADD'))
    updated=await LiquidityDashboardService(session).get_portfolio_liquidity_overview('PORT_REMOVE')
    assert len(updated.holdings)==1
    assert updated.holdings[0].position_shares == 35
    assert updated.total_nav == 3500
    await remove_local_position('PORT_REMOVE','TEST_STOCK',session)
    book=(await session.execute(select(PositionBook).where(PositionBook.account_id=='ACTUAL_ACCOUNT'))).scalar_one()
    snapshot=(await session.execute(select(PositionSnapshot).order_by(PositionSnapshot.snapshot_version.desc()).limit(1))).scalar_one()
    assert snapshot.net_signed_quantity == 0
    assert book.position_status.value == 'CLOSED'
    count=(await session.execute(select(func.count()).select_from(PositionEvent))).scalar_one()
    assert count == 4
    await remove_local_position('PORT_REMOVE','TEST_STOCK',session)
    assert (await session.execute(select(func.count()).select_from(PositionEvent))).scalar_one() == count
    overview=await LiquidityDashboardService(session).get_portfolio_liquidity_overview('PORT_REMOVE')
    assert overview.holdings == []


async def test_conversion_is_timestamped_and_missing_fx_is_not_one(monkeypatch):
    from backend.app.modules.dashboard_visualization.liquidity_dashboard.services.presentation import conversion_rate
    from backend.app.modules.market_data_ingestion.adapters.yfinance import latest_quote
    async def valid(symbol):return {'status':'available','price':0.012,'currency':'USD','source_time':datetime.now(timezone.utc).isoformat()}
    monkeypatch.setattr(latest_quote,'latest_market_quote',valid)
    rate, stamp, source=await conversion_rate('INR','USD')
    assert rate==D('.012') and stamp and 'INRUSD=X' in source
    async def missing(symbol):return {'status':'unavailable'}
    monkeypatch.setattr(latest_quote,'latest_market_quote',missing)
    assert (await conversion_rate('INR','USD'))[0] is None
