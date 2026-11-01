"""
Module 03.03: Timestamp Validation - Subfeature M03.03.01: Out-of-Order Event Detector.
Tracks per-stream sequence and event-time progression.
Identifies:
- Event-time regressions (timestamp moving backward unexpectedly)
- Sequence regressions (sequence number decreasing without a documented reset)
- Late arrivals within vs. beyond configured reordering tolerance
- Connection epoch resets (reconnection state clears)
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from backend.app.modules.market_data_quality.timestamp_validation.models import (
    FinalTimestampStatus,
    OrderingStatus,
)


@dataclass
class StreamState:
    last_event_timestamp: datetime
    last_sequence_number: Optional[int] = None
    last_receive_timestamp: Optional[datetime] = None
    connection_epoch: int = 1


@dataclass
class OrderingEvaluationResult:
    status: OrderingStatus
    final_status: FinalTimestampStatus
    delta_ms: float
    sequence_delta: Optional[int]
    reason: str


class OutOfOrderDetector:
    """Evaluates event-time monotonicity and sequence continuity per stream."""

    def __init__(self):
        # Key: (provider_id, feed_id, instrument_id, channel) -> StreamState
        self._stream_states: Dict[Tuple[str, str, str, str], StreamState] = {}

    def get_stream_key(
        self, provider_id: str, feed_id: str, instrument_id: str, channel: str
    ) -> Tuple[str, str, str, str]:
        return (provider_id.upper(), feed_id.upper(), instrument_id.upper(), channel.upper())

    def reset_stream_epoch(
        self, provider_id: str, feed_id: str, instrument_id: str, channel: str, new_epoch: int
    ) -> None:
        key = self.get_stream_key(provider_id, feed_id, instrument_id, channel)
        if key in self._stream_states:
            self._stream_states[key].connection_epoch = new_epoch
            self._stream_states[key].last_sequence_number = None

    def evaluate(
        self,
        provider_id: str,
        feed_id: str,
        instrument_id: str,
        channel: str,
        current_event_timestamp: datetime,
        current_sequence: Optional[int] = None,
        receive_timestamp: Optional[datetime] = None,
        connection_epoch: int = 1,
        reordering_tolerance_ms: float = 1000.0,  # Default 1 second grace tolerance
        is_historical_backfill: bool = False,
    ) -> OrderingEvaluationResult:
        """
        Evaluates incoming observation ordering against prior state for this stream.
        """
        key = self.get_stream_key(provider_id, feed_id, instrument_id, channel)
        now_rx = receive_timestamp or datetime.now(timezone.utc)

        # Historical backfills are not evaluated against real-time monotonic stream state,
        # BUT we still update the stream state baseline if no state exists yet!
        if is_historical_backfill:
            if key not in self._stream_states:
                self._stream_states[key] = StreamState(
                    last_event_timestamp=current_event_timestamp,
                    last_sequence_number=current_sequence,
                    last_receive_timestamp=now_rx,
                    connection_epoch=connection_epoch,
                )
            else:
                self._stream_states[key].last_event_timestamp = current_event_timestamp
                if current_sequence is not None:
                    self._stream_states[key].last_sequence_number = current_sequence
            return OrderingEvaluationResult(
                status=OrderingStatus.IN_ORDER,
                final_status=FinalTimestampStatus.VALID,
                delta_ms=0.0,
                sequence_delta=None,
                reason="Historical backfill event bypassed live monotonic ordering check.",
            )

        state = self._stream_states.get(key)
        if state is None or state.connection_epoch != connection_epoch:
            # First event on this stream or new epoch after reconnection
            self._stream_states[key] = StreamState(
                last_event_timestamp=current_event_timestamp,
                last_sequence_number=current_sequence,
                last_receive_timestamp=now_rx,
                connection_epoch=connection_epoch,
            )
            return OrderingEvaluationResult(
                status=OrderingStatus.IN_ORDER,
                final_status=FinalTimestampStatus.VALID,
                delta_ms=0.0,
                sequence_delta=None,
                reason="Initial event on stream, sequence initialized.",
            )

        delta_ms = (current_event_timestamp - state.last_event_timestamp).total_seconds() * 1000.0
        seq_delta = None
        if current_sequence is not None and state.last_sequence_number is not None:
            seq_delta = current_sequence - state.last_sequence_number

        # 1. Check for Sequence Regression
        if seq_delta is not None and seq_delta < 0:
            # Sequence moved backward within the same connection epoch
            return OrderingEvaluationResult(
                status=OrderingStatus.SEQUENCE_REGRESSION,
                final_status=FinalTimestampStatus.REJECTED,
                delta_ms=delta_ms,
                sequence_delta=seq_delta,
                reason=f"Sequence regressed from {state.last_sequence_number} to {current_sequence}.",
            )

        # 2. Check for Event-Time Regression
        if delta_ms < 0:
            abs_regression_ms = abs(delta_ms)
            if abs_regression_ms <= reordering_tolerance_ms:
                # Late arrival within acceptable jitter tolerance -> Warning
                return OrderingEvaluationResult(
                    status=OrderingStatus.LATE_ARRIVAL,
                    final_status=FinalTimestampStatus.VALID_WITH_WARNING,
                    delta_ms=delta_ms,
                    sequence_delta=seq_delta,
                    reason=f"Late arrival: event timestamp is {abs_regression_ms:.1f}ms behind previous, within {reordering_tolerance_ms}ms tolerance.",
                )
            else:
                # Material regression exceeding tolerance -> Quarantined
                return OrderingEvaluationResult(
                    status=OrderingStatus.EVENT_TIME_REGRESSION,
                    final_status=FinalTimestampStatus.QUARANTINED,
                    delta_ms=delta_ms,
                    sequence_delta=seq_delta,
                    reason=f"Event time regressed by {abs_regression_ms:.1f}ms, exceeding tolerance {reordering_tolerance_ms}ms.",
                )

        # Normal progression: update state
        state.last_event_timestamp = current_event_timestamp
        if current_sequence is not None:
            state.last_sequence_number = current_sequence
        state.last_receive_timestamp = now_rx

        return OrderingEvaluationResult(
            status=OrderingStatus.IN_ORDER,
            final_status=FinalTimestampStatus.VALID,
            delta_ms=delta_ms,
            sequence_delta=seq_delta,
            reason="Observation arrived strictly in order.",
        )
