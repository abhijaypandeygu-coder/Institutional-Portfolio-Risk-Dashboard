"""
Module 02: Market Data Ingestion Engine - Data Normalization Engine.
Parses heterogeneous provider payloads into standardized canonical models:
MarketTick, OHLCVCandle, TradeEvent, OrderBookSnapshot, OrderBookDelta, ProviderHeartbeat.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple, Union

from backend.app.modules.market_data_ingestion.normalization.schemas import (
    IngestionError,
    MarketTick,
    OHLCVCandle,
    OrderBookDelta,
    OrderBookLevel,
    OrderBookOperation,
    OrderBookSide,
    OrderBookSnapshot,
    ProviderHeartbeat,
    TradeEvent,
)


def parse_iso_datetime(dt_val: Union[str, datetime]) -> datetime:
    if isinstance(dt_val, datetime):
        return dt_val if dt_val.tzinfo else dt_val.replace(tzinfo=timezone.utc)
    # Parse string
    try:
        dt = datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


class NormalizationEngine:
    """Transforms raw dictionary payloads into validated canonical events."""

    @staticmethod
    def normalize_tick(payload: Dict[str, Any]) -> MarketTick:
        return MarketTick(
            event_id=payload.get("event_id") or payload.get("provider_event_id"),
            provider_event_id=payload.get("provider_event_id"),
            feed_id=str(payload["feed_id"]),
            instrument_id=str(payload.get("instrument_id") or f"EQ_{payload['symbol']}"),
            exchange=payload.get("exchange", "NSE"),
            symbol=payload["symbol"],
            last_traded_price=Decimal(str(payload["last_price"])),
            last_traded_quantity=Decimal(str(payload["last_qty"])),
            best_bid_price=Decimal(str(payload["best_bid"])) if payload.get("best_bid") else None,
            best_bid_quantity=Decimal(str(payload["best_bid_qty"])) if payload.get("best_bid_qty") else None,
            best_ask_price=Decimal(str(payload["best_ask"])) if payload.get("best_ask") else None,
            best_ask_quantity=Decimal(str(payload["best_ask_qty"])) if payload.get("best_ask_qty") else None,
            event_timestamp=parse_iso_datetime(payload.get("timestamp")),
            provider_sequence=payload.get("sequence"),
            source_metadata={"provider": payload.get("provider_id", "UNKNOWN")},
        )

    @staticmethod
    def normalize_trade(payload: Dict[str, Any]) -> TradeEvent:
        aggressor = None
        if payload.get("aggressor_side"):
            side_str = str(payload["aggressor_side"]).upper()
            aggressor = OrderBookSide.BID if "BID" in side_str or "BUY" in side_str else OrderBookSide.ASK

        return TradeEvent(
            event_id=payload.get("event_id"),
            provider_trade_id=payload.get("provider_trade_id"),
            feed_id=str(payload["feed_id"]),
            instrument_id=str(payload.get("instrument_id") or f"EQ_{payload['symbol']}"),
            exchange=payload.get("exchange", "NSE"),
            price=Decimal(str(payload["price"])),
            quantity=Decimal(str(payload["quantity"])),
            trade_timestamp=parse_iso_datetime(payload.get("timestamp")),
            aggressor_side=aggressor,
            sequence_number=payload.get("sequence"),
            source_metadata={"provider": payload.get("provider_id")},
        )

    @staticmethod
    def normalize_snapshot(payload: Dict[str, Any]) -> OrderBookSnapshot:
        bids = [
            OrderBookLevel(
                price=Decimal(str(b["price"])),
                quantity=Decimal(str(b["quantity"])),
                order_count=b.get("order_count"),
                level_position=int(b.get("level_position", idx + 1)),
            )
            for idx, b in enumerate(payload.get("bids", []))
        ]
        asks = [
            OrderBookLevel(
                price=Decimal(str(a["price"])),
                quantity=Decimal(str(a["quantity"])),
                order_count=a.get("order_count"),
                level_position=int(a.get("level_position", idx + 1)),
            )
            for idx, a in enumerate(payload.get("asks", []))
        ]
        return OrderBookSnapshot(
            event_id=payload.get("event_id"),
            feed_id=str(payload["feed_id"]),
            instrument_id=str(payload.get("instrument_id") or f"EQ_{payload['symbol']}"),
            exchange=payload.get("exchange", "NSE"),
            snapshot_sequence=int(payload["sequence"]),
            snapshot_timestamp=parse_iso_datetime(payload.get("timestamp")),
            bids=bids,
            asks=asks,
            source_metadata={"provider": payload.get("provider_id")},
        )

    @staticmethod
    def normalize_delta(payload: Dict[str, Any]) -> OrderBookDelta:
        side_val = OrderBookSide.BID if payload["side"].upper() == "BID" else OrderBookSide.ASK
        op_map = {
            "INSERT": OrderBookOperation.INSERT,
            "UPDATE": OrderBookOperation.UPDATE,
            "DELETE": OrderBookOperation.DELETE,
        }
        op = op_map.get(payload["operation"].upper(), OrderBookOperation.UPDATE)

        return OrderBookDelta(
            event_id=payload.get("event_id"),
            feed_id=str(payload["feed_id"]),
            instrument_id=str(payload.get("instrument_id") or f"EQ_{payload['symbol']}"),
            exchange=payload.get("exchange", "NSE"),
            sequence_number=int(payload["sequence"]),
            previous_sequence_number=payload.get("previous_sequence"),
            event_timestamp=parse_iso_datetime(payload.get("timestamp")),
            side=side_val,
            price=Decimal(str(payload["price"])),
            quantity=Decimal(str(payload["quantity"])),
            operation=op,
            order_count=payload.get("order_count"),
        )

    @staticmethod
    def normalize_heartbeat(payload: Dict[str, Any]) -> ProviderHeartbeat:
        return ProviderHeartbeat(
            feed_id=str(payload["feed_id"]),
            provider_id=str(payload["provider_id"]),
            heartbeat_timestamp=parse_iso_datetime(payload.get("timestamp")),
            connection_id=payload.get("connection_id"),
        )

    @classmethod
    def normalize_event(cls, payload: Dict[str, Any]) -> Tuple[str, Any]:
        """Auto-detects message type and normalizes payload."""
        msg_type = payload.get("msg_type", "").upper()
        if msg_type == "TICK":
            return "TICK", cls.normalize_tick(payload)
        elif msg_type == "TRADE":
            return "TRADE", cls.normalize_trade(payload)
        elif msg_type == "SNAPSHOT":
            return "SNAPSHOT", cls.normalize_snapshot(payload)
        elif msg_type == "DELTA":
            return "DELTA", cls.normalize_delta(payload)
        elif msg_type == "HEARTBEAT":
            return "HEARTBEAT", cls.normalize_heartbeat(payload)
        else:
            raise ValueError(f"Unknown message type '{msg_type}'")
