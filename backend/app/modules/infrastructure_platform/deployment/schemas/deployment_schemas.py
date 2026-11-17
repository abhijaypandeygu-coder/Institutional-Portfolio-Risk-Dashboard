from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.infrastructure_platform.deployment.models.deployment_models import (
    ServiceLifecycleStatus,
    ReleaseActivationStatus,
)


class DeploymentEnvironmentValidationResult(BaseModel):
    is_valid: bool
    python_version: str
    node_version: Optional[str] = None
    database_reachable: bool
    database_url_safe: bool
    port_availability: Dict[str, bool]
    missing_variables: List[str]
    warnings: List[str]


class ServiceStatusItem(BaseModel):
    service_code: str
    service_name: str
    status: ServiceLifecycleStatus
    endpoint: Optional[str] = None
    is_mandatory: bool
    health_details: Optional[Dict[str, Any]] = None


class ApplicationDeploymentStatusResponse(BaseModel):
    application_name: str
    application_version: str
    active_profile: str
    overall_status: ServiceLifecycleStatus
    environment_safe: bool
    services: List[ServiceStatusItem]
    schema_revision: str
    timestamp: datetime


class ReleaseManifest(BaseModel):
    application_version: str = Field(..., example="1.0.0")
    build_identifier: str = Field(..., example="BUILD-20261117-001")
    source_revision: str = Field(..., example="ef02940")
    build_timestamp: datetime
    expected_schema_revision: str = Field("head")
    runtime_requirements: Dict[str, str] = Field(default_factory=dict)
    notes: Optional[str] = None


class ReleaseActivationRequest(BaseModel):
    release_id: str
    activated_by: Optional[str] = "operator"
    confirm_destructive_migrations: bool = False


class ReleaseRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    release_id: str
    application_version: str
    build_identifier: str
    source_revision: str
    schema_revision: str
    status: ReleaseActivationStatus
    activated_at: Optional[datetime] = None
    activated_by: str
    notes: Optional[str] = None
    created_at: datetime
