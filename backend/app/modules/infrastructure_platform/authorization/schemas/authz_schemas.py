from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.infrastructure_platform.authorization.models.authz_models import (
    AssignmentStatus,
    ScopeType,
    AuthDecisionType,
)


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    permission_id: str
    permission_code: str
    permission_name: str
    description: Optional[str] = None
    module: str
    resource_type: str
    action: str
    category: str
    status: str


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role_id: str
    role_code: str
    role_name: str
    description: Optional[str] = None
    is_system_role: bool
    status: str
    version: int
    created_at: datetime


class RoleCreateRequest(BaseModel):
    role_code: str = Field(..., min_length=3, max_length=64, description="Unique uppercase code, e.g. RISK_ANALYST")
    role_name: str = Field(..., min_length=3, max_length=128)
    description: Optional[str] = None
    permission_codes: List[str] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    role_name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class RolePermissionsUpdateRequest(BaseModel):
    permission_codes: List[str] = Field(..., description="Complete set of permission codes for the role")


class UserRoleAssignmentRequest(BaseModel):
    role_code: str
    scope_type: ScopeType = ScopeType.GLOBAL
    scope_id: Optional[str] = None
    expires_at: Optional[datetime] = None


class UserRoleAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assignment_id: str
    user_id: str
    role_id: str
    scope_type: ScopeType
    scope_id: Optional[str] = None
    status: AssignmentStatus
    effective_from: datetime
    expires_at: Optional[datetime] = None


class ResourceAccessAssignmentRequest(BaseModel):
    resource_type: str = "PORTFOLIO"
    resource_id: str = Field(..., description="Specific target resource ID (e.g. portfolio_id)")
    access_level: str = Field("READ", description="READ, WRITE, ADMIN")
    expires_at: Optional[datetime] = None


class ResourceAccessAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assignment_id: str
    user_id: str
    resource_type: str
    resource_id: str
    access_level: str
    status: AssignmentStatus
    effective_from: datetime
    expires_at: Optional[datetime] = None


class EffectivePermissionsResponse(BaseModel):
    user_id: str
    roles: List[str]
    permissions: List[str]
    portfolio_scopes: List[str] # List of portfolio_ids explicitly accessible or ['*'] for global
    is_admin: bool


class AuthorizationCheckRequest(BaseModel):
    permission_code: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None


class AuthorizationDecisionResponse(BaseModel):
    decision: AuthDecisionType
    reason_code: str
    user_id: Optional[str] = None
    permission_code: Optional[str] = None
    resource_id: Optional[str] = None
    evaluated_at: datetime
