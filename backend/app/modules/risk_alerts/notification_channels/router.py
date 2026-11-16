"""
FastAPI router for M12.07 — Notification Channels.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.risk_alerts.notification_channels.services.notification_channels_service import (
    NotificationChannelsService,
)
from backend.app.modules.risk_alerts.notification_channels.schemas.notification_channels_schemas import (
    ChannelRegisterRequest,
    ChannelUpdateRequest,
    ChannelResponse,
    UserPreferenceUpdateRequest,
    UserPreferenceResponse,
    SubscriptionCreateRequest,
    SubscriptionResponse,
    InAppNotificationResponse,
    NotificationCountsResponse,
    DeliveryAttemptResponse,
    DeliveryStatusHistoryResponse,
    DeliveryResponse,
    ManualRetryRequest,
    DeadLetterResponse,
    DeliveryMetricsResponse,
    AlertNotificationIngestRequest,
)

router = APIRouter(prefix="/notifications", tags=["M12.07 Notification Channels"])


def get_service(session: AsyncSession = Depends(get_db)) -> NotificationChannelsService:
    return NotificationChannelsService(session)


# -------------------------------------------------------------
# Channel Registry Endpoints
# -------------------------------------------------------------
@router.get("/channels", response_model=List[ChannelResponse])
async def list_channels(
    enabled_only: bool = Query(False),
    service: NotificationChannelsService = Depends(get_service),
):
    await service.ensure_default_channels()
    channels = await service.repo.list_channels(enabled_only=enabled_only)
    return channels


@router.get("/channels/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: str,
    service: NotificationChannelsService = Depends(get_service),
):
    channel = await service.repo.get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.post("/channels", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def register_channel(
    req: ChannelRegisterRequest,
    service: NotificationChannelsService = Depends(get_service),
):
    existing = await service.repo.get_channel_by_code(req.channel_code)
    if existing:
        raise HTTPException(status_code=409, detail=f"Channel {req.channel_code} already registered")
    
    channel = await service.repo.create_channel(
        channel_code=req.channel_code,
        channel_name=req.channel_name,
        channel_type=req.channel_type,
        description=req.description,
        is_enabled=req.is_enabled,
        capabilities_json=req.capabilities_json,
        initial_config_json=req.initial_config_json,
        created_by=req.created_by,
    )
    return channel


@router.post("/channels/{channel_id}/enable", response_model=ChannelResponse)
async def enable_channel(
    channel_id: str,
    service: NotificationChannelsService = Depends(get_service),
):
    channel = await service.repo.update_channel_status(channel_id=channel_id, is_enabled=True)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.post("/channels/{channel_id}/disable", response_model=ChannelResponse)
async def disable_channel(
    channel_id: str,
    service: NotificationChannelsService = Depends(get_service),
):
    channel = await service.repo.update_channel_status(channel_id=channel_id, is_enabled=False)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


# -------------------------------------------------------------
# In-App Notification Inbox Endpoints
# -------------------------------------------------------------
@router.get("/inbox", response_model=List[InAppNotificationResponse])
async def get_in_app_inbox(
    user_id: str = Query("risk_manager_1"),
    unread_only: bool = Query(False),
    severity: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    portfolio_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: NotificationChannelsService = Depends(get_service),
):
    items = await service.repo.list_in_app_inbox(
        user_id=user_id,
        unread_only=unread_only,
        severity=severity,
        category=category,
        portfolio_id=portfolio_id,
        limit=limit,
        offset=offset,
    )
    return items


@router.get("/counts", response_model=NotificationCountsResponse)
async def get_in_app_counts(
    user_id: str = Query("risk_manager_1"),
    service: NotificationChannelsService = Depends(get_service),
):
    counts = await service.repo.get_in_app_counts(user_id=user_id)
    return counts


@router.post("/{notification_id}/read", response_model=InAppNotificationResponse)
async def mark_notification_read(
    notification_id: str,
    user_id: str = Query("risk_manager_1"),
    service: NotificationChannelsService = Depends(get_service),
):
    item = await service.repo.mark_in_app_read(notification_id=notification_id, user_id=user_id, is_read=True)
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found for this user")
    return item


@router.post("/{notification_id}/unread", response_model=InAppNotificationResponse)
async def mark_notification_unread(
    notification_id: str,
    user_id: str = Query("risk_manager_1"),
    service: NotificationChannelsService = Depends(get_service),
):
    item = await service.repo.mark_in_app_read(notification_id=notification_id, user_id=user_id, is_read=False)
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found for this user")
    return item


@router.post("/read-all")
async def mark_all_notifications_read(
    user_id: str = Query("risk_manager_1"),
    service: NotificationChannelsService = Depends(get_service),
):
    count = await service.repo.mark_all_in_app_read(user_id=user_id)
    return {"message": "All notifications marked as read", "updated_count": count}


# -------------------------------------------------------------
# Preferences & Subscriptions Endpoints
# -------------------------------------------------------------
@router.get("/preferences", response_model=List[UserPreferenceResponse])
async def list_user_preferences(
    user_id: str = Query("risk_manager_1"),
    service: NotificationChannelsService = Depends(get_service),
):
    prefs = await service.repo.list_user_preferences(user_id=user_id)
    return prefs


@router.put("/preferences", response_model=UserPreferenceResponse)
async def update_user_preference(
    req: UserPreferenceUpdateRequest,
    service: NotificationChannelsService = Depends(get_service),
):
    pref = await service.repo.upsert_user_preference(
        user_id=req.user_id,
        channel_code=req.channel_code,
        enabled=req.enabled,
        email_address=req.email_address,
        is_email_verified=req.is_email_verified,
        allowed_severities=req.allowed_severities,
        allowed_categories=req.allowed_categories,
        quiet_period_enabled=req.quiet_period_enabled,
        quiet_period_start=req.quiet_period_start,
        quiet_period_end=req.quiet_period_end,
        timezone=req.timezone,
        emergency_bypass=req.emergency_bypass,
        digest_enabled=req.digest_enabled,
    )
    return pref


@router.get("/subscriptions", response_model=List[SubscriptionResponse])
async def list_subscriptions(
    user_id: str = Query("risk_manager_1"),
    service: NotificationChannelsService = Depends(get_service),
):
    subs = await service.repo.get_subscriptions_for_user(user_id=user_id)
    return subs


@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    req: SubscriptionCreateRequest,
    service: NotificationChannelsService = Depends(get_service),
):
    sub = await service.repo.create_subscription(
        user_id=req.user_id,
        subscription_type=req.subscription_type,
        portfolio_id=req.portfolio_id,
        instrument_id=req.instrument_id,
        channel_code=req.channel_code,
        min_severity=req.min_severity,
        is_enabled=req.is_enabled,
    )
    return sub


# -------------------------------------------------------------
# Delivery Operations, Retries & Dead Letters
# -------------------------------------------------------------
@router.get("/deliveries/{delivery_id}", response_model=DeliveryResponse)
async def get_delivery_details(
    delivery_id: str,
    service: NotificationChannelsService = Depends(get_service),
):
    deliv = await service.repo.get_delivery_by_id(delivery_id)
    if not deliv:
        raise HTTPException(status_code=404, detail="Delivery record not found")
    return deliv


@router.get("/deliveries/{delivery_id}/attempts", response_model=List[DeliveryAttemptResponse])
async def get_delivery_attempts(
    delivery_id: str,
    service: NotificationChannelsService = Depends(get_service),
):
    deliv = await service.repo.get_delivery_by_id(delivery_id)
    if not deliv:
        raise HTTPException(status_code=404, detail="Delivery record not found")
    return deliv.attempts


@router.post("/deliveries/{delivery_id}/retry")
async def retry_delivery(
    delivery_id: str,
    req: ManualRetryRequest,
    service: NotificationChannelsService = Depends(get_service),
):
    try:
        res = await service.retry_failed_delivery(
            delivery_id=delivery_id,
            authorized_by=req.authorized_by,
            retry_reason=req.retry_reason,
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/dead-letters", response_model=List[DeadLetterResponse])
async def list_dead_letters(
    limit: int = Query(50, ge=1, le=200),
    service: NotificationChannelsService = Depends(get_service),
):
    dls = await service.repo.list_dead_letters(limit=limit)
    return dls


@router.get("/delivery-metrics", response_model=DeliveryMetricsResponse)
async def get_delivery_metrics(
    service: NotificationChannelsService = Depends(get_service),
):
    metrics = await service.repo.get_delivery_metrics()
    return metrics


# -------------------------------------------------------------
# Ingestion Endpoint (Triggered from Alert Pipeline)
# -------------------------------------------------------------
@router.post("/ingest-alert", status_code=status.HTTP_202_ACCEPTED)
async def ingest_alert(
    req: AlertNotificationIngestRequest,
    service: NotificationChannelsService = Depends(get_service),
):
    result = await service.ingest_alert_notification(req)
    return result


@router.post("/process-queue")
async def process_queue_batch(
    limit: int = Query(20, ge=1, le=100),
    service: NotificationChannelsService = Depends(get_service),
):
    res = await service.run_queue_batch(limit=limit)
    return res

