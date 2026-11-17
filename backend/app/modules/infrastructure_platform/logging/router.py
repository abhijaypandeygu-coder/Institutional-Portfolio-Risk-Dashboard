import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from backend.app.modules.infrastructure_platform.authorization.dependencies import (
    require_permission,
)
from backend.app.modules.infrastructure_platform.logging.handlers.log_manager import (
    LOG_FILE_PATH,
)
from backend.app.modules.infrastructure_platform.logging.services.log_search_service import (
    LogSearchService,
)

router = APIRouter(prefix="/api/v1/logging", tags=["M15.08 Logging"])


class LogRecordResponse(BaseModel):
    schema_version: str = "1.0"
    timestamp: str
    level: str
    service: str
    environment: str
    logger: str
    message: str
    event_name: Optional[str] = None
    correlation_id: Optional[str] = None
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    exception_type: Optional[str] = None
    stack_trace: Optional[List[str]] = None


class LoggingHealthResponse(BaseModel):
    status: str
    log_file_present: bool
    log_file_size_bytes: int
    destination: str
    redaction_engine: str
    timestamp: datetime


@router.get("/health", response_model=LoggingHealthResponse)
async def get_logging_health(
    admin_user=Depends(require_permission("admin.roles.read")),
):
    """Retrieves operational status of structured file-based logging."""
    present = os.path.exists(LOG_FILE_PATH)
    size = os.path.getsize(LOG_FILE_PATH) if present else 0

    return LoggingHealthResponse(
        status="HEALTHY" if present else "INITIALIZING",
        log_file_present=present,
        log_file_size_bytes=size,
        destination=LOG_FILE_PATH,
        redaction_engine="ACTIVE",
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/search", response_model=List[Dict[str, Any]])
async def search_logs(
    level: Optional[str] = Query(None, description="INFO, WARNING, ERROR, CRITICAL"),
    correlation_id: Optional[str] = Query(None, description="Filter by correlation ID"),
    module: Optional[str] = Query(None, description="Module code or prefix"),
    query: Optional[str] = Query(None, description="Free text message search"),
    limit: int = Query(50, ge=1, le=200),
    admin_user=Depends(require_permission("admin.roles.read")),
):
    """Retrieves redacted, filtered structured log records."""
    return LogSearchService.search_logs(
        level=level,
        correlation_id=correlation_id,
        module=module,
        query=query,
        limit=limit,
    )
