"""
M03.05 - Shared Event Identity Resolver.
Builds deterministic idempotency keys and canonical payload fingerprints (SHA-256).
Enforces hierarchy:
1. Provider Event ID
2. Exchange Trade ID
3. Sequence ID + Connection Epoch
4. Composite Fingerprint
"""

import hashlib
import json
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from backend.app.modules.market_data_quality.duplicate_detection.schemas import EventDetectionInput


class EventIdentityResolver:
    """
    Resolves stable idempotency keys and cryptographic fingerprints.
    Guarantees cross-restart stability by excluding volatile local arrival timestamps.
    """

    @staticmethod
    def _to_clean_decimal(val: Any) -> Optional[str]:
        if val is None:
            return None
        try:
            d = Decimal(str(val))
            # Standardize representation
            return f"{d:.6f}"
        except Exception:
            return str(val)

    @classmethod
    def compute_payload_fingerprint(cls, input_data: EventDetectionInput) -> str:
        """
        Computes SHA-256 fingerprint from immutable business contents.
        Excludes volatile local machine/process timestamps.
        """
        content_dict = {
            "provider_id": input_data.provider_id.upper(),
            "feed_id": input_data.feed_id,
            "instrument_id": input_data.instrument_id.upper(),
            "exchange": input_data.exchange.upper(),
            "event_type": input_data.event_type.upper(),
            "event_timestamp": input_data.event_timestamp.isoformat(),
            "price": cls._to_clean_decimal(input_data.price),
            "quantity": cls._to_clean_decimal(input_data.quantity),
            "side": (input_data.side or "").upper(),
            "trade_condition": input_data.trade_condition or "",
            "interval": input_data.interval or "",
            "raw_payload": input_data.raw_payload or {}
        }
        serialized = json.dumps(content_dict, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def resolve_identity(
        cls, input_data: EventDetectionInput
    ) -> Tuple[str, str, str, str]:
        """
        Determines the idempotency key and identity strategy.
        Returns (idempotency_key, identity_strategy, identity_scope, canonical_table).
        """
        provider = input_data.provider_id.upper()
        feed = input_data.feed_id
        inst = input_data.instrument_id.upper()
        exch = input_data.exchange.upper()
        ev_type = input_data.event_type.upper()

        # Map event type to canonical storage table
        table_map = {
            "TRADE": "market_trade_events",
            "QUOTE": "normalized_market_ticks",
            "TICK": "normalized_market_ticks",
            "SNAPSHOT": "order_book_snapshots",
            "DELTA": "order_book_deltas",
            "OHLCV": "market_ohlcv",
        }
        canonical_table = table_map.get(ev_type, "raw_market_events")

        # 1. Exchange Trade ID (Highest priority for trades)
        if ev_type == "TRADE" and input_data.exchange_trade_id:
            trade_date = input_data.event_timestamp.strftime("%Y%m%d")
            scope = f"{exch}:{inst}:{trade_date}"
            key = f"TRD_EXCH:{scope}:{input_data.exchange_trade_id}"
            return key, "EXCHANGE_TRADE_ID", scope, canonical_table

        # 2. Provider Event ID
        if input_data.provider_event_id:
            scope = f"{provider}:{feed}:{inst}:{ev_type}"
            key = f"PRV_EVT:{scope}:{input_data.provider_event_id}"
            return key, "PROVIDER_EVENT_ID", scope, canonical_table

        # 3. Sequence Identity (with connection epoch)
        if input_data.sequence_number is not None:
            epoch = input_data.connection_epoch or 1
            scope = f"{provider}:{feed}:{inst}:{ev_type}:ep{epoch}"
            key = f"SEQ:{scope}:{input_data.sequence_number}"
            return key, "SEQUENCE_ID", scope, canonical_table

        # 4. OHLCV Bar Natural Identity
        if ev_type == "OHLCV" and input_data.interval:
            bar_start = input_data.event_timestamp.strftime("%Y%m%d_%H%M%S")
            scope = f"{provider}:{feed}:{inst}:{input_data.interval}"
            key = f"OHLCV:{scope}:{bar_start}"
            return key, "OHLCV_NATURAL_KEY", scope, canonical_table

        # 5. Composite Fingerprint Fallback
        fingerprint = cls.compute_payload_fingerprint(input_data)
        scope = f"{provider}:{feed}:{inst}:{ev_type}"
        key = f"FINGERPRINT:{scope}:{fingerprint[:32]}"
        return key, "COMPOSITE_FINGERPRINT", scope, canonical_table
