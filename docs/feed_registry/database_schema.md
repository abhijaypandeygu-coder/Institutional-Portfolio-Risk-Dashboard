# Module 01: Database Schema

All tables are managed by SQLAlchemy 2.x and are PostgreSQL and SQLite compatible.

### 1. `feed_registry`
- `id`: UUID (Primary Key)
- `feed_code`: VARCHAR(64) UNIQUE NOT NULL (Indexed)
- `feed_name`: VARCHAR(128) NOT NULL
- `description`: VARCHAR(512)
- `category`: VARCHAR(64) NOT NULL
- `asset_class`: VARCHAR(32) NOT NULL (Default: 'EQUITIES')
- `transport_protocol`: VARCHAR(32) NOT NULL
- `capabilities`: JSON NOT NULL
- `desired_state`: VARCHAR(32) NOT NULL (Default: 'INACTIVE')
- `record_status`: VARCHAR(32) NOT NULL (Default: 'ACTIVE')
- `current_version`: INTEGER NOT NULL (Default: 0)
- `is_primary_eligible`: BOOLEAN NOT NULL (Default: TRUE)
- `is_backup_eligible`: BOOLEAN NOT NULL (Default: TRUE)
- `metadata_json`: JSON NOT NULL
- `created_at`: TIMESTAMPTZ NOT NULL
- `updated_at`: TIMESTAMPTZ NOT NULL

### 2. `feed_config_versions`
- `id`: UUID (Primary Key)
- `feed_id`: UUID (Foreign Key -> feed_registry.id, ON DELETE CASCADE)
- `version_number`: INTEGER NOT NULL
- `schema_version`: VARCHAR(32) NOT NULL
- `config_payload`: JSON NOT NULL (Endpoint, reconnect policies, SecretReference)
- `config_hash`: VARCHAR(64) NOT NULL (SHA-256)
- `change_reason`: VARCHAR(256) NOT NULL
- `author`: VARCHAR(128) NOT NULL
- `created_at`: TIMESTAMPTZ NOT NULL
- *Constraints*: UNIQUE(`feed_id`, `version_number`)

### 3. `feed_schedules`
- `id`: UUID (Primary Key)
- `feed_id`: UUID (Foreign Key -> feed_registry.id, UNIQUE, ON DELETE CASCADE)
- `timezone`: VARCHAR(64) NOT NULL (IANA Timezone)
- `auto_start_stop_enabled`: BOOLEAN NOT NULL
- `sessions`: JSON NOT NULL
- `polling_interval_ms`: INTEGER NOT NULL
- `active_days`: JSON NOT NULL
- `created_at`: TIMESTAMPTZ NOT NULL
- `updated_at`: TIMESTAMPTZ NOT NULL

### 4. `feed_failover_groups`
- `id`: UUID (Primary Key)
- `group_name`: VARCHAR(64) UNIQUE NOT NULL
- `description`: VARCHAR(256)
- `required_capabilities`: JSON NOT NULL
- `failover_latency_threshold_ms`: FLOAT NOT NULL
- `consecutive_error_threshold`: INTEGER NOT NULL
- `created_at`: TIMESTAMPTZ NOT NULL
- `updated_at`: TIMESTAMPTZ NOT NULL

### 5. `feed_priority_members`
- `id`: UUID (Primary Key)
- `group_id`: UUID (Foreign Key -> feed_failover_groups.id, ON DELETE CASCADE)
- `feed_id`: UUID (Foreign Key -> feed_registry.id, ON DELETE CASCADE)
- `priority_rank`: INTEGER NOT NULL
- `is_active_in_group`: BOOLEAN NOT NULL
- `custom_weight`: FLOAT NOT NULL
- `created_at`: TIMESTAMPTZ NOT NULL
- *Constraints*: UNIQUE(`group_id`, `feed_id`), UNIQUE(`group_id`, `priority_rank`)

### 6. `feed_health_events`
- `id`: INTEGER / BIGINT (Primary Key, Autoincrement)
- `feed_id`: UUID (Foreign Key -> feed_registry.id, ON DELETE CASCADE)
- `timestamp`: TIMESTAMPTZ NOT NULL
- `runtime_state`: VARCHAR(32) NOT NULL
- `latency_ms`: FLOAT
- `messages_received_delta`: BIGINT NOT NULL
- `bytes_received_delta`: BIGINT NOT NULL
- `error_count_delta`: INTEGER NOT NULL
- `last_heartbeat_timestamp`: TIMESTAMPTZ
- `last_data_timestamp`: TIMESTAMPTZ
- `error_code`: VARCHAR(64)
- `error_details`: JSON

### 7. `feed_lifecycle_commands` (Transactional Outbox)
- `id`: UUID (Primary Key)
- `feed_id`: UUID (Foreign Key -> feed_registry.id, ON DELETE CASCADE)
- `command_type`: VARCHAR(32) NOT NULL (`START`, `STOP`, `PAUSE`, `DRAIN`)
- `parameters`: JSON NOT NULL
- `idempotency_key`: VARCHAR(128) UNIQUE NOT NULL
- `status`: VARCHAR(32) NOT NULL (`PENDING`, `PROCESSING`, `PROCESSED`, `FAILED`)
- `attempts`: INTEGER NOT NULL
- `executed_at`: TIMESTAMPTZ
- `error_message`: VARCHAR(512)
- `created_at`: TIMESTAMPTZ NOT NULL

### 8. `feed_audit_logs`
- `id`: INTEGER / BIGINT (Primary Key, Autoincrement)
- `actor`: VARCHAR(128) NOT NULL
- `operation`: VARCHAR(64) NOT NULL
- `resource_type`: VARCHAR(64) NOT NULL
- `resource_id`: VARCHAR(64)
- `success`: BOOLEAN NOT NULL
- `details`: JSON NOT NULL
- `client_ip`: VARCHAR(45)
- `created_at`: TIMESTAMPTZ NOT NULL

