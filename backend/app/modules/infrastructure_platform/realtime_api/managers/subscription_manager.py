import uuid
from typing import Dict, List, Optional, Set
from backend.app.modules.infrastructure_platform.realtime_api.schemas.message_schemas import (
    RealtimeChannelType,
    SubscribeMessage,
)


class ClientSubscription:
    """Represents an active authorized subscription for a connected client session."""

    def __init__(
        self,
        subscription_id: str,
        connection_id: str,
        channel: RealtimeChannelType,
        resource_ids: List[str],
        event_types: List[str],
        options: Dict[str, any],
    ):
        self.subscription_id = subscription_id
        self.connection_id = connection_id
        self.channel = channel
        self.resource_ids = set(resource_ids)
        self.event_types = set(event_types)
        self.options = options

    def matches(self, channel: RealtimeChannelType, resource_id: str, event_type: str) -> bool:
        """Determines if published event matches this subscription's channel, resource, and type."""
        if self.channel != channel:
            return False
        # If resource_ids specified, resource_id must be in set; if empty, matches all channel resources
        if self.resource_ids and resource_id not in self.resource_ids:
            return False
        # If event_types specified, event_type must match; if empty, matches all channel types
        if self.event_types and event_type not in self.event_types:
            return False
        return True


class SubscriptionManager:
    """Manages subscription registries, fast fan-out lookup, and connection-isolated subscriptions."""

    def __init__(self, max_subscriptions_per_conn: int = 50):
        self.max_subscriptions_per_conn = max_subscriptions_per_conn
        # conn_id -> {sub_id: ClientSubscription}
        self._conn_subscriptions: Dict[str, Dict[str, ClientSubscription]] = {}

    def register_subscription(
        self,
        connection_id: str,
        req: SubscribeMessage,
        authorized_resources: Optional[List[str]] = None,
    ) -> ClientSubscription:
        """Registers a subscription after verifying limits and authorization."""
        if connection_id not in self._conn_subscriptions:
            self._conn_subscriptions[connection_id] = {}

        current_subs = self._conn_subscriptions[connection_id]
        if len(current_subs) >= self.max_subscriptions_per_conn:
            raise ValueError(f"Maximum subscriptions limit ({self.max_subscriptions_per_conn}) exceeded for connection.")

        sub_id = f"sub-{uuid.uuid4().hex[:8]}"
        final_resources = authorized_resources if authorized_resources is not None else req.resource_ids

        sub = ClientSubscription(
            subscription_id=sub_id,
            connection_id=connection_id,
            channel=req.channel,
            resource_ids=final_resources,
            event_types=req.event_types,
            options=req.options,
        )
        current_subs[sub_id] = sub
        return sub

    def remove_subscription(self, connection_id: str, subscription_id: str) -> bool:
        """Removes a specific subscription for a connection."""
        if connection_id in self._conn_subscriptions:
            if subscription_id in self._conn_subscriptions[connection_id]:
                del self._conn_subscriptions[connection_id][subscription_id]
                return True
        return False

    def remove_all_for_connection(self, connection_id: str):
        """Cleans up all active subscriptions when a connection terminates."""
        if connection_id in self._conn_subscriptions:
            del self._conn_subscriptions[connection_id]

    def get_subscriptions_for_connection(self, connection_id: str) -> List[ClientSubscription]:
        """Returns all active subscriptions for the given connection ID."""
        return list(self._conn_subscriptions.get(connection_id, {}).values())

    def get_matching_connections(
        self,
        channel: RealtimeChannelType,
        resource_id: str,
        event_type: str
    ) -> Set[str]:
        """Returns the set of connection IDs that have an active matching subscription."""
        matching_conns = set()
        for conn_id, subs in self._conn_subscriptions.items():
            for sub in subs.values():
                if sub.matches(channel, resource_id, event_type):
                    matching_conns.add(conn_id)
                    break # Connection matches, move to next connection
        return matching_conns
