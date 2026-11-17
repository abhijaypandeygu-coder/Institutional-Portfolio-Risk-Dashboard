import json
import uuid
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status

from backend.app.modules.infrastructure_platform.realtime_api.gateway import gateway
from backend.app.modules.infrastructure_platform.realtime_api.schemas.message_schemas import (
    ClientMessageType,
    ServerMessageType,
    ConnectionAckMessage,
    SubscriptionAckMessage,
    SubscriptionErrorMessage,
    SubscribeMessage,
    UnsubscribeMessage,
    ResyncRequestMessage,
    ResyncStatusMessage,
    RealtimeServerMessage,
)

logger = logging.getLogger("m15_02.realtime_api.router")

router = APIRouter(tags=["M15.02 Real-time API"])


@router.websocket("/api/v1/ws")
async def websocket_realtime_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="Session authentication token"),
):
    """Institutional WebSocket endpoint providing subscription-based market, portfolio, risk, and alert streaming."""
    await websocket.accept()

    connection_id = f"conn-{uuid.uuid4().hex[:12]}"
    user_id = "trader_demo" if token else "anonymous"
    role = "OPERATOR" if token else "READ_ONLY"

    # Register connection in connection manager
    ctx = gateway.connection_manager.register_connection(
        connection_id=connection_id,
        websocket=websocket,
        user_id=user_id,
        role=role,
    )

    # 1. Send initial ConnectionAck
    ack_msg = ConnectionAckMessage(
        connection_id=connection_id,
        status="CONNECTED",
        heartbeat_interval_seconds=30,
        protocol_version=1,
    )
    await gateway.connection_manager.send_direct_message(
        connection_id, ack_msg.model_dump(mode="json")
    )

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
            except Exception:
                await gateway.connection_manager.send_direct_message(
                    connection_id,
                    {"type": ServerMessageType.ERROR.value, "code": "MALFORMED_JSON", "message": "Invalid JSON format"},
                )
                continue

            msg_type = data.get("type")

            # A. Heartbeat / Ping
            if msg_type == ClientMessageType.PING:
                await gateway.connection_manager.send_direct_message(
                    connection_id,
                    {"type": ServerMessageType.PONG.value, "timestamp": data.get("timestamp")},
                )

            # B. Subscribe
            elif msg_type == ClientMessageType.SUBSCRIBE:
                req_id = data.get("request_id", "req-unknown")
                try:
                    sub_req = SubscribeMessage.model_validate(data)
                    sub = gateway.subscription_manager.register_subscription(
                        connection_id=connection_id,
                        req=sub_req,
                    )
                    ack = SubscriptionAckMessage(
                        request_id=req_id,
                        subscription_id=sub.subscription_id,
                        channel=sub.channel,
                        accepted_resources=list(sub.resource_ids),
                        status="ACTIVE",
                    )
                    await gateway.connection_manager.send_direct_message(
                        connection_id, ack.model_dump(mode="json")
                    )
                except Exception as e:
                    err = SubscriptionErrorMessage(
                        request_id=req_id,
                        code="SUBSCRIPTION_FAILED",
                        message=str(e),
                    )
                    await gateway.connection_manager.send_direct_message(
                        connection_id, err.model_dump(mode="json")
                    )

            # C. Unsubscribe
            elif msg_type == ClientMessageType.UNSUBSCRIBE:
                req_id = data.get("request_id", "req-unknown")
                sub_id = data.get("subscription_id", "")
                success = gateway.subscription_manager.remove_subscription(connection_id, sub_id)
                await gateway.connection_manager.send_direct_message(
                    connection_id,
                    {
                        "type": "unsubscription.ack",
                        "request_id": req_id,
                        "subscription_id": sub_id,
                        "status": "UNSUBSCRIBED" if success else "NOT_FOUND",
                    },
                )

            # D. Resync Request
            elif msg_type == ClientMessageType.RESYNC_REQUEST:
                req_id = data.get("request_id", "req-unknown")
                stream_id = data.get("stream_id", "")
                from_seq = data.get("from_sequence", 1)

                replayed_events = gateway.replay_stream_events(stream_id, from_seq)

                if replayed_events is None:
                    # Sequences have expired from replay buffer -> client must request snapshot via REST
                    resync_req_msg = ResyncStatusMessage(
                        type=ServerMessageType.RESYNC_REQUIRED,
                        stream_id=stream_id,
                        from_sequence=from_seq,
                        message="Requested sequence expired from buffer. Refresh full snapshot via REST API.",
                    )
                    await gateway.connection_manager.send_direct_message(
                        connection_id, resync_req_msg.model_dump(mode="json")
                    )
                else:
                    # Send resync.started
                    await gateway.connection_manager.send_direct_message(
                        connection_id,
                        ResyncStatusMessage(
                            type=ServerMessageType.RESYNC_STARTED,
                            stream_id=stream_id,
                            from_sequence=from_seq,
                            replayed_count=len(replayed_events),
                        ).model_dump(mode="json"),
                    )

                    # Dispatch replayed events in sequence order
                    for evt in replayed_events:
                        msg_wrap = RealtimeServerMessage(type=ServerMessageType.EVENT, event=evt)
                        await gateway.connection_manager.send_direct_message(
                            connection_id, msg_wrap.model_dump(mode="json")
                        )

                    # Send resync.completed
                    latest_seq = replayed_events[-1].sequence if replayed_events else from_seq - 1
                    await gateway.connection_manager.send_direct_message(
                        connection_id,
                        ResyncStatusMessage(
                            type=ServerMessageType.RESYNC_COMPLETED,
                            stream_id=stream_id,
                            from_sequence=from_seq,
                            to_sequence=latest_seq,
                            replayed_count=len(replayed_events),
                        ).model_dump(mode="json"),
                    )

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {connection_id}")
    finally:
        # Idempotent cleanup of connection & subscriptions
        gateway.subscription_manager.remove_all_for_connection(connection_id)
        await gateway.connection_manager.unregister_connection(connection_id)
