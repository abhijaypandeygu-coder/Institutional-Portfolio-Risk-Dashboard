import asyncio
import base64
import copy
import hashlib
import json
import math
import statistics
import time
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
from dateutil.parser import isoparse

from backend.app.core.config import settings
from backend.app.modules.external_data.service import ExternalDataService, ProviderError


def now():
    return datetime.now(timezone.utc).isoformat()


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def normalize_quote(key, raw, stale_seconds=120):
    """Missing/zero depth is unavailable, never fabricated. Prices remain INR."""
    def levels(side, reverse):
        rows = []
        for r in raw.get('depth', {}).get(side, []):
            price, quantity = number(r.get('price')), number(r.get('quantity'))
            if price is not None and price > 0 and quantity is not None and quantity > 0:
                rows.append({'price': price, 'quantity': quantity, 'orders': r.get('orders')})
        return sorted(rows, key=lambda r: r['price'], reverse=reverse)
    bids, asks = levels('buy', True), levels('sell', False)
    bid, ask = bids[0]['price'] if bids else None, asks[0]['price'] if asks else None
    mid = (bid + ask) / 2 if bid is not None and ask is not None else None
    spread = ask - bid if mid else None
    bq, aq = sum(r['quantity'] for r in bids), sum(r['quantity'] for r in asks)
    timestamp = raw.get('timestamp')
    age = None
    try:
        dt = isoparse(str(timestamp))
        if dt.tzinfo: age = max(0, (datetime.now(timezone.utc) - dt).total_seconds())
    except ValueError:
        pass
    ltp = number(raw.get('last_price'))
    # V3 OHLC close can be today's latest candle, not yesterday's close.
    close = number(raw.get('prev_close_price', raw.get('ohlc', {}).get('close')))
    return {'instrument_key': raw.get('instrument_token') or key, 'symbol': raw.get('symbol') or key,
            'currency': 'INR', 'ltp': ltp, 'previous_close': close,
            'movement_pct': (ltp / close - 1) * 100 if ltp is not None and close and close > 0 else None,
            'timestamp': timestamp, 'age_seconds': age,
            'freshness': 'UNKNOWN' if age is None else ('STALE' if age > stale_seconds else 'FRESH'),
            'bids': bids, 'asks': asks, 'depth_levels': min(len(bids), len(asks)),
            'best_bid': bid, 'best_ask': ask, 'midpoint': mid, 'spread': spread,
            'spread_bps': spread / mid * 10000 if spread is not None and mid else None,
            'book_state': 'UNAVAILABLE' if mid is None else ('CROSSED' if spread < 0 else ('LOCKED' if spread == 0 else 'NORMAL')),
            'bid_ask_imbalance': (bq - aq) / (bq + aq) if bids and asks and bq + aq else None,
            'visible_depth_quantity': bq + aq if bids and asks else None,
            'volume': number(raw.get('volume', raw.get('ohlc', {}).get('volume')))}


def history_inputs(candles):
    # V2 timestamps are ISO dates; sort ascending and deduplicate by timestamp.
    rows = {}
    for c in candles:
        if len(c) >= 6:
            close = number(c[4])
            if close is not None and close > 0:
                rows[str(c[0])] = {'timestamp': str(c[0]), 'close': close, 'volume': number(c[5])}
    points = [rows[k] for k in sorted(rows)]
    returns = [math.log(b['close'] / a['close']) for a, b in zip(points, points[1:])]
    vol = statistics.stdev(returns) * math.sqrt(252) if len(returns) >= 20 else None
    return {'points': points, 'return_observations': len(returns),
            'annualized_volatility': vol, 'volatility_method': 'sample standard deviation of daily log returns × sqrt(252)',
            'status': 'AVAILABLE' if vol is not None else 'INSUFFICIENT_HISTORY'}


def evaluate_rules(quotes, previous, limits, portfolio, volatility=None, market_status=None, stream=None):
    alerts = []
    def add(code, value=None, limit=None, key=None):
        alerts.append({'code': code, 'value': value, 'limit': limit, 'instrument_key': key,
                       'observed_at': now(), 'source': 'UPSTOX', 'status': 'TRIGGERED'})
    for q in quotes:
        key = q['instrument_key']
        if q['freshness'] != 'FRESH':
            add('STALE_OR_UNDATED_QUOTE', q['age_seconds'], limits['stale_seconds'], key)
            continue
        if q['movement_pct'] is not None and abs(q['movement_pct']) >= limits['movement_pct']:
            add('ABNORMAL_PRICE_MOVEMENT', q['movement_pct'], limits['movement_pct'], key)
        if q['spread_bps'] is not None and q['spread_bps'] >= limits['spread_bps']:
            add('WIDE_SPREAD', q['spread_bps'], limits['spread_bps'], key)
        old = previous.get(key, {})
        before, current = old.get('visible_depth_quantity'), q['visible_depth_quantity']
        if before and current is not None and old.get('timestamp') != q['timestamp']:
            drop = (before - current) / before * 100
            if drop >= limits['depth_drop_pct']: add('LIQUIDITY_DETERIORATION', drop, limits['depth_drop_pct'], key)
    if volatility is not None and volatility >= limits['annualized_volatility']:
        add('VOLATILITY_THRESHOLD', volatility, limits['annualized_volatility'])
    if portfolio.get('gross_position_exposure') is not None and portfolio['gross_position_exposure'] > limits['gross_exposure_inr']:
        add('POSITION_GROSS_EXPOSURE_LIMIT', portfolio['gross_position_exposure'], limits['gross_exposure_inr'])
    if portfolio.get('position_pnl') is not None and portfolio['position_pnl'] < -limits['loss_inr']:
        add('POSITION_PNL_LOSS_LIMIT', portfolio['position_pnl'], -limits['loss_inr'])
    if market_status and market_status != 'NORMAL_OPEN': add('MARKET_NOT_NORMAL_OPEN', market_status)
    if stream and (stream.get('status') == 'ERROR' or (stream.get('status') == 'DISCONNECTED' and stream.get('subscriptions'))):
        add('STREAM_DISCONNECTED')
    if stream and stream.get('status') == 'CONNECTED' and stream.get('message_freshness') == 'STALE':
        add('STREAM_MESSAGES_STALE', stream.get('last_message_age_seconds'), 120)
    return alerts


DEFAULT_LIMITS = {'movement_pct': 5.0, 'spread_bps': 25.0, 'depth_drop_pct': 50.0,
                  'annualized_volatility': 0.40, 'gross_exposure_inr': 1_000_000.0,
                  'loss_inr': 10_000.0, 'stale_seconds': 120.0}


class BrokerService:
    """One configured broker account. Does not merge broker records into local test portfolios."""
    def __init__(self, config=settings, transport=None):
        self.config, self.transport = config, transport
        self.cache, self.previous, self.liquidity_previous = {}, {}, {}
        self.lock = asyncio.Lock()
        self.diagnostics = {}

    async def request(self, operation, params=None):
        params = params or {}
        # Token fingerprint invalidates cache on token rotation without exposing token.
        token = self.config.UPSTOX_ACCESS_TOKEN or ''
        identity = hashlib.sha256(token.encode()).hexdigest()
        cache_key = (identity, operation, json.dumps(params, sort_keys=True))
        async with self.lock:
            cached = self.cache.get(cache_key)
            if cached and time.monotonic() - cached[0] < 15:
                return copy.deepcopy(cached[1])
            try:
                if operation in ('market_status', 'stream_authorize'):
                    if not token: raise ProviderError('MISSING_CONFIGURATION_UPSTOX_ACCESS_TOKEN', 503)
                    path = 'v2/market/status/NSE' if operation == 'market_status' else 'v3/feed/market-data-feed/authorize'
                    async with httpx.AsyncClient(timeout=15, transport=self.transport, follow_redirects=False) as client:
                        r = await client.get('https://api.upstox.com/' + path, headers={'Authorization': 'Bearer ' + token})
                    if r.status_code != 200: raise ProviderError('UPSTOX_ACCESS_DENIED' if r.status_code in (401, 403) else 'UPSTOX_HTTP_ERROR', 503)
                    envelope = r.json()
                    if envelope.get('status') != 'success': raise ProviderError('UPSTOX_REJECTED_REQUEST')
                    result = envelope['data']
                else:
                    envelope = await ExternalDataService(self.config, self.transport).fetch('upstox', operation, params)
                    result = envelope['data']['data']
                self.diagnostics[operation] = {'status': 'SUCCESS', 'checked_at': now()}
                self.cache[cache_key] = (time.monotonic(), copy.deepcopy(result))
                if len(self.cache) > 100: self.cache.pop(next(iter(self.cache)))
                return result
            except (ProviderError, httpx.HTTPError, ValueError, KeyError) as exc:
                self.diagnostics[operation] = {'status': 'ERROR', 'code': exc.code if isinstance(exc, ProviderError) else 'UPSTOX_NETWORK_OR_SCHEMA_ERROR', 'checked_at': now()}
                raise ProviderError(self.diagnostics[operation]['code'], 503) from None

    async def account(self):
        results, errors = {}, {}
        for op in ('holdings', 'positions', 'funds_and_margin', 'market_status'):
            try: results[op] = await self.request(op)
            except ProviderError as e: errors[op] = e.code
        holdings, positions = results.get('holdings'), results.get('positions')
        keys = list(dict.fromkeys(r.get('instrument_token') for rows in (holdings, positions)
                                 if isinstance(rows, list) for r in rows if r.get('instrument_token')))
        quotes = []
        if keys:
            try: quotes = (await self.liquidity(keys[:20]))['quotes']
            except ProviderError as e: errors['holding_quotes'] = e.code
        def complete_sum(rows, field):
            if not isinstance(rows, list): return None
            values = [number(r.get(field)) for r in rows]
            return sum(values) if all(v is not None for v in values) else None
        exposure = None
        if isinstance(positions, list):
            values = [(number(r.get('quantity')), number(r.get('last_price'))) for r in positions]
            if all(q is not None and p is not None for q, p in values): exposure = sum(abs(q * p) for q, p in values)
        return {'source': 'UPSTOX', 'scope': 'CONFIGURED_BROKER_ACCOUNT', 'currency': 'INR',
                'retrieved_at': now(), 'holdings': holdings, 'positions': positions,
                'position_pnl': complete_sum(positions, 'pnl'), 'holdings_pnl': complete_sum(holdings, 'pnl'),
                'gross_position_exposure': exposure, 'funds_and_margin': results.get('funds_and_margin'),
                'holding_quotes': quotes, 'quote_coverage': {'requested': min(len(keys), 20), 'total': len(keys), 'returned': len(quotes)},
                'market_status': results.get('market_status'), 'errors': errors,
                'status': 'AVAILABLE' if not errors else ('PARTIAL' if results else 'UNAVAILABLE')}

    async def liquidity(self, keys, stale_seconds=120):
        raw = await self.request('quotes', {'instrument_key': ','.join(keys)})
        if not isinstance(raw, dict): raise ProviderError('INVALID_QUOTE_SCHEMA')
        normalized = [normalize_quote(k, v, stale_seconds) for k, v in raw.items() if isinstance(v, dict)]
        matched = {q['instrument_key'] for q in normalized}
        deltas = []
        for q in normalized:
            old = self.liquidity_previous.get(q['instrument_key'])
            deltas.append({'instrument_key': q['instrument_key'],
                           'comparable': bool(old and old['timestamp'] != q['timestamp']),
                           'depth_quantity_change': q['visible_depth_quantity'] - old['visible_depth_quantity']
                           if old and old['timestamp'] != q['timestamp'] and q['visible_depth_quantity'] is not None and old['visible_depth_quantity'] is not None else None})
        self.liquidity_previous.update({q['instrument_key']: copy.deepcopy(q) for q in normalized})
        return {'source': 'UPSTOX_REST', 'transport': 'POLLING', 'retrieved_at': now(), 'currency': 'INR',
                'quotes': normalized, 'missing_instruments': [k for k in keys if k not in matched],
                'depth_changes': deltas, 'depth_limit': 5}

    async def stress(self, keys, from_date, to_date, shock_pct, quantities):
        liquidity = await self.liquidity(keys)
        quotes = {q['instrument_key']: q for q in liquidity['quotes']}
        histories, errors = {}, {}
        for key in keys:
            try:
                data = await self.request('historical_candle', {'instrument_key': key, 'interval': 'day', 'from_date': from_date, 'to_date': to_date})
                histories[key] = history_inputs(data.get('candles', []))
            except ProviderError as e: errors[key] = e.code
        components = []
        for key, quantity in quantities.items():
            q = quotes.get(key)
            price = q.get('ltp') if q else None
            value = quantity * price if price is not None else None
            components.append({'instrument_key': key, 'quantity': quantity, 'price': price,
                               'baseline_value': value, 'stressed_value': value * (1 + shock_pct / 100) if value is not None else None,
                               'pnl': value * shock_pct / 100 if value is not None else None,
                               'freshness': q.get('freshness') if q else 'UNAVAILABLE'})
        vix = None
        try:
            data = await self.liquidity(['NSE_INDEX|India VIX'])
            vix = data['quotes'][0] if data['quotes'] else None
        except ProviderError as e: errors['india_vix'] = e.code
        complete = bool(components) and all(c['pnl'] is not None for c in components)
        return {'source': 'UPSTOX', 'scope': 'EXPLICIT_SCENARIO_QUANTITIES', 'currency': 'INR', 'retrieved_at': now(),
                'history': histories, 'india_vix': vix, 'shock_pct': shock_pct,
                'components': components, 'scenario_pnl': sum(c['pnl'] for c in components) if complete else None,
                'errors': errors, 'assumptions': ['Parallel price shock; no derivatives repricing, FX, fees or liquidity costs.',
                                               'Daily candle history is unadjusted; corporate actions can affect volatility.',
                                               'Current quote timestamps are retained; stale quotes are reference inputs, not live marks.']}

    async def risk(self, keys, limits, from_date, to_date, stream_status):
        account = await self.account()
        errors = dict(account['errors'])
        try: liquidity = await self.liquidity(keys, limits['stale_seconds'])
        except ProviderError as e:
            return {'alerts': [{'code': 'FEED_REQUEST_FAILED', 'source': 'UPSTOX', 'observed_at': now()}], 'errors': {'quotes': e.code}, 'limits': limits}
        vol = None
        if keys:
            try:
                d = await self.request('historical_candle', {'instrument_key': keys[0], 'interval': 'day', 'from_date': from_date, 'to_date': to_date})
                vol = history_inputs(d.get('candles', []))['annualized_volatility']
                if vol is None: errors['volatility'] = 'INSUFFICIENT_HISTORY'
            except ProviderError as e: errors['volatility'] = e.code
        alerts = evaluate_rules(liquidity['quotes'], self.previous, limits, account, vol,
                                (account.get('market_status') or {}).get('status'), stream_status)
        for key in liquidity['missing_instruments']:
            alerts.append({'code': 'MISSING_INSTRUMENT_QUOTE', 'instrument_key': key,
                           'source': 'UPSTOX', 'observed_at': now(), 'status': 'TRIGGERED'})
        self.previous.update({q['instrument_key']: copy.deepcopy(q) for q in liquidity['quotes']})
        return {'scope': 'CONFIGURED_BROKER_ACCOUNT', 'source': 'UPSTOX', 'retrieved_at': now(),
                'alerts': alerts, 'limits': limits, 'errors': errors, 'volatility': vol,
                'volatility_instrument': keys[0] if keys else None,
                'evaluation': 'ON_REQUEST', 'persistence': 'PROCESS_LOCAL', 'liquidity': liquidity}

    def status(self):
        expiry = None
        try:
            # Diagnostic expiry only: JWT payload is not authentication validation.
            part = (self.config.UPSTOX_ACCESS_TOKEN or '').split('.')[1]
            claims = json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))
            expiry = datetime.fromtimestamp(claims['exp'], timezone.utc).isoformat()
        except (ValueError, KeyError, IndexError, TypeError): pass
        return {'source': 'UPSTOX', 'scope': 'CONFIGURED_BROKER_ACCOUNT', 'token_configured': bool(self.config.UPSTOX_ACCESS_TOKEN),
                'token_expiry_unverified': expiry, 'operations': self.diagnostics,
                'transport': 'REST_POLLING_OR_EXPLICIT_WEBSOCKET', 'tls_verification': True}


broker = BrokerService()
