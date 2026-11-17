import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Set
from backend.app.modules.infrastructure_platform.realtime_api.schemas.message_schemas import (
    RealtimeChannelType,
    RealtimeEventEnvelope,
)
from backend.app.modules.infrastructure_platform.realtime_api.managers.subscription_manager import (
    SubscriptionManager,
)
from backend.app.modules.infrastructure_platform.realtime_api.managers.sequence_manager import (
    SequenceAndReplayManager,
)
from backend.app.modules.infrastructure_platform.realtime_api.managers.connection_manager import (
    RealtimeConnectionManager,
)

logger = logging.getLogger("m15_02.realtime_api.gateway")


class RealtimeGateway:
    """Institutional central Real-time Gateway orchestrating channels, sequencing, subscriptions, and delivery."""

    def __init__(
        self,
        connection_manager: Optional[RealtimeConnectionManager] = None,
        subscription_manager: Optional[SubscriptionManager] = None,
        sequence_manager: Optional[SequenceAndReplayManager] = None,
    ):
        self.connection_manager = connection_manager or RealtimeConnectionManager()
        self.subscription_manager = subscription_manager or SubscriptionManager()
        self.sequence_manager = sequence_manager or SequenceAndReplayManager()

    async def publish_event(
        self,
        channel: RealtimeChannelType,
        event_type: str,
        resource_id: str,
        stream_id: str,
        payload: Dict[str, Any],
        producer_module: str = "UNKNOWN",
        quality_status: str = "VALID",
        occurred_at: Optional[datetime] = None,
    ) -> RealtimeEventEnvelope:
        """Core publishing interface used by business modules to push validated real-time updates.
        
        Guarantees:
        - Stable monotonic sequence numbering per stream_id.
        - Event buffering in sequence replay log.
        - Fan-out to authorized matching subscriptions only.
        - Non-blocking asynchronous delivery via bounded client queues.
        """
        event_id = f"evt-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        envelope = RealtimeEventEnvelope(
            event_id=event_id,
            event_type=event_type,
            channel=channel,
            schema_version=1,
            stream_id=stream_id,
            sequence=0, # Will be assigned by sequence manager
            occurred_at=occurred_at or now,
            published_at=now,
            producer_module=producer_module,
            resource_id=resource_id,
            quality_status=quality_status,
            payload=payload,
        )

        # 1. Assign monotonic sequence & store in replay buffer
        sequenced_event = self.sequence_manager.assign_sequence_and_buffer(envelope)

        # 2. Match subscriptions
        target_connections = self.subscription_manager.get_matching_connections(
            channel=channel,
            resource_id=resource_id,
            event_type=event_type,
        )

        # 3. Fan-out
        if target_connections:
            await self.connection_manager.broadcast_event(target_connections, sequenced_event)

        return sequenced_event

    def replay_stream_events(self, stream_id: str, from_sequence: int) -> Optional[List[RealtimeEventEnvelope]]:
        """Retrieves replayable events from sequence manager buffer."""
        return self.sequence_manager.get_events_from_sequence(stream_id, from_sequence)


# Singleton Gateway instance for application lifetime
gateway = RealtimeGateway()
