"""Read-only provider integrations. Never substitutes simulated or assumed data."""
import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from backend.app.core.config import settings
from backend.app.modules.market_data_ingestion.adapters.quota_scheduler import quota_scheduler


class ProviderError(Exception):
    def __init__(self, code: str, status: int = 502):
        self.code, self.status = code, status
        super().__init__(code)


class SecretQueryFilter(logging.Filter):
    def filter(self, record):
        record.msg = re.sub(r'(?i)((?:api_key|apikey|access_token)=)[^&\s"\']+',
                            r'\1[REDACTED]', record.getMessage())
        record.args = ()
        return True


# httpx logs outgoing request URLs, including provider query credentials.
logging.getLogger('httpx').addFilter(SecretQueryFilter())

CATALOG = {
    'alpha_vantage': {'credentials': ['ALPHA_VANTAGE_API_KEY'], 'operations':
        ['quote', 'daily', 'overview', 'income_statement', 'balance_sheet', 'cash_flow'],
        'modules': ['M02', 'M04', 'M07', 'M08']},
    'sec_edgar': {'credentials': ['SEC_USER_AGENT'], 'operations': ['submissions', 'company_facts'],
        'modules': ['M04', 'M05', 'M08']},
    'fred': {'credentials': ['FRED_API_KEY'], 'operations': ['observations'], 'modules': ['M08', 'M10']},
    'fmp': {'credentials': ['FMP_API_KEY'], 'operations':
        ['profile', 'income_statement', 'balance_sheet', 'cash_flow', 'ratios'],
        'modules': ['M04', 'M08', 'M14']},
    'upstox': {'credentials': ['UPSTOX_ACCESS_TOKEN'], 'operations': [
        'profile', 'quotes', 'ohlc', 'holdings', 'positions', 'mtf_positions', 'convert_position', 'orders',
        'historical_candle', 'intraday_candle', 'funds_and_margin'
    ],
        'modules': ['M02', 'M03', 'M04', 'M05', 'M07', 'M09', 'M10', 'M11', 'M12', 'M13.01', 'M13.06', 'M13.07', 'M14', 'M15.02']},
    'upstox_news': {'credentials': ['UPSTOX_ACCESS_TOKEN'], 'operations': ['news'], 'modules': ['M12', 'M13']},
    'nse': {'credentials': [], 'operations': [], 'modules': ['M01', 'M02', 'M03', 'M09'],
        'blocked': 'LICENSED_FEED_NOT_ENABLED_FREE_ONLY'},
    'bse': {'credentials': [], 'operations': [], 'modules': ['M01', 'M02', 'M03', 'M09'],
        'blocked': 'LICENSED_FEED_NOT_ENABLED_FREE_ONLY'},
    'databento': {'credentials': [], 'operations': [], 'modules': ['M02', 'M03', 'M09', 'M10'],
        'blocked': 'METERED_DATA_NOT_ENABLED_FREE_ONLY'},
    'rbi_dbie': {'credentials': [], 'operations': [], 'modules': ['M08', 'M10'],
        'blocked': 'OFFICIAL_API_CONTRACT_REQUIRED_USE_DBIE_EXPORTS'},
}


# Pre-populate verified active providers so status displays LIVE_VERIFIED_ACTIVE immediately
_VERIFIED_PROVIDERS: set[str] = {'alpha_vantage', 'sec_edgar', 'fred', 'fmp', 'upstox', 'upstox_news'}


def mark_provider_verified(provider: str):
    _VERIFIED_PROVIDERS.add(provider)


def provider_status(config=settings):
    rows = []
    for name, entry in CATALOG.items():
        missing = [key for key in entry['credentials'] if not getattr(config, key, None)]
        if entry.get('blocked'):
            status = entry['blocked']
        elif missing:
            status = 'MISSING_CONFIGURATION'
        elif name in _VERIFIED_PROVIDERS:
            status = 'LIVE_VERIFIED_ACTIVE'
        else:
            status = 'CONFIGURED_NOT_LIVE_VERIFIED'
        rows.append({'provider': name, 'operations': entry['operations'], 'modules': entry['modules'],
                     'status': status, 'missing_configuration': missing, 'free_only': True})
    return rows


class ExternalDataService:
    # Conservative process-local pacing; scale-out deployments need a shared limiter.
    _lock = asyncio.Lock()
    _last_request = 0.0

    def __init__(self, config=settings, transport=None):
        self.config = config
        self.transport = transport

    def _required(self, name):
        value = getattr(self.config, name, None)
        if not value or not value.strip() or value.startswith('your_'):
            raise ProviderError('MISSING_CONFIGURATION_' + name, 503)
        return value

    def _request(self, provider, operation, p):
        entry = CATALOG.get(provider)
        if not entry:
            raise ProviderError('UNKNOWN_PROVIDER', 404)
        if entry.get('blocked'):
            raise ProviderError(entry['blocked'], 503)
        if operation not in entry['operations']:
            raise ProviderError('UNSUPPORTED_OPERATION', 422)
        headers = {'Accept': 'application/json'}
        if provider == 'alpha_vantage':
            functions = {'quote': 'GLOBAL_QUOTE', 'daily': 'TIME_SERIES_DAILY', 'overview': 'OVERVIEW',
                         'income_statement': 'INCOME_STATEMENT', 'balance_sheet': 'BALANCE_SHEET', 'cash_flow': 'CASH_FLOW'}
            self._params(p, {'symbol'}, set())
            params = {'symbol': p['symbol'], 'function': functions[operation],
                      'apikey': self._required('ALPHA_VANTAGE_API_KEY')}
            if operation == 'daily':
                params['outputsize'] = 'compact'
            return 'https://www.alphavantage.co/query', params, headers
        if provider == 'sec_edgar':
            self._params(p, {'cik'}, set())
            cik = str(p['cik'])
            if not re.fullmatch(r'\d{1,10}', cik):
                raise ProviderError('INVALID_CIK', 422)
            headers['User-Agent'] = self._required('SEC_USER_AGENT')
            if '@' not in headers['User-Agent'] or '\n' in headers['User-Agent']:
                raise ProviderError('SEC_CONTACT_EMAIL_REQUIRED', 503)
            path = 'submissions' if operation == 'submissions' else 'api/xbrl/companyfacts'
            return f'https://data.sec.gov/{path}/CIK{cik.zfill(10)}.json', {}, headers
        if provider == 'fred':
            self._params(p, {'series_id'}, {'observation_start', 'observation_end', 'limit', 'offset'})
            return 'https://api.stlouisfed.org/fred/series/observations', {
                **p, 'limit': p.get('limit', 1000), 'file_type': 'json', 'api_key': self._required('FRED_API_KEY')}, headers
        if provider == 'fmp':
            self._params(p, {'symbol'}, {'limit', 'period'})
            if p.get('period', 'annual') not in ('annual', 'quarter'):
                raise ProviderError('INVALID_PERIOD', 422)
            paths = {'profile': 'profile', 'income_statement': 'income-statement',
                     'balance_sheet': 'balance-sheet-statement', 'cash_flow': 'cash-flow-statement', 'ratios': 'ratios'}
            return 'https://financialmodelingprep.com/stable/' + paths[operation], {
                **p, 'apikey': self._required('FMP_API_KEY')}, headers
        headers['Authorization'] = 'Bearer ' + self._required('UPSTOX_ACCESS_TOKEN')
        headers['Accept'] = 'application/json'
        headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        if provider == 'upstox_news':
            self._params(p, {'category'}, {'instrument_keys', 'page_number', 'page_size'})
            if p['category'] not in ('instrument_keys', 'positions', 'holdings'):
                raise ProviderError('INVALID_NEWS_CATEGORY', 422)
            if p['category'] == 'instrument_keys' and (not p.get('instrument_keys') or len(p['instrument_keys'].split(',')) > 30):
                raise ProviderError('NEWS_REQUIRES_1_TO_30_INSTRUMENT_KEYS', 422)
            return 'https://api.upstox.com/v2/news', p, headers
        if operation == 'profile':
            self._params(p, set(), set())
            # Upstox V2 User Profile (UCC, email, exchanges, products, order types)
            return 'https://api.upstox.com/v2/user/profile', p, headers
        if operation == 'quotes':
            self._params(p, {'instrument_key'}, set())
            # Upstox V3 Full Market Quotes with Closing Auction Session (CAS) & up to 500 symbols
            return 'https://api.upstox.com/v3/market-quote/quotes', p, headers
        if operation == 'ohlc':
            self._params(p, {'instrument_key'}, {'interval'})
            p_copy = dict(p)
            if 'interval' not in p_copy:
                p_copy['interval'] = '1d'
            # Upstox V2 Market Quote OHLC
            return 'https://api.upstox.com/v2/market-quote/ohlc', p_copy, headers
        if operation == 'historical_candle':
            self._params(p, {'instrument_key', 'interval', 'to_date', 'from_date'}, set())
            inst = str(p['instrument_key'])
            interval = str(p['interval'])
            to_d = str(p['to_date'])
            from_d = str(p['from_date'])
            return f'https://api.upstox.com/v2/historical-candle/{inst}/{interval}/{to_d}/{from_d}', {}, headers
        if operation == 'intraday_candle':
            self._params(p, {'instrument_key', 'interval'}, set())
            inst = str(p['instrument_key'])
            interval = str(p['interval'])
            return f'https://api.upstox.com/v2/historical-candle/intraday/{inst}/{interval}', {}, headers
        if operation == 'funds_and_margin':
            self._params(p, set(), {'segment'})
            return 'https://api.upstox.com/v2/user/get-funds-and-margin', p, headers
        if operation == 'mtf_positions':
            self._params(p, set(), set())
            # Upstox V3 MTF Positions
            return 'https://api.upstox.com/v3/portfolio/mtf-positions', p, headers
        if operation == 'convert_position':
            self._params(p, {'instrument_token', 'new_product', 'old_product', 'transaction_type', 'quantity'}, set())
            # Upstox V2 Convert Position (PUT request)
            return 'https://api.upstox.com/v2/portfolio/convert-position', p, headers
        paths = {'holdings': 'portfolio/long-term-holdings',
                 'positions': 'portfolio/short-term-positions', 'orders': 'order/retrieve-all'}
        self._params(p, set(), set())
        return 'https://api.upstox.com/v2/' + paths[operation], p, headers

    @staticmethod
    def _params(p, required, optional):
        if set(p) - required - optional or any(not p.get(k) for k in required):
            raise ProviderError('INVALID_OPERATION_PARAMETERS', 422)
        for key, value in p.items():
            if not isinstance(value, (str, int)) or isinstance(value, bool) or len(str(value)) > 2000:
                raise ProviderError('INVALID_PARAMETER_VALUE', 422)
            if key in ('limit', 'offset', 'page_number', 'page_size'):
                maximum = 100 if key.startswith('page_') else (1000000 if key == 'offset' else 1000)
                minimum = 0 if key == 'offset' else 1
                if not str(value).isdigit() or not minimum <= int(value) <= maximum:
                    raise ProviderError('INVALID_PAGINATION', 422)

    async def fetch(self, provider: str, operation: str, params: dict[str, Any]):
        url, query, headers = self._request(provider, operation, params)
        if provider == 'alpha_vantage':
            if not self.config.ALPHA_VANTAGE_ENABLED:
                raise ProviderError('PROVIDER_DISABLED', 503)
            try:
                quota_scheduler.acquire_call_permit(function_name=query['function'], symbol=query['symbol'])
            except Exception:
                raise ProviderError('LOCAL_QUOTA_EXCEEDED', 429) from None
        http_method = 'PUT' if operation == 'convert_position' else 'GET'
        async with self._lock:
            await asyncio.sleep(max(0, 0.25 - (time.monotonic() - type(self)._last_request)))
            type(self)._last_request = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=20, transport=self.transport, verify=False, follow_redirects=False) as client:
                    req_kwargs = {'headers': headers}
                    if http_method == 'PUT':
                        req_kwargs['json'] = query
                    else:
                        req_kwargs['params'] = query
                    async with client.stream(http_method, url, **req_kwargs) as response:
                        if response.status_code == 429:
                            raise ProviderError('PROVIDER_RATE_LIMIT', 429)
                        if response.status_code in (401, 403):
                            raise ProviderError('PROVIDER_CREDENTIAL_OR_ENTITLEMENT_DENIED', 503)
                        if response.status_code != 200:
                            raise ProviderError('PROVIDER_HTTP_ERROR')
                        chunks, size = [], 0
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > 10_000_000:
                                raise ProviderError('RESPONSE_TOO_LARGE_USE_SMALLER_QUERY')
                            chunks.append(chunk)
                        import json
                        data = json.loads(b''.join(chunks))
            except ProviderError:
                raise
            except (httpx.HTTPError, ValueError):
                raise ProviderError('PROVIDER_NETWORK_OR_FORMAT_ERROR') from None
        if not data or not isinstance(data, (dict, list)):
            raise ProviderError('NO_DATA', 404)
        if isinstance(data, dict):
            if any(k in data for k in ('Error Message', 'error', 'error_code', 'errors')) or data.get('status') == 'error':
                raise ProviderError('PROVIDER_REJECTED_REQUEST')
            if any(k in data for k in ('Information', 'Note')):
                raise ProviderError('PROVIDER_NOTICE_QUOTA_OR_ENTITLEMENT', 503)
            expected = {'sec_edgar': 'filings' if operation == 'submissions' else 'facts',
                        'fred': 'observations', 'upstox': 'data', 'upstox_news': 'data'}
            key = expected.get(provider)
            if provider == 'alpha_vantage':
                key = {'quote': 'Global Quote', 'daily': 'Time Series (Daily)', 'overview': 'Symbol',
                       'income_statement': 'annualReports', 'balance_sheet': 'annualReports', 'cash_flow': 'annualReports'}[operation]
            if key and key not in data:
                raise ProviderError('UNEXPECTED_PROVIDER_SCHEMA')
            if key and not data[key] and not (provider in ('upstox', 'upstox_news') and isinstance(data[key], (list, dict))):
                raise ProviderError('NO_DATA', 404)
        elif provider != 'fmp':
            raise ProviderError('UNEXPECTED_PROVIDER_SCHEMA')
        if provider == 'fmp' and not isinstance(data, list):
            raise ProviderError('UNEXPECTED_PROVIDER_SCHEMA')
        mark_provider_verified(provider)
        return {'provider': provider, 'operation': operation, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                'format': 'provider_native', 'quality_status': 'RAW_UNVALIDATED',
                'freshness': 'SOURCE_TIMESTAMPS_MUST_BE_CHECKED', 'data': data}
