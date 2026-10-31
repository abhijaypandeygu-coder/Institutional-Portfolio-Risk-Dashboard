"""
Module 01: Feed Registry & Configuration - FastAPI REST Router.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import AuthenticatedUser, UserRole, require_role
from backend.app.modules.feed_registry.models import FeedCategory, FeedDesiredState
from backend.app.modules.feed_registry.schemas import (
    AuditLogResponse,
    ConfigCreate,
    ConfigDiffResponse,
    ConfigRollbackRequest,
    ConfigVersionResponse,
    FailoverGroupCreate,
    FailoverGroupResponse,
    FeedCreate,
    FeedHealthSummary,
    FeedResponse,
    FeedUpdate,
    HealthEventReport,
    HealthEventResponse,
    LifecycleCommandResponse,
    ScheduleCreate,
    ScheduleResponse,
    StateTransitionRequest,
)
from backend.app.modules.feed_registry.service import FeedService

router = APIRouter(prefix="/feeds", tags=["Feed Registry & Configuration"])


# ============================================================================
# Feed Registry Endpoints (Milestones 1 & 2)
# ============================================================================

@router.post(
    "",
    response_model=FeedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new market data feed",
)
async def register_feed(
    payload: FeedCreate,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    service = FeedService(db)
    return await service.register_feed(payload, actor)


@router.get(
    "",
    response_model=List[FeedResponse],
    summary="List all registered feeds with optional filters",
)
async def list_feeds(
    category: Optional[FeedCategory] = Query(default=None),
    desired_state: Optional[FeedDesiredState] = Query(default=None),
    include_archived: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    service = FeedService(db)
    return await service.list_feeds(
        category=category.value if category else None,
        desired_state=desired_state.value if desired_state else None,
        include_archived=include_archived,
    )


@router.get(
    "/{feed_id}",
    response_model=FeedResponse,
    summary="Retrieve feed registry details by ID",
)
async def get_feed(
    feed_id: UUID,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    service = FeedService(db)
    return await service.get_feed(feed_id)


@router.patch(
    "/{feed_id}",
    response_model=FeedResponse,
    summary="Update feed registry metadata and capabilities",
)
async def update_feed(
    feed_id: UUID,
    payload: FeedUpdate,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    service = FeedService(db)
    return await service.update_feed(feed_id, payload, actor)


# ============================================================================
# Feed Configuration Versioning Endpoints (Milestone 3)
# ============================================================================

@router.post(
    "/{feed_id}/configurations",
    response_model=ConfigVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Publish an immutable new configuration version for a feed",
)
async def create_configuration(
    feed_id: UUID,
    payload: ConfigCreate,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    service = FeedService(db)
    return await service.create_configuration_version(feed_id, payload, actor)


@router.get(
    "/{feed_id}/configurations",
    response_model=List[ConfigVersionResponse],
    summary="List all historical configuration versions for a feed",
)
async def list_configurations(
    feed_id: UUID,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    service = FeedService(db)
    return await service.list_configurations(feed_id)


@router.get(
    "/{feed_id}/configurations/latest",
    response_model=ConfigVersionResponse,
    summary="Get the current active configuration version for a feed",
)
async def get_latest_configuration(
    feed_id: UUID,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    service = FeedService(db)
    return await service.get_configuration(feed_id)


@router.get(
    "/{feed_id}/configurations/{version_number}",
    response_model=ConfigVersionResponse,
    summary="Get a specific historical configuration version by number",
)
async def get_configuration_version(
    feed_id: UUID,
    version_number: int,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    service = FeedService(db)
    return await service.get_configuration(feed_id, version=version_number)


@router.get(
    "/{feed_id}/configurations/diff/{from_version}/{to_version}",
    response_model=ConfigDiffResponse,
    summary="Diff two historical configuration versions",
)
async def diff_configurations(
    feed_id: UUID,
    from_version: int,
    to_version: int,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    service = FeedService(db)
    return await service.diff_configurations(feed_id, from_version, to_version)


@router.post(
    "/{feed_id}/configurations/rollback",
    response_model=ConfigVersionResponse,
    summary="Perform an immutable rollback by creating a new version with previous payload",
)
async def rollback_configuration(
    feed_id: UUID,
    payload: ConfigRollbackRequest,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.ADMIN)),
):
    service = FeedService(db)
    return await service.rollback_configuration(feed_id, payload, actor)


# ============================================================================
# Lifecycle State Transition Endpoints (Milestone 4)
# ============================================================================

@router.post(
    "/{feed_id}/state",
    response_model=LifecycleCommandResponse,
    summary="Request a desired state transition (enqueues transactional outbox command for M02)",
)
async def transition_state(
    feed_id: UUID,
    payload: StateTransitionRequest,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    service = FeedService(db)
    return await service.request_state_transition(feed_id, payload, actor)


# ============================================================================
# Scheduling & Active Windows Endpoints (Milestone 5)
# ============================================================================

@router.post(
    "/{feed_id}/schedule",
    response_model=ScheduleResponse,
    summary="Configure timezone and active trading sessions for a feed",
)
async def configure_schedule(
    feed_id: UUID,
    payload: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    service = FeedService(db)
    return await service.configure_schedule(feed_id, payload, actor)


@router.get(
    "/{feed_id}/schedule",
    response_model=ScheduleResponse,
    summary="Get active schedule and trading session windows for a feed",
)
async def get_schedule(
    feed_id: UUID,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    service = FeedService(db)
    return await service.get_schedule(feed_id)


# ============================================================================
# Priority & Failover Groups Endpoints (Milestone 6)
# ============================================================================

@router.post(
    "/failover-groups",
    response_model=FailoverGroupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a failover group with prioritized feed members",
)
async def create_failover_group(
    payload: FailoverGroupCreate,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.ADMIN)),
):
    service = FeedService(db)
    return await service.create_failover_group(payload, actor)


@router.get(
    "/failover-groups",
    response_model=List[FailoverGroupResponse],
    summary="List all configured failover groups",
)
async def list_failover_groups(
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    service = FeedService(db)
    return await service.list_failover_groups()


# ============================================================================
# Health & Monitoring Sinks Endpoints (Milestone 7)
# ============================================================================

@router.post(
    "/{feed_id}/health",
    response_model=HealthEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Report runtime health metrics and state from M02 ingestion engine",
)
async def report_health(
    feed_id: UUID,
    payload: HealthEventReport,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    service = FeedService(db)
    return await service.ingest_health_report(feed_id, payload, actor)


@router.get(
    "/{feed_id}/health/summary",
    response_model=FeedHealthSummary,
    summary="Get aggregated health summary and latest runtime metrics for a feed",
)
async def get_health_summary(
    feed_id: UUID,
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    service = FeedService(db)
    return await service.get_feed_health_summary(feed_id)


# ============================================================================
# Audit Logs Endpoints (Milestone 8)
# ============================================================================

@router.get(
    "/audit/logs",
    response_model=List[AuditLogResponse],
    summary="Retrieve immutable audit trail entries",
)
async def list_audit_logs(
    feed_id: Optional[UUID] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    actor: AuthenticatedUser = Depends(require_role(UserRole.ADMIN)),
):
    service = FeedService(db)
    return await service.list_audit_logs(feed_id=feed_id, limit=limit)
