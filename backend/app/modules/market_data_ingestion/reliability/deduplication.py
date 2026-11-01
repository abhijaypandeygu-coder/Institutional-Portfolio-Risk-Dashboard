"""
Module 02: Market Data Ingestion Engine - Event Reliability & Recovery Engine.
Handles deduplication, stream sequence tracking, gap detection, and checkpointing.
"""
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Optional, Set, Tuple


class ReliabilityEngine:
    """
    Ensures message stream integrity:
    1. Deduplication using provider event keys / compound keys.
    2. Sequence tracking and gap detection.
    3. Stream checkpoints.
    """

    def __init__(self, dedup_window_size: int = 5000):
        self._dedup_window_size = dedup_window_size
        self._seen_event_ids: Set[str] = set()
        self._dedup_queue: deque = deque()

        # Stream sequence tracking: (feed_id, instrument_id, channel) -> last_sequence
        self._stream_sequences: Dict[Tuple[str, str, str], int] = {}
        # Gaps detected: (feed_id, instrument_id, channel) -> list of missing sequence numbers
        self._detected_gaps: Dict[Tuple[str, str, str], list] = {}

    def is_duplicate(self, event_key: str) -> bool:
        """Checks if event_key has already been processed within the sliding window."""
        if not event_key:
            return False

        if event_key in self._seen_event_ids:
            return True

        self._seen_event_ids.add(event_key)
        self._dedup_queue.append(event_key)

        if len(self._dedup_queue) > self._dedup_window_size:
            oldest = self._dedup_queue.popleft()
            self._seen_event_ids.discard(oldest)

        return False

    def track_sequence(
        self,
        feed_id: str,
        instrument_id: str,
        channel: str,
        sequence: Optional[int],
    ) -> Optional[Tuple[int, int]]:
        """
        Tracks sequence continuity for a given stream key.
        Returns (expected, actual) if a gap is detected, else None.
        """
        if sequence is None:
            return None

        stream_key = (feed_id, instrument_id, channel)
        last_seq = self._stream_sequences.get(stream_key)

        gap = None
        if last_seq is not None:
            expected = last_seq + 1
            if sequence > expected:
                gap = (expected, sequence)
                if stream_key not in self._detected_gaps:
                    self._detected_gaps[stream_key] = []
                self._detected_gaps[stream_key].append(gap)

        self._stream_sequences[stream_key] = sequence
        return gap

    def get_last_sequence(self, feed_id: str, instrument_id: str, channel: str) -> int:
        return self._stream_sequences.get((feed_id, instrument_id, channel), 0)

    def get_detected_gaps(self, feed_id: str, instrument_id: str, channel: str) -> list:
        return self._detected_gaps.get((feed_id, instrument_id, channel), [])

    def reset(self) -> None:
        self._seen_event_ids.clear()
        self._dedup_queue.clear()
        self._stream_sequences.clear()
        self._detected_gaps.clear()
