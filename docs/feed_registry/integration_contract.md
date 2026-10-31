# M01 -> M02 Integration Contract

## Purpose
Establishes the typed contract between **Module 01 (Feed Registry & Configuration)** and **Module 02 (Market Data Ingestion Engine)**.

## Separation of Concerns
- **M01 Responsibilities**:
  - Feed registration, category, and protocol classification.
  - Immutable configuration versioning and diffing.
  - SecretReference resolution pointers (`secret://<scope>/<key>`).
  - Storing desired operational states (`ACTIVE`, `INACTIVE`, `PAUSED`, `DRAINING`).
  - Scheduling trading session windows.
  - Priority failover clustering definitions.
  - Publishing commands via transactional outbox (`feed_lifecycle_commands`).
  - Ingesting and aggregating health reports.
- **M02 Responsibilities**:
  - Polling or subscribing to `feed_lifecycle_commands` outbox.
  - Opening actual network sockets (WebSocket, TCP, Multicast UDP).
  - Provider session authentication using resolved secrets.
  - High-throughput packet ingestion and parsing.
  - Emitting periodic runtime telemetry to `POST /api/v1/feeds/{feed_id}/health`.

## Python Integration Client
Located at: `backend/app/integrations/ingestion_engine/interface.py`

```python
class FeedRuntimeConfig(BaseModel):
    feed_id: UUID
    feed_code: str
    asset_class: AssetClass
    transport_protocol: TransportProtocol
    desired_state: FeedDesiredState
    version_number: int
    endpoint_url: str
    backup_endpoint_url: Optional[str] = None
    heartbeat_interval_seconds: int = 15
    reconnect_backoff_initial_ms: int = 500
    reconnect_backoff_max_ms: int = 10000
    max_reconnect_attempts: int = 10
    subscription_symbols: List[str] = []
    auth_credentials_ref: Optional[str] = None
    custom_parameters: Dict[str, Any] = {}

class M02HealthReportPayload(BaseModel):
    runtime_state: FeedRuntimeState
    latency_ms: Optional[float] = None
    messages_received_delta: int = 0
    bytes_received_delta: int = 0
    error_count_delta: int = 0
    last_heartbeat_timestamp: Optional[datetime] = None
    last_data_timestamp: Optional[datetime] = None
    error_code: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
```

