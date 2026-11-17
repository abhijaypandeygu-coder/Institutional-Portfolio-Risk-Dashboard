import pytest
import json
import asyncio
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.modules.infrastructure_platform.realtime_api.gateway import gateway, RealtimeGateway
from backend.app.modules.infrastructure_platform.realtime_api.schemas.message_schemas import (
    RealtimeChannelType,
    ClientMessageType,
    ServerMessageType,
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


@pytest.fixture
def clean_gateway():
    """Provides an isolated clean RealtimeGateway instance for testing."""
    gw = RealtimeGateway(
        connection_manager=RealtimeConnectionManager(max_queue_size=10),
        subscription_manager=SubscriptionManager(max_subscriptions_per_conn=10),
        sequence_manager=SequenceAndReplayManager(max_buffer_per_stream=100),
    )
    return gw


@pytest.mark.asyncio
async def test_subscription_manager_filtering():
    """Verify subscription matching against channel, resource ID, and event sub-types."""
    sub_mgr = SubscriptionManager()

    from backend.app.modules.infrastructure_platform.realtime_api.schemas.message_schemas import SubscribeMessage

    # Subscribe to market channel for AAPL and MSFT only
    req = SubscribeMessage(
        request_id="req-1",
        channel=RealtimeChannelType.MARKET,
        resource_ids=["AAPL", "MSFT"],
        event_types=["market.quote"],
    )
    sub = sub_mgr.register_subscription("conn-1", req)
    assert sub.subscription_id.startswith("sub-")

    # Match AAPL quote -> should match
    matches = sub_mgr.get_matching_connections(RealtimeChannelType.MARKET, "AAPL", "market.quote")
    assert "conn-1" in matches

    # Different resource TSLA -> should not match
    assert "conn-1" not in sub_mgr.get_matching_connections(RealtimeChannelType.MARKET, "TSLA", "market.quote")

    # Different event type market.trade -> should not match
    assert "conn-1" not in sub_mgr.get_matching_connections(RealtimeChannelType.MARKET, "AAPL", "market.trade")

    # Different channel PORTFOLIO -> should not match
    assert "conn-1" not in sub_mgr.get_matching_connections(RealtimeChannelType.PORTFOLIO, "AAPL", "market.quote")


@pytest.mark.asyncio
async def test_sequence_monotonicity_and_replay(clean_gateway):
    """Verify stream sequence numbers increment monotonically and replay returns ordered sequence."""
    stream = "portfolio-PORT-001"

    # Publish 5 events
    for i in range(1, 6):
        await clean_gateway.publish_event(
            channel=RealtimeChannelType.PORTFOLIO,
            event_type="portfolio.valuation.updated",
            resource_id="PORT-001",
            stream_id=stream,
            payload={"nav": 1000000 + i * 1000},
            producer_module="M05",
        )

    assert clean_gateway.sequence_manager.get_current_sequence(stream) == 5

    # Replay from sequence 3 -> should return seq 3, 4, 5
    replayed = clean_gateway.replay_stream_events(stream, from_sequence=3)
    assert replayed is not None
    assert len(replayed) == 3
    assert [e.sequence for e in replayed] == [3, 4, 5]

    # Replay from expired sequence (if we simulate buffer smaller than sequence)
    clean_gateway.sequence_manager.max_buffer_per_stream = 2
    # Publish 2 more to evict older sequences
    await clean_gateway.publish_event(
        channel=RealtimeChannelType.PORTFOLIO,
        event_type="portfolio.valuation.updated",
        resource_id="PORT-001",
        stream_id=stream,
        payload={"nav": 2000000},
    )
    await clean_gateway.publish_event(
        channel=RealtimeChannelType.PORTFOLIO,
        event_type="portfolio.valuation.updated",
        resource_id="PORT-001",
        stream_id=stream,
        payload={"nav": 2001000},
    )
    # Replay from sequence 1 should now return None (RESYNC_REQUIRED)
    assert clean_gateway.replay_stream_events(stream, from_sequence=1) is None


@pytest.mark.asyncio
async def test_bounded_queue_backpressure():
    """Verify bounded outbound queue drops events when high water mark is exceeded."""
    conn_mgr = RealtimeConnectionManager(max_queue_size=3)
    ctx = conn_mgr.register_connection("conn-test-slow", None) # dummy websocket

    # Fill queue to capacity
    assert await ctx.enqueue_event("msg-1") is True
    assert await ctx.enqueue_event("msg-2") is True
    assert await ctx.enqueue_event("msg-3") is True

    # 4th message should be dropped due to backpressure limit
    assert await ctx.enqueue_event("msg-4") is False
    assert ctx.dropped_events_count == 1

    await conn_mgr.unregister_connection("conn-test-slow")


def test_websocket_endpoint_protocol_handshake():
    """Verify WebSocket handshake, ConnectionAck, Ping/Pong, and subscription lifecycle using TestClient."""
    client = TestClient(app)

    with client.websocket_connect("/api/v1/ws?token=mock_jwt_trader") as ws:
        # 1. First message must be ConnectionAck
        ack_data = ws.receive_json()
        assert ack_data["type"] == ServerMessageType.CONNECTION_ACK.value
        assert ack_data["status"] == "CONNECTED"
        assert "connection_id" in ack_data
        conn_id = ack_data["connection_id"]

        # 2. Test Ping/Pong
        ws.send_json({"type": ClientMessageType.PING.value, "timestamp": 12345678})
        pong_data = ws.receive_json()
        assert pong_data["type"] == ServerMessageType.PONG.value
        assert pong_data["timestamp"] == 12345678

        # 3. Test Subscribe
        sub_req = {
            "type": ClientMessageType.SUBSCRIBE.value,
            "request_id": "req-sub-001",
            "channel": RealtimeChannelType.RISK.value,
            "resource_ids": ["PORT-001"],
            "event_types": ["risk.var.updated"],
        }
        ws.send_json(sub_req)
        sub_ack = ws.receive_json()
        assert sub_ack["type"] == ServerMessageType.SUBSCRIPTION_ACK.value
        assert sub_ack["request_id"] == "req-sub-001"
        assert sub_ack["status"] == "ACTIVE"
        assert "subscription_id" in sub_ack
        sub_id = sub_ack["subscription_id"]

        # 4. Test Unsubscribe
        ws.send_json({
            "type": ClientMessageType.UNSUBSCRIBE.value,
            "request_id": "req-unsub-001",
            "subscription_id": sub_id,
        })
        unsub_ack = ws.receive_json()
        assert unsub_ack["type"] == "unsubscription.ack"
        assert unsub_ack["status"] == "UNSUBSCRIBED"


def test_websocket_resync_protocol():
    """Verify client resync protocol: resync.request -> resync.started -> replayed events -> resync.completed."""
    client = TestClient(app)

    with client.websocket_connect("/api/v1/ws") as ws:
        # Connection Ack
        ws.receive_json()

        # Send resync request for existing stream
        ws.send_json({
            "type": ClientMessageType.RESYNC_REQUEST.value,
            "request_id": "req-resync-1",
            "stream_id": "stream-mock-test",
            "from_sequence": 1,
        })

        # Receive resync.started
        start_msg = ws.receive_json()
        assert start_msg["type"] == ServerMessageType.RESYNC_STARTED.value
        assert start_msg["stream_id"] == "stream-mock-test"

        # Receive resync.completed
        comp_msg = ws.receive_json()
        assert comp_msg["type"] == ServerMessageType.RESYNC_COMPLETED.value
        assert comp_msg["stream_id"] == "stream-mock-test"
