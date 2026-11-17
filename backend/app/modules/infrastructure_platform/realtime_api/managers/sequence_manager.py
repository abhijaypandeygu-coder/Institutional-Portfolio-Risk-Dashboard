from collections import deque
from typing import Dict, List, Optional
from backend.app.modules.infrastructure_platform.realtime_api.schemas.message_schemas import (
    RealtimeEventEnvelope,
)


class SequenceAndReplayManager:
    """Maintains monotonic stream sequences, sequence gap detection, and bounded memory replay buffers."""

    def __init__(self, max_buffer_per_stream: int = 1000):
        self.max_buffer_per_stream = max_buffer_per_stream
        # stream_id -> current monotonic sequence integer
        self._stream_sequences: Dict[str, int] = {}
        # stream_id -> deque of RealtimeEventEnvelope
        self._replay_buffers: Dict[str, deque] = {}

    def assign_sequence_and_buffer(self, event: RealtimeEventEnvelope) -> RealtimeEventEnvelope:
        """Assigns the next monotonic sequence number for event's stream_id and saves to replay buffer."""
        stream_id = event.stream_id
        current_seq = self._stream_sequences.get(stream_id, 0)
        next_seq = current_seq + 1
        self._stream_sequences[stream_id] = next_seq

        # Update event with monotonic sequence
        event.sequence = next_seq

        if stream_id not in self._replay_buffers:
            self._replay_buffers[stream_id] = deque(maxlen=self.max_buffer_per_stream)
        elif self._replay_buffers[stream_id].maxlen != self.max_buffer_per_stream:
            # Recreate deque with updated maxlen if reconfigured
            self._replay_buffers[stream_id] = deque(self._replay_buffers[stream_id], maxlen=self.max_buffer_per_stream)

        self._replay_buffers[stream_id].append(event)
        return event

    def get_current_sequence(self, stream_id: str) -> int:
        return self._stream_sequences.get(stream_id, 0)

    def get_events_from_sequence(
        self,
        stream_id: str,
        from_sequence: int
    ) -> Optional[List[RealtimeEventEnvelope]]:
        """Returns ordered list of events starting from `from_sequence`.
        
        Returns:
            List[RealtimeEventEnvelope] if replayable, or None if requested sequence has fallen outside the replay buffer.
        """
        buf = self._replay_buffers.get(stream_id)
        if not buf:
            return []

        earliest_seq = buf[0].sequence
        latest_seq = buf[-1].sequence

        if from_sequence > latest_seq + 1:
            # Client requested a sequence in the future
            return []

        if from_sequence < earliest_seq:
            # Sequence has expired beyond the retention buffer; client must request fresh snapshot via REST
            return None

        # Collect events from requested sequence
        return [evt for evt in buf if evt.sequence >= from_sequence]
