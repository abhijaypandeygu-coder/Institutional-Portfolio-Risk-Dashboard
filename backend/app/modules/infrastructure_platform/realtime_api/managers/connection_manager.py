import asyncio
import json
import logging
from typing import Dict, Optional, Set
from fastapi import WebSocket
from backend.app.modules.infrastructure_platform.realtime_api.schemas.message_schemas import (
    RealtimeEventEnvelope,
    RealtimeServerMessage,
    ServerMessageType,
)

logger = logging.getLogger("m15_02.realtime_api.connection_manager")


class ClientConnectionContext:
    """Encapsulates a live WebSocket client connection with bounded queue and backpressure tracking."""

    def __init__(
        self,
        connection_id: str,
        websocket: WebSocket,
        user_id: str,
        role: str,
        max_queue_size: int = 500,
    ):
        self.connection_id = connection_id
        self.websocket = websocket
        self.user_id = user_id
        self.role = role
        self.max_queue_size = max_queue_size
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.is_active = True
        self.dropped_events_count = 0
        self.writer_task: Optional[asyncio.Task] = None

    async def enqueue_event(self, event_json: str, is_coalesceable: bool = False) -> bool:
        """Pushes serialized message onto bounded queue with backpressure protection.
        
        Returns:
            True if delivered to queue, False if dropped due to buffer overflow.
        """
        if not self.is_active:
            return False

        if self.queue.full():
            self.dropped_events_count += 1
            logger.warning(
                f"Backpressure warning: Queue full ({self.max_queue_size}) for connection {self.connection_id}. "
                f"Dropping event (total dropped: {self.dropped_events_count})"
            )
            return False

        try:
            self.queue.put_nowait(event_json)
            return True
        except asyncio.QueueFull:
            self.dropped_events_count += 1
            return False


class RealtimeConnectionManager:
    """Manages active WebSocket connections, writer worker loops, and bounded outbound delivery."""

    def __init__(self, max_queue_size: int = 500):
        self.max_queue_size = max_queue_size
        self._connections: Dict[str, ClientConnectionContext] = {}

    def register_connection(
        self,
        connection_id: str,
        websocket: WebSocket,
        user_id: str = "anonymous",
        role: str = "READ_ONLY",
    ) -> ClientConnectionContext:
        ctx = ClientConnectionContext(
            connection_id=connection_id,
            websocket=websocket,
            user_id=user_id,
            role=role,
            max_queue_size=self.max_queue_size,
        )
        self._connections[connection_id] = ctx
        # Start background writer task
        ctx.writer_task = asyncio.create_task(self._connection_writer(ctx))
        return ctx

    async def unregister_connection(self, connection_id: str):
        ctx = self._connections.pop(connection_id, None)
        if ctx:
            ctx.is_active = False
            if ctx.writer_task:
                ctx.writer_task.cancel()
                try:
                    await ctx.writer_task
                except asyncio.CancelledError:
                    pass

    async def _connection_writer(self, ctx: ClientConnectionContext):
        """Dedicated async consumer task draining outbound queue to client socket."""
        try:
            while ctx.is_active:
                msg = await ctx.queue.get()
                await ctx.websocket.send_text(msg)
                ctx.queue.task_done()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.info(f"Connection writer terminated for {ctx.connection_id}: {str(e)}")
            ctx.is_active = False

    async def send_direct_message(self, connection_id: str, message_dict: Dict):
        """Sends an unbuffered control message directly or via high priority queue."""
        ctx = self._connections.get(connection_id)
        if ctx and ctx.is_active:
            try:
                await ctx.websocket.send_text(json.dumps(message_dict, default=str))
            except Exception as e:
                logger.warning(f"Failed to send direct message to {connection_id}: {str(e)}")

    async def broadcast_event(self, target_connection_ids: Set[str], event: RealtimeEventEnvelope):
        """Dispatches an envelope across targeted client connection queues."""
        msg_wrapper = RealtimeServerMessage(type=ServerMessageType.EVENT, event=event)
        msg_json = json.dumps(msg_wrapper.model_dump(mode="json"), default=str)

        for conn_id in target_connection_ids:
            ctx = self._connections.get(conn_id)
            if ctx and ctx.is_active:
                await ctx.enqueue_event(msg_json)

    def get_connection(self, connection_id: str) -> Optional[ClientConnectionContext]:
        return self._connections.get(connection_id)

    def get_active_connection_count(self) -> int:
        return len(self._connections)
