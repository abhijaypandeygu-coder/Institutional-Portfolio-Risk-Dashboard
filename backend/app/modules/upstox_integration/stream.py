"""TLS-verified V3 stream. Uses official SDK protobuf types, not its socket transport."""
import asyncio
import copy
import json
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from backend.app.core.config import settings
from backend.app.modules.external_data.service import ProviderError
from .service import broker, now


class StreamManager:
    def __init__(self):
        self.task = None
        self.keys = []
        self.mode = 'full'
        self.state = 'DISCONNECTED'
        self.last_message = None
        self.last_error = None
        self.quotes = {}
        self.lock = asyncio.Lock()

    def status(self):
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(self.last_message)).total_seconds() if self.last_message else None
        return {'status': self.state, 'subscriptions': list(self.keys), 'mode': self.mode,
                'depth_entitlement': 30 if self.mode == 'full_d30' else 5,
                'last_message_at': self.last_message, 'error': self.last_error,
                'last_message_age_seconds': age,
                'message_freshness': 'UNKNOWN' if age is None else ('STALE' if age > 120 else 'FRESH'),
                'subscription_scope': 'CONFIGURED_BROKER_ACCOUNT', 'tls_verification': True}

    async def start(self, keys, mode):
        if mode == 'full_d30' and not settings.UPSTOX_ALLOW_30_LEVEL:
            raise ProviderError('THIRTY_LEVEL_ENTITLEMENT_NOT_ENABLED', 403)
        try:
            from upstox_client.feeder.proto import MarketDataFeedV3_pb2  # noqa
            import websockets  # noqa
        except ImportError:
            raise ProviderError('INSTALL_BACKEND_REQUIREMENTS_UPSTOX', 503) from None
        async with self.lock:
            await self.stop()
            # Fail synchronously on expired credentials instead of returning CONNECTED.
            auth = await broker.request('stream_authorize')
            url = auth.get('authorized_redirect_uri', '')
            parsed = urlparse(url)
            if parsed.scheme != 'wss' or not parsed.hostname or not parsed.hostname.endswith('.upstox.com'):
                raise ProviderError('INVALID_AUTHORIZED_STREAM_HOST')
            self.keys, self.mode = list(keys), mode
            self.state, self.last_error = 'CONNECTING', None
            self.task = asyncio.create_task(self._run(url))
            return self.status()

    async def stop(self):
        if self.task:
            self.task.cancel()
            try: await self.task
            except asyncio.CancelledError: pass
        self.task = None
        self.state = 'DISCONNECTED'
        self.keys, self.quotes = [], {}
        return self.status()

    def decode(self, message):
        from google.protobuf.json_format import MessageToDict
        from upstox_client.feeder.proto.MarketDataFeedV3_pb2 import FeedResponse
        decoded = MessageToDict(FeedResponse.FromString(message))
        for key, feed in decoded.get('feeds', {}).items():
            if key not in self.keys: continue
            full = feed.get('fullFeed', {})
            market = full.get('marketFF') or full.get('indexFF') or {}
            ltpc = market.get('ltpc') or feed.get('ltpc') or {}
            depth = market.get('marketLevel', {}).get('bidAskQuote', [])
            ltt = ltpc.get('ltt')
            timestamp = datetime.fromtimestamp(int(ltt) / 1000, timezone.utc).isoformat() if ltt else None
            self.quotes[key] = {'instrument_token': key, 'symbol': key, 'last_price': ltpc.get('ltp'),
                                'ohlc': {'close': ltpc.get('cp')}, 'timestamp': timestamp,
                                'volume': market.get('vtt'), 'depth': {
                                    'buy': [{'price': d.get('bidP'), 'quantity': d.get('bidQ')} for d in depth],
                                    'sell': [{'price': d.get('askP'), 'quantity': d.get('askQ')} for d in depth]}}
        return decoded

    async def _run(self, url):
        import websockets
        for attempt in range(3):
            try:
                # Default SSL context verifies the server certificate and hostname.
                async with websockets.connect(url, open_timeout=15, ping_interval=20,
                                              ping_timeout=20, max_size=2_000_000, max_queue=8) as socket:
                    await socket.send(json.dumps({'guid': str(uuid.uuid4()), 'method': 'sub',
                                                  'data': {'instrumentKeys': self.keys, 'mode': self.mode}}).encode())
                    self.state = 'CONNECTED'
                    async for message in socket:
                        if isinstance(message, bytes): self.decode(message)
                        self.last_message = now()
                self.last_error = 'STREAM_CLOSED'
            except asyncio.CancelledError:
                raise
            except Exception:
                # Exception messages may contain authorized URLs/tokens.
                self.last_error = 'STREAM_CONNECTION_OR_DECODE_FAILED'
            self.state = 'RECONNECTING'
            await asyncio.sleep(2 ** attempt)
        self.state = 'ERROR'


stream = StreamManager()
