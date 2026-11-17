import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from backend.app.core.database import get_db
from backend.app.core.config import settings
from backend.app.core.security import get_current_user, AuthenticatedUser
from backend.app.modules.infrastructure_platform.backend_api.schemas.common_schemas import (
    APIResponseMeta,
    PaginationMeta,
    SingleResourceResponse,
    PaginatedCollectionResponse,
    HealthStatusResponse,
)

router = APIRouter(prefix="/api/v1", tags=["M15.01 - Backend API Core"])

_STARTUP_TIME = time.time()


def create_meta(request: Request) -> APIResponseMeta:
    req_id = getattr(request.state, "request_id", "req-unknown")
    return APIResponseMeta(
        request_id=req_id,
        timestamp=datetime.now(timezone.utc),
        environment=getattr(settings, "ENVIRONMENT", "production-local"),
        version="v1",
    )


@router.get("/health", response_model=SingleResourceResponse[HealthStatusResponse])
async def get_platform_health(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Platform health check reporting database connectivity, uptime, and runtime environment."""
    meta = create_meta(request)
    uptime = time.time() - _STARTUP_TIME

    # Verify DB connectivity
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    data = HealthStatusResponse(
        status="healthy" if db_ok else "degraded",
        app_name=getattr(settings, "APP_NAME", "Institutional Portfolio Risk Dashboard"),
        api_version="v1",
        uptime_seconds=round(uptime, 2),
        modules_registered=42, # Core registered business and visualization modules
        database_connected=db_ok,
    )
    return SingleResourceResponse(data=data, meta=meta)


@router.get("/catalog", response_model=SingleResourceResponse[Dict[str, Any]])
async def get_api_catalog(request: Request):
    """Institutional API resource catalogue enumerating primary business domain endpoints."""
    meta = create_meta(request)
    catalog = {
        "title": "Institutional Portfolio Risk Dashboard REST API",
        "version": "v1",
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_json": "/openapi.json",
        },
        "resource_groups": {
            "portfolio": {
                "base_path": "/api/v1/portfolios",
                "description": "M05 Portfolio Management - positions, transactions, and valuations",
            },
            "risk": {
                "base_path": "/api/v1/portfolios/{portfolio_id}/risk",
                "description": "M06-M08 Quantitative Market Risk & Factor Analytics - VaR, ES, exposures",
            },
            "scenarios": {
                "base_path": "/api/v1/scenarios",
                "description": "M10 Scenario Analysis & Stress Testing - historical, crash, and Monte Carlo runs",
            },
            "risk_controls": {
                "base_path": "/api/v1/risk-limits",
                "description": "M11 Risk Limits & Control Framework - limits, breach lifecycle, and pre-trade checks",
            },
            "alerts": {
                "base_path": "/api/v1/alerts",
                "description": "M12 Risk Alerts & Notification Engine - alerts, triage, and notifications",
            },
            "reporting": {
                "base_path": "/api/v1/reports",
                "description": "M14 Reporting, Attribution & Audit - daily reports, export engine, and report archive",
            },
            "audit": {
                "base_path": "/api/v1/audit",
                "description": "M14.07 Audit Trail - cryptographic hash chaining and regulatory tamper verification",
            },
            "archive": {
                "base_path": "/api/v1/report-archive",
                "description": "M14.08 Historical Report Archive - immutable report preservation and legal holds",
            },
        },
    }
    return SingleResourceResponse(data=catalog, meta=meta)
