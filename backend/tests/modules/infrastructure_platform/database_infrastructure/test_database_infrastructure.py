import pytest
import os
import shutil
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.modules.infrastructure_platform.database_infrastructure.models.database_models import (
    DatabasePartitionMetadata,
    DatabaseBackupRecord,
    DatabaseQueryPerformanceBaseline,
    BackupStatus,
    BackupType,
    PartitionInterval,
)
from backend.app.modules.infrastructure_platform.database_infrastructure.services.database_service import (
    DatabaseInfrastructureService,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_BACKUP_DIR = "artifacts/test_backups"


@pytest.fixture(autouse=True)
def cleanup_backups():
    os.makedirs(TEST_BACKUP_DIR, exist_ok=True)
    yield
    if os.path.exists(TEST_BACKUP_DIR):
        try:
            shutil.rmtree(TEST_BACKUP_DIR)
        except OSError:
            pass


@pytest.fixture
async def test_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_database_health_service(test_session):
    """Verify database connectivity check and connection pool diagnostics."""
    service = DatabaseInfrastructureService(test_session)
    health = await service.get_database_health()
    assert health.is_connected is True
    assert health.transaction_isolation == "READ_COMMITTED"
    assert health.pool_size >= 1


@pytest.mark.asyncio
async def test_partition_boundary_catalog(test_session):
    """Verify registration and querying of declarative partition intervals."""
    service = DatabaseInfrastructureService(test_session)
    now = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 11, 30, 23, 59, tzinfo=timezone.utc)

    part = await service.register_partition_boundary(
        parent_table="market_depth_observations",
        period_start=now,
        period_end=end,
        partition_interval=PartitionInterval.MONTHLY,
    )
    assert part.partition_name == "market_depth_observations_p202611"
    assert part.is_archived is False

    # List partitions
    parts = await service.list_partition_metadata(parent_table="market_depth_observations")
    assert len(parts) == 1
    assert parts[0].parent_table == "market_depth_observations"


@pytest.mark.asyncio
async def test_backup_creation_and_integrity_verification(test_session):
    """Verify backup manifest generation, SHA-256 computation, and checksum verification."""
    service = DatabaseInfrastructureService(test_session)
    backup_resp = await service.create_backup_manifest(
        backup_type=BackupType.FULL,
        storage_dir=TEST_BACKUP_DIR,
    )
    assert backup_resp.status == BackupStatus.COMPLETED
    assert backup_resp.verification_status == "UNVERIFIED"
    assert os.path.exists(backup_resp.storage_path)

    # Verify integrity
    is_valid, msg = await service.verify_backup_integrity(backup_resp.backup_id)
    assert is_valid is True
    assert "verified successfully" in msg.lower()

    # Test tampering detection
    with open(backup_resp.storage_path, "wb") as f:
        f.write(b"CORRUPTED_BACKUP_PAYLOAD_DATA")

    is_tampered_valid, tamper_msg = await service.verify_backup_integrity(backup_resp.backup_id)
    assert is_tampered_valid is False
    assert "checksum mismatch" in tamper_msg.lower()


@pytest.mark.asyncio
async def test_query_baseline_performance_tracking(test_session):
    """Verify recording and incremental moving average of query latency baselines."""
    service = DatabaseInfrastructureService(test_session)

    b1 = await service.record_query_baseline(
        query_signature="SELECT_PORTFOLIO_NAV_TIME_SERIES",
        latency_ms=Decimal("12.500"),
        workload_type="ANALYTICAL",
    )
    assert b1.call_count == 1
    assert b1.avg_latency_ms == Decimal("12.500")

    # Record second execution with 15.5ms
    b2 = await service.record_query_baseline(
        query_signature="SELECT_PORTFOLIO_NAV_TIME_SERIES",
        latency_ms=Decimal("15.500"),
        workload_type="ANALYTICAL",
    )
    assert b2.call_count == 2
    assert b2.avg_latency_ms == Decimal("14.000")


@pytest.mark.asyncio
async def test_fastapi_database_infrastructure_endpoints(test_session):
    """Verify FastAPI endpoints: health, partitions, backups, and verification."""
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Health
        h_resp = await ac.get("/api/v1/infrastructure/database/health")
        assert h_resp.status_code == 200
        assert h_resp.json()["is_connected"] is True

        # 2. Create backup
        b_resp = await ac.post("/api/v1/infrastructure/database/backups", json={"backup_type": "FULL", "target_directory": TEST_BACKUP_DIR})
        assert b_resp.status_code == 201
        bkp_data = b_resp.json()
        backup_id = bkp_data["backup_id"]

        # 3. Verify backup
        v_resp = await ac.post(f"/api/v1/infrastructure/database/backups/{backup_id}/verify")
        assert v_resp.status_code == 200
        assert v_resp.json()["status"] == "SUCCESS"

        # 4. List partitions
        p_resp = await ac.get("/api/v1/infrastructure/database/partitions")
        assert p_resp.status_code == 200
        assert isinstance(p_resp.json(), list)

    app.dependency_overrides.clear()
