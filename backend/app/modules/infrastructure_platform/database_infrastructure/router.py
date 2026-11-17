from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.infrastructure_platform.backend_api.schemas.common_schemas import (
    SingleResourceResponse,
    PaginatedCollectionResponse,
    APIResponseMeta,
)
from backend.app.modules.infrastructure_platform.backend_api.router.core_router import create_meta
from backend.app.modules.infrastructure_platform.database_infrastructure.schemas.db_schemas import (
    DatabaseHealthSummary,
    PartitionMetadataResponse,
    BackupCreateRequest,
    BackupRecordResponse,
    QueryBaselineResponse,
)
from backend.app.modules.infrastructure_platform.database_infrastructure.services.database_service import (
    DatabaseInfrastructureService,
)

router = APIRouter(prefix="/api/v1/infrastructure/database", tags=["M15.03 Database Infrastructure"])


@router.get("/health", response_model=DatabaseHealthSummary)
async def get_database_health(db: AsyncSession = Depends(get_db)):
    """Reports database connection state, pool size, active/idle count, and isolation level."""
    service = DatabaseInfrastructureService(db)
    return await service.get_database_health()


@router.get("/partitions", response_model=List[PartitionMetadataResponse])
async def list_partitions(
    parent_table: Optional[str] = Query(None, description="Filter by parent table"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves partition metadata catalog entries for time-series and analytical tables."""
    service = DatabaseInfrastructureService(db)
    return await service.list_partition_metadata(parent_table=parent_table)


@router.post("/backups", response_model=BackupRecordResponse, status_code=status.HTTP_201_CREATED)
async def create_backup(
    req: BackupCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generates an institutional backup record, writes manifest, and records recovery watermark."""
    service = DatabaseInfrastructureService(db)
    storage_dir = req.target_directory or "artifacts/backups"
    return await service.create_backup_manifest(backup_type=req.backup_type, storage_dir=storage_dir)


@router.post("/backups/{backup_id}/verify")
async def verify_backup(
    backup_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Verifies physical backup artifact against registered SHA-256 checksum."""
    service = DatabaseInfrastructureService(db)
    is_valid, msg = await service.verify_backup_integrity(backup_id)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return {"status": "SUCCESS", "backup_id": backup_id, "detail": msg}
