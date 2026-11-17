from types import SimpleNamespace
import logging
import httpx
import pytest
from fastapi import FastAPI
from backend.app.modules.external_data.service import ExternalDataService, ProviderError, provider_status, SecretQueryFilter
from backend.app.modules.external_data.router import router


def config(**overrides):
    return SimpleNamespace(**{'SEC_USER_AGENT': 'Test test@example.com', 'FRED_API_KEY': 'test-secret',
        'FMP_API_KEY': 'test-secret', 'UPSTOX_ACCESS_TOKEN': 'test-token',
        'ALPHA_VANTAGE_API_KEY': 'test-secret', 'ALPHA_VANTAGE_ENABLED': True, **overrides})


@pytest.mark.asyncio
@pytest.mark.parametrize('provider,operation,params,payload,host', [
    ('sec_edgar','company_facts',{'cik':'320193'},{'facts':{'us-gaap':{}}},'data.sec.gov'),
    ('sec_edgar','submissions',{'cik':'320193'},{'filings':{'recent':{}}},'data.sec.gov'),
    ('fred','observations',{'series_id':'DGS10'},{'observations':[{'value':'.','date':'2026-01-01'}]},'api.stlouisfed.org'),
    ('fmp','income_statement',{'symbol':'IBM'},[{'symbol':'IBM','revenue':123}],'financialmodelingprep.com'),
    ('upstox','holdings',{}, {'status':'success','data':[{'quantity':1}]},'api.upstox.com'),
    ('upstox_news','news',{'category':'holdings'},{'status':'success','data':[{'headline':'test'}]},'api.upstox.com'),
])
async def test_provider_contracts(provider, operation, params, payload, host):
    def handler(request):
        assert request.method == 'GET' and request.url.host == host
        if provider == 'sec_edgar':
            assert request.url.path.endswith('CIK0000320193.json')
            assert request.headers['User-Agent'] == 'Test test@example.com'
        if provider.startswith('upstox'):
            assert request.headers['Authorization'] == 'Bearer test-token'
        return httpx.Response(200, json=payload)
    result = await ExternalDataService(config(), httpx.MockTransport(handler)).fetch(provider, operation, params)
    assert result['data'] == payload
    assert result['quality_status'] == 'RAW_UNVALIDATED'


@pytest.mark.asyncio
@pytest.mark.parametrize('code,payload,expected', [
    (429,{},'PROVIDER_RATE_LIMIT'), (403,{},'PROVIDER_CREDENTIAL_OR_ENTITLEMENT_DENIED'),
    (200,{'error_code':400},'PROVIDER_REJECTED_REQUEST'),
    (200,{'Information':'secret text'},'PROVIDER_NOTICE_QUOTA_OR_ENTITLEMENT'),
    (200,{'observations':[]},'NO_DATA'), (200,{'unrelated':1},'UNEXPECTED_PROVIDER_SCHEMA'),
])
async def test_provider_errors_never_become_data(code,payload,expected):
    service = ExternalDataService(config(), httpx.MockTransport(lambda r: httpx.Response(code,json=payload)))
    with pytest.raises(ProviderError) as exc:
        await service.fetch('fred','observations',{'series_id':'DGS10'})
    assert exc.value.code == expected


@pytest.mark.asyncio
async def test_missing_credentials_and_paid_providers_never_call_network():
    def unexpected(_):
        pytest.fail('Network must not be called')
    service = ExternalDataService(config(FRED_API_KEY=None),httpx.MockTransport(unexpected))
    for provider,op,p in [('fred','observations',{'series_id':'DGS10'}),('nse','quotes',{}),
                          ('bse','quotes',{}),('databento','trades',{}),('rbi_dbie','observations',{})]:
        with pytest.raises(ProviderError):
            await service.fetch(provider,op,p)


@pytest.mark.asyncio
async def test_no_url_or_credential_injection():
    service = ExternalDataService(config())
    for params in [{'series_id':'DGS10','api_key':'attacker'},{'series_id':'DGS10','url':'http://localhost'},
                   {'series_id':'DGS10','limit':-1}]:
        with pytest.raises(ProviderError):
            await service.fetch('fred','observations',params)


@pytest.mark.asyncio
async def test_routes_require_authentication():
    app = FastAPI()
    app.include_router(router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        assert (await client.get('/api/v1/external-data/providers')).status_code == 401
        assert (await client.post('/api/v1/external-data/upstox/holdings',json={})).status_code == 401


def test_status_and_logs_do_not_leak_secrets():
    assert 'test-secret' not in str(provider_status(config()))
    record = logging.LogRecord('httpx',20,'',1,'GET https://example.com/?api_key=test-secret&symbol=IBM',(),None)
    SecretQueryFilter().filter(record)
    assert 'test-secret' not in record.getMessage()


def test_unknown_streaming_provider_cannot_silently_simulate():
    from backend.app.modules.market_data_ingestion.adapters.registry import ProviderAdapterRegistry
    with pytest.raises(ValueError):
        ProviderAdapterRegistry.get_or_create_adapter('test', 'FRED')
