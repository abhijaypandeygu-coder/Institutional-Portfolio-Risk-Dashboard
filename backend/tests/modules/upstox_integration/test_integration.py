import asyncio
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from backend.app.core.config import settings
from backend.app.modules.external_data.service import ProviderError
from backend.app.modules.upstox_integration.service import (
    BrokerService, normalize_quote, history_inputs, evaluate_rules, DEFAULT_LIMITS,
)
from backend.app.modules.upstox_integration.router import Query, StressQuery, router
from backend.app.modules.upstox_integration.stream import StreamManager

KEY = 'NSE_EQ|TEST'


def raw(**kw):
    return {'instrument_token': KEY, 'symbol': 'TEST', 'timestamp': datetime.now(timezone.utc).isoformat(),
            'last_price': 110, 'ohlc': {'close': 100}, 'depth': {
                'buy': [{'price': 99, 'quantity': 30}, {'price': 100, 'quantity': 10}],
                'sell': [{'price': 102, 'quantity': 20}, {'price': 0, 'quantity': 0}]}, **kw}


def test_hand_calculated_spread_depth_imbalance_and_movement():
    q = normalize_quote(KEY, raw())
    assert q['best_bid'] == 100 and q['best_ask'] == 102
    assert q['spread_bps'] == pytest.approx(2/101*10000)
    assert q['bid_ask_imbalance'] == pytest.approx(1/3)
    assert q['movement_pct'] == pytest.approx(10)
    assert q['depth_levels'] == 1 and q['freshness'] == 'FRESH'


def test_missing_depth_and_price_are_unavailable():
    q = normalize_quote(KEY, {})
    assert q['ltp'] is None and q['spread_bps'] is None and q['bid_ask_imbalance'] is None
    assert q['freshness'] == 'UNKNOWN' and q['book_state'] == 'UNAVAILABLE'


def test_provider_single_digit_fractional_second_timestamp():
    stamp=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')+'.9+00:00'
    assert normalize_quote(KEY,raw(timestamp=stamp))['freshness']=='FRESH'


def test_v3_uses_explicit_previous_close_for_market_movement():
    q=normalize_quote(KEY,raw(prev_close_price=100,ohlc={'close':110}))
    assert q['movement_pct']==pytest.approx(10)


def test_stale_quotes_do_not_trigger_price_rules():
    q = normalize_quote(KEY, raw(timestamp=(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat()))
    codes = [a['code'] for a in evaluate_rules([q], {}, DEFAULT_LIMITS, {})]
    assert codes == ['STALE_OR_UNDATED_QUOTE']


def test_comparable_depth_deterioration_and_loss_rules():
    q = normalize_quote(KEY, raw())
    previous = {KEY: {'timestamp': 'earlier', 'visible_depth_quantity': 200}}
    codes = {a['code'] for a in evaluate_rules([q], previous, DEFAULT_LIMITS,
        {'position_pnl': -20000, 'gross_position_exposure': 2000000}, volatility=.5)}
    assert {'LIQUIDITY_DETERIORATION','POSITION_PNL_LOSS_LIMIT','POSITION_GROSS_EXPOSURE_LIMIT','VOLATILITY_THRESHOLD'} <= codes


def test_daily_history_sorted_deduplicated_and_volatility():
    rows = [[f'2026-01-{i:02d}',0,0,0,100+i,100] for i in range(1,25)]
    h = history_inputs(list(reversed(rows))+[rows[0]])
    assert len(h['points']) == 24 and h['return_observations'] == 23
    assert h['annualized_volatility'] > 0
    assert history_inputs(rows[:5])['annualized_volatility'] is None


@pytest.mark.parametrize('keys', [['invalid'],['NSE_EQ|X/evil'],['NSE_EQ|X','NSE_EQ|X']])
def test_invalid_keys_rejected(keys):
    with pytest.raises(ValidationError): Query(instrument_keys=keys)


def test_quantity_keys_and_dates_validated():
    with pytest.raises(ValidationError): StressQuery(instrument_keys=[KEY],quantities={'other':1})
    with pytest.raises(ValidationError): StressQuery(instrument_keys=[KEY],from_date='2026-02-02',to_date='2026-01-01')
    with pytest.raises(ValidationError): StressQuery(instrument_keys=[KEY],quantities={KEY:float('nan')})


@pytest.mark.asyncio
async def test_broker_empty_account_is_valid_not_fabricated():
    async def handler(req):
        assert req.headers['Authorization'] == 'Bearer token'
        assert req.url.host == 'api.upstox.com'
        if 'funds' in req.url.path: data={'equity':{'available_margin':0,'used_margin':0}}
        elif 'status' in req.url.path: data={'status':'NORMAL_CLOSE'}
        else: data=[]
        return httpx.Response(200,json={'status':'success','data':data})
    b = BrokerService(SimpleNamespace(UPSTOX_ACCESS_TOKEN='token'), httpx.MockTransport(handler))
    r = await b.account()
    assert r['status'] == 'AVAILABLE' and r['positions'] == []
    assert r['position_pnl'] == 0 and r['gross_position_exposure'] == 0
    assert r['scope'] == 'CONFIGURED_BROKER_ACCOUNT' and r['currency'] == 'INR'


@pytest.mark.asyncio
async def test_expired_token_errors_are_sanitized():
    transport = httpx.MockTransport(lambda r:httpx.Response(401,json={'errors':[{'message':'token secret'}]}))
    b=BrokerService(SimpleNamespace(UPSTOX_ACCESS_TOKEN='secret'),transport)
    r=await b.account()
    assert r['status']=='UNAVAILABLE' and r['positions'] is None
    assert 'secret' not in str(r)


@pytest.mark.asyncio
async def test_scenario_keeps_short_quantity_sign():
    b=BrokerService()
    async def liquidity(keys,stale_seconds=120):return {'quotes':[{'instrument_key':KEY,'ltp':100,'freshness':'FRESH'}]}
    async def request(*args,**kw):return {'candles':[]}
    b.liquidity,b.request=liquidity,request
    r=await b.stress([KEY],'2026-01-01','2026-01-31',-10,{KEY:-2})
    assert r['scenario_pnl']==20 and r['components'][0]['baseline_value']==-200


@pytest.mark.asyncio
async def test_all_integrated_routes_enforce_operator_role():
    app=FastAPI();app.include_router(router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        for path in ['account','liquidity','risk','stress','stream/start','monitor/start']:
            assert (await c.post('/api/v1/broker/upstox/'+path,json={})).status_code==401
            assert (await c.post('/api/v1/broker/upstox/'+path,json={},headers={'X-API-Key':settings.API_KEY_READ_ONLY})).status_code==403


def test_official_protobuf_decoding_keeps_actual_depth():
    from upstox_client.feeder.proto.MarketDataFeedV3_pb2 import FeedResponse
    response=FeedResponse()
    market=response.feeds[KEY].fullFeed.marketFF
    market.ltpc.ltp=100;market.ltpc.cp=99;market.ltpc.ltt=1795060449000
    level=market.marketLevel.bidAskQuote.add();level.bidP=99;level.bidQ=10;level.askP=101;level.askQ=20
    s=StreamManager();s.keys=[KEY];s.decode(response.SerializeToString())
    q=normalize_quote(KEY,s.quotes[KEY])
    assert q['best_bid']==99 and q['best_ask']==101 and q['depth_levels']==1


@pytest.mark.asyncio
async def test_paid_depth_not_enabled_by_default():
    if not settings.UPSTOX_ALLOW_30_LEVEL:
        with pytest.raises(ProviderError) as exc:await StreamManager().start([KEY],'full_d30')
        assert exc.value.code=='THIRTY_LEVEL_ENTITLEMENT_NOT_ENABLED'
