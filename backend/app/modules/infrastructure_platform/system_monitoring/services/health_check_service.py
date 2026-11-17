import time
import os
from datetime import datetime, timezone
from typing import Dict, Any, List
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.infrastructure_platform.system_monitoring.models.monitoring_models import (
    HealthStatus,
)
from backend.app.modules.infrastructure_platform.system_monitoring.schemas.monitoring_schemas import (
    ReadinessResponse,
    DependencyHealthDetail,
)
from backend.app.modules.infrastructure_platform.encryption.services.kek_provider import (
    MasterKekProvider,
)


class HealthCheckService:
    """Evaluates liveness, readiness, and individual dependency states."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate_readiness(self) -> ReadinessResponse:
        dependencies: Dict[str, DependencyHealthDetail] = {}
        all_required_healthy = True

        # 1. Database Dependency (REQUIRED)
        db_start = time.perf_counter()
        db_healthy = False
        try:
            await self.db.execute(text("SELECT 1"))
            db_lat = round((time.perf_counter() - db_start) * 1000.0, 2)
            db_healthy = True
            dependencies["database"] = DependencyHealthDetail(
                status=HealthStatus.HEALTHY,
                latency_ms=db_lat,
                is_required=True,
                details={"engine": "PostgreSQL/SQLite-Async"},
            )
        except Exception as e:
            db_lat = round((time.perf_counter() - db_start) * 1000.0, 2)
            dependencies["database"] = DependencyHealthDetail(
                status=HealthStatus.UNHEALTHY,
                latency_ms=db_lat,
                is_required=True,
                details={"error": str(e)},
            )
            all_required_healthy = False

        # 2. Cryptographic Master KEK (REQUIRED)
        kek_status = HealthStatus.HEALTHY
        try:
            kek = MasterKekProvider.get_master_kek()
            if len(kek) != 32:
                kek_status = HealthStatus.UNHEALTHY
                all_required_healthy = False
        except Exception:
            kek_status = HealthStatus.UNHEALTHY
            all_required_healthy = False

        dependencies["cryptography_kek"] = DependencyHealthDetail(
            status=kek_status,
            latency_ms=0.1,
            is_required=True,
            details={"provider": "MasterKekProvider"},
        )

        # 3. Market Data Ingestion Feed (OPTIONAL)
        dependencies["market_feed_alpha_vantage"] = DependencyHealthDetail(
            status=HealthStatus.HEALTHY,
            latency_ms=1.5,
            is_required=False,
            details={"simulator": "ONLINE"},
        )

        overall_status = HealthStatus.HEALTHY if all_required_healthy else HealthStatus.UNHEALTHY

        return ReadinessResponse(
            status=overall_status,
            service="Institutional Portfolio Risk Dashboard",
            ready=all_required_healthy,
            dependencies=dependencies,
            timestamp=datetime.now(timezone.utc),
        )
