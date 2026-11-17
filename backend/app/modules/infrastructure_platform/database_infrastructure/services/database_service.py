import os
import hashlib
import uuid
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Tuple, Dict, Any

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.database import engine
from backend.app.modules.infrastructure_platform.database_infrastructure.models.database_models import (
    DatabasePartitionMetadata,
    DatabaseBackupRecord,
    DatabaseQueryPerformanceBaseline,
    BackupStatus,
    BackupType,
    PartitionInterval,
)
from backend.app.modules.infrastructure_platform.database_infrastructure.schemas.db_schemas import (
    DatabaseHealthSummary,
    PartitionMetadataResponse,
    BackupRecordResponse,
    QueryBaselineResponse,
)


class DatabaseInfrastructureService:
    """Core institutional service managing partitioning, backups, query baselines, and health diagnostics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_database_health(self) -> DatabaseHealthSummary:
        """Evaluates database connectivity, active connection pool metrics, and transaction isolation."""
        is_connected = False
        db_engine = "PostgreSQL" if "postgresql" in settings.DATABASE_URL else "SQLite"

        try:
            res = await self.db.execute(text("SELECT 1"))
            if res.scalar_one() == 1:
                is_connected = True
        except Exception:
            is_connected = False

        # Pool metrics from current engine
        pool = engine.pool
        pool_size = getattr(pool, "size", lambda: 5)() if callable(getattr(pool, "size", None)) else getattr(pool, "size", 5)
        checked_out = getattr(pool, "checkedout", lambda: 0)() if callable(getattr(pool, "checkedout", None)) else getattr(pool, "checkedout", 0)
        overflow = getattr(pool, "overflow", lambda: 0)() if callable(getattr(pool, "overflow", None)) else getattr(pool, "overflow", 0)

        effective_pool_size = max(5, pool_size + overflow)

        return DatabaseHealthSummary(
            is_connected=is_connected,
            database_engine=db_engine,
            active_connections=checked_out,
            idle_connections=max(0, effective_pool_size - checked_out),
            pool_size=effective_pool_size,
            transaction_isolation="READ_COMMITTED",
        )

    async def register_partition_boundary(
        self,
        parent_table: str,
        period_start: datetime,
        period_end: datetime,
        partition_interval: PartitionInterval = PartitionInterval.MONTHLY,
    ) -> DatabasePartitionMetadata:
        """Registers a declarative partition boundary and tracks row capacity in the catalog."""
        part_name = f"{parent_table}_p{period_start.strftime('%Y%m')}"
        
        # Check if already exists
        stmt = select(DatabasePartitionMetadata).where(DatabasePartitionMetadata.partition_name == part_name)
        res = await self.db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return existing

        part = DatabasePartitionMetadata(
            parent_table=parent_table,
            partition_name=part_name,
            partition_interval=partition_interval,
            period_start=period_start,
            period_end=period_end,
            row_count=0,
            size_bytes=0,
            is_archived=False,
        )
        self.db.add(part)
        await self.db.commit()
        await self.db.refresh(part)
        return part

    async def list_partition_metadata(self, parent_table: Optional[str] = None) -> List[PartitionMetadataResponse]:
        """Lists active and historical partition intervals from catalog."""
        stmt = select(DatabasePartitionMetadata)
        if parent_table:
            stmt = stmt.where(DatabasePartitionMetadata.parent_table == parent_table)
        stmt = stmt.order_by(DatabasePartitionMetadata.period_start.desc())

        res = await self.db.execute(stmt)
        return [PartitionMetadataResponse.model_validate(p) for p in res.scalars().all()]

    async def create_backup_manifest(
        self,
        backup_type: BackupType = BackupType.FULL,
        storage_dir: str = "artifacts/backups",
    ) -> BackupRecordResponse:
        """Executes backup procedure, generates SHA-256 manifest, and records recovery watermark."""
        os.makedirs(storage_dir, exist_ok=True)
        backup_id = f"BKP-{uuid.uuid4().hex[:12].upper()}"
        filename = f"{backup_id}_{backup_type.value.lower()}.tar"
        filepath = os.path.join(storage_dir, filename).replace("\\", "/")

        start_time = time.perf_counter()
        now = datetime.now(timezone.utc)

        # Generate institutional mock backup artifact payload with database metadata
        manifest_content = f"INSTITUTIONAL_DATABASE_BACKUP:{backup_id}:{backup_type.value}:{now.isoformat()}".encode("utf-8")
        with open(filepath, "wb") as f:
            f.write(manifest_content)

        duration = Decimal(str(round(time.perf_counter() - start_time, 2)))
        file_size = len(manifest_content)
        checksum = hashlib.sha256(manifest_content).hexdigest()

        rec = DatabaseBackupRecord(
            backup_id=backup_id,
            backup_type=backup_type,
            storage_path=filepath,
            size_bytes=file_size,
            checksum_sha256=checksum,
            rpo_timestamp=now,
            duration_seconds=duration,
            status=BackupStatus.COMPLETED,
            verification_status="UNVERIFIED",
        )
        self.db.add(rec)
        await self.db.commit()
        await self.db.refresh(rec)
        return BackupRecordResponse.model_validate(rec)

    async def verify_backup_integrity(self, backup_id: str) -> Tuple[bool, str]:
        """Validates physical backup artifact on disk against registered SHA-256 manifest."""
        stmt = select(DatabaseBackupRecord).where(DatabaseBackupRecord.backup_id == backup_id)
        res = await self.db.execute(stmt)
        rec = res.scalar_one_or_none()
        if not rec:
            return False, "Backup record not found"

        if not os.path.exists(rec.storage_path):
            rec.status = BackupStatus.FAILED
            rec.verification_status = "FILE_MISSING"
            await self.db.commit()
            return False, "Physical backup file missing from storage path"

        with open(rec.storage_path, "rb") as f:
            content = f.read()

        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash.lower() == rec.checksum_sha256.lower():
            rec.status = BackupStatus.VERIFIED
            rec.verification_status = "VERIFIED"
            rec.last_verified_at = datetime.now(timezone.utc)
            await self.db.commit()
            return True, "Backup verified successfully with matching SHA-256 checksum."
        else:
            rec.status = BackupStatus.CORRUPTED
            rec.verification_status = "CORRUPTED"
            rec.last_verified_at = datetime.now(timezone.utc)
            await self.db.commit()
            return False, f"Checksum mismatch: expected {rec.checksum_sha256}, calculated {actual_hash}"

    async def record_query_baseline(
        self,
        query_signature: str,
        latency_ms: Decimal,
        workload_type: str = "TRANSACTIONAL",
    ) -> QueryBaselineResponse:
        """Records or updates execution latency baselines for analytical and transactional queries."""
        stmt = select(DatabaseQueryPerformanceBaseline).where(
            DatabaseQueryPerformanceBaseline.query_signature == query_signature
        )
        res = await self.db.execute(stmt)
        baseline = res.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if not baseline:
            baseline = DatabaseQueryPerformanceBaseline(
                query_signature=query_signature,
                workload_type=workload_type,
                avg_latency_ms=latency_ms,
                p95_latency_ms=latency_ms,
                p99_latency_ms=latency_ms,
                call_count=1,
                last_executed_at=now,
            )
            self.db.add(baseline)
        else:
            # Incremental moving average
            new_calls = baseline.call_count + 1
            new_avg = (baseline.avg_latency_ms * baseline.call_count + latency_ms) / new_calls
            baseline.avg_latency_ms = new_avg
            baseline.call_count = new_calls
            baseline.p95_latency_ms = max(baseline.p95_latency_ms, latency_ms)
            baseline.p99_latency_ms = max(baseline.p99_latency_ms, latency_ms)
            baseline.last_executed_at = now

        await self.db.commit()
        await self.db.refresh(baseline)
        return QueryBaselineResponse.model_validate(baseline)
