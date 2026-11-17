"""
FastAPI Router for M15.11 Deployment.
Exposes read-only lifecycle state, environment validation, release history,
and release manifest generation.
"""
from typing import List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, status
from backend.app.modules.infrastructure_platform.deployment.schemas import (
    DeploymentEnvironmentValidationResult,
    ApplicationDeploymentStatusResponse,
    ReleaseManifest,
    ReleaseActivationRequest,
    ReleaseRecordResponse,
)
from backend.app.modules.infrastructure_platform.deployment.services import (
    EnvironmentValidator,
    ServiceOrchestrator,
    ReleaseManager,
)
from backend.app.core.config import settings

router = APIRouter(prefix="/api/v1/deployment", tags=["M15.11 Deployment"])


@router.get("/validate", response_model=DeploymentEnvironmentValidationResult)
async def validate_deployment_environment():
    """Validates local host runtime prerequisites, port availability, and database safety."""
    return EnvironmentValidator.validate_full_environment()


@router.get("/status", response_model=ApplicationDeploymentStatusResponse)
async def get_application_deployment_status():
    """Returns application readiness, active profile, and sub-service status."""
    service_states = ServiceOrchestrator.get_service_states()
    overall = ServiceOrchestrator.get_overall_application_status()
    current_rel = ReleaseManager.get_current_release()
    db_safe = EnvironmentValidator.validate_database_safety(settings.DATABASE_URL)

    return {
        "application_name": settings.APP_NAME,
        "application_version": current_rel["application_version"],
        "active_profile": settings.ENVIRONMENT,
        "overall_status": overall,
        "environment_safe": db_safe["url_safe"],
        "services": service_states,
        "schema_revision": current_rel["schema_revision"],
        "timestamp": datetime.now(timezone.utc),
    }


@router.get("/releases/manifest", response_model=ReleaseManifest)
async def get_release_manifest():
    """Generates machine-readable release manifest for deployment verification."""
    return ReleaseManager.generate_release_manifest()


@router.get("/releases", response_model=List[ReleaseRecordResponse])
async def list_release_history():
    """Lists deployment release ledger records."""
    return ReleaseManager.list_releases()


@router.post("/releases/activate", response_model=ReleaseRecordResponse)
async def activate_release_endpoint(req: ReleaseActivationRequest):
    """Activates a target application release."""
    record = ReleaseManager.activate_release(
        release_id=req.release_id,
        activated_by=req.activated_by or "operator",
        confirm_destructive_migrations=req.confirm_destructive_migrations,
    )
    return record
