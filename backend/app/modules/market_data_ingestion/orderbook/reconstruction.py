"""
Module 02: Market Data Ingestion Engine - Real-Time Order Book Reconstruction Engine.
Maintains an in-memory double-sided price ladder (Bids sorted descending, Asks sorted ascending).
Applies Level 2 snapshots, processes incremental deltas, verifies sequence continuity,
and detects sequence gaps requiring snapshot resynchronization.
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from backend.app.modules.market_data_ingestion.normalization.schemas import (
    OrderBookDelta,
    OrderBookLevel,
    OrderBookOperation,
    OrderBookSide,
    OrderBookSnapshot,
)


class OrderBookSequenceError(Exception):
    """Raised when sequence continuity is broken in delta stream."""
    pass


class ReconstructedOrderBook:
    """
    Maintains the state of an instrument's limit order book.
    - bids: price -> (quantity, order_count) [descending]
    - asks: price -> (quantity, order_count) [ascending]
    """

    def __init__(self, instrument_id: str):
        self.instrument_id = instrument_id
        self.bids: Dict[Decimal, Tuple[Decimal, Optional[int]]] = {}
        self.asks: Dict[Decimal, Tuple[Decimal, Optional[int]]] = {}
        self.last_sequence: int = 0
        self.is_synchronized: bool = False
        self.snapshot_timestamp: Optional[Any] = None

    def apply_snapshot(self, snapshot: OrderBookSnapshot) -> None:
        """Resets the book and initializes price levels from a full L2 snapshot."""
        self.bids.clear()
        self.asks.clear()

        for b in snapshot.bids:
            self.bids[b.price] = (b.quantity, b.order_count)
        for a in snapshot.asks:
            self.asks[a.price] = (a.quantity, a.order_count)

        self.last_sequence = snapshot.snapshot_sequence
        self.snapshot_timestamp = snapshot.snapshot_timestamp
        self.is_synchronized = True

    def apply_delta(self, delta: OrderBookDelta) -> None:
        """
        Applies an incremental update (INSERT, UPDATE, DELETE) to the reconstructed book.
        Enforces strict sequence continuity (delta.sequence_number == last_sequence + 1).
        """
        if not self.is_synchronized:
            raise OrderBookSequenceError(f"Cannot apply delta to unsynchronized order book for {self.instrument_id}")

        # Gap detection
        expected_seq = self.last_sequence + 1
        if delta.sequence_number != expected_seq:
            self.is_synchronized = False
            raise OrderBookSequenceError(
                f"Order book sequence gap detected for {self.instrument_id}! "
                f"Expected {expected_seq}, received {delta.sequence_number}."
            )

        side_dict = self.bids if delta.side == OrderBookSide.BID else self.asks

        if delta.operation == OrderBookOperation.DELETE or delta.quantity <= Decimal("0"):
            side_dict.pop(delta.price, None)
        elif delta.operation in (OrderBookOperation.INSERT, OrderBookOperation.UPDATE):
            side_dict[delta.price] = (delta.quantity, delta.order_count)

        self.last_sequence = delta.sequence_number

    def get_top_of_book(self) -> Tuple[Optional[Tuple[Decimal, Decimal]], Optional[Tuple[Decimal, Decimal]]]:
        """Returns ((best_bid_price, best_bid_qty), (best_ask_price, best_ask_qty))."""
        best_bid = None
        best_ask = None

        if self.bids:
            sorted_bids = sorted(self.bids.keys(), reverse=True)
            best_bid_p = sorted_bids[0]
            best_bid = (best_bid_p, self.bids[best_bid_p][0])

        if self.asks:
            sorted_asks = sorted(self.asks.keys())
            best_ask_p = sorted_asks[0]
            best_ask = (best_ask_p, self.asks[best_ask_p][0])

        return best_bid, best_ask

    def get_depth_snapshot(self, depth: int = 5) -> Dict[str, Any]:
        """Exports ordered top-N bid and ask levels."""
        sorted_bids = sorted(self.bids.keys(), reverse=True)[:depth]
        sorted_asks = sorted(self.asks.keys())[:depth]

        bid_levels = [
            {"price": str(p), "quantity": str(self.bids[p][0]), "order_count": self.bids[p][1], "level": idx + 1}
            for idx, p in enumerate(sorted_bids)
        ]
        ask_levels = [
            {"price": str(p), "quantity": str(self.asks[p][0]), "order_count": self.asks[p][1], "level": idx + 1}
            for idx, p in enumerate(sorted_asks)
        ]

        total_bid_qty = sum(self.bids[p][0] for p in sorted_bids)
        total_ask_qty = sum(self.asks[p][0] for p in sorted_asks)

        return {
            "instrument_id": self.instrument_id,
            "last_sequence": self.last_sequence,
            "is_synchronized": self.is_synchronized,
            "total_bid_qty": str(total_bid_qty),
            "total_ask_qty": str(total_ask_qty),
            "bids": bid_levels,
            "asks": ask_levels,
        }


class OrderBookManager:
    """Manages active order book reconstructions for multiple instruments."""

    def __init__(self):
        self._books: Dict[str, ReconstructedOrderBook] = {}

    def get_or_create_book(self, instrument_id: str) -> ReconstructedOrderBook:
        if instrument_id not in self._books:
            self._books[instrument_id] = ReconstructedOrderBook(instrument_id)
        return self._books[instrument_id]

    def clear(self) -> None:
        self._books.clear()
