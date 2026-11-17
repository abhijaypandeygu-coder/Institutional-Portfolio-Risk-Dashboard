from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.database import get_db
from backend.app.modules.infrastructure_platform.authentication.router import (
    get_current_authenticated_user,
)
from backend.app.modules.infrastructure_platform.authorization.dependencies import (
    require_permission,
)
from backend.app.modules.infrastructure_platform.authorization.models.authz_models import (
    Role,
    Permission,
    UserRoleAssignment,
    ResourceAccessAssignment,
    AuthorizationDecisionRecord,
)
from backend.app.modules.infrastructure_platform.authorization.schemas.authz_schemas import (
    RoleResponse,
    RoleCreateRequest,
    RolePermissionsUpdateRequest,
    PermissionResponse,
    UserRoleAssignmentRequest,
    UserRoleAssignmentResponse,
    ResourceAccessAssignmentRequest,
    ResourceAccessAssignmentResponse,
    EffectivePermissionsResponse,
    AuthorizationDecisionResponse,
)
from backend.app.modules.infrastructure_platform.authorization.services.role_service import (
    RoleManagementService,
)
from backend.app.modules.infrastructure_platform.authorization.services.portfolio_scope_service import (
    PortfolioScopeService,
)
from backend.app.modules.infrastructure_platform.authorization.services.authz_service import (
    AuthorizationService,
)

router = APIRouter(prefix="/api/v1/authz", tags=["M15.05 Authorization & Access Control"])


@router.get("/permissions", response_model=List[PermissionResponse])
async def list_permissions(
    admin_user=Depends(require_permission("admin.roles.read")),
    db: AsyncSession = Depends(get_db),
):
    """Lists all registered granular permissions."""
    res = await db.execute(select(Permission).order_by(Permission.module, Permission.permission_code))
    return list(res.scalars().all())


@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    admin_user=Depends(require_permission("admin.roles.read")),
    db: AsyncSession = Depends(get_db),
):
    """Lists all configured system and custom roles."""
    service = RoleManagementService(db)
    return await service.list_roles()


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_role(
    req: RoleCreateRequest,
    admin_user=Depends(require_permission("admin.roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Creates a new custom role with assigned permissions."""
    service = RoleManagementService(db)
    try:
        role = await service.create_custom_role(
            role_code=req.role_code,
            role_name=req.role_name,
            description=req.description,
            permission_codes=req.permission_codes,
            created_by=admin_user.user_id,
        )
        return role
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/roles/{role_id}/permissions", response_model=RoleResponse)
async def update_role_permissions(
    role_id: str,
    req: RolePermissionsUpdateRequest,
    admin_user=Depends(require_permission("admin.roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Updates granular permissions mapped to a role."""
    service = RoleManagementService(db)
    try:
        return await service.update_role_permissions(
            role_id=role_id,
            permission_codes=req.permission_codes,
            updated_by=admin_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/users/{user_id}/roles", response_model=UserRoleAssignmentResponse)
async def assign_role_to_user(
    user_id: str,
    req: UserRoleAssignmentRequest,
    admin_user=Depends(require_permission("admin.roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Assigns an RBAC role to a user."""
    # Escalation protection: Prevent assigning ADMINISTRATOR if admin_user is assigning to themselves
    if req.role_code.upper() == "ADMINISTRATOR" and admin_user.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-escalation prevention: Users cannot assign administrator roles to themselves.",
        )

    service = RoleManagementService(db)
    try:
        return await service.assign_role_to_user(
            user_id=user_id,
            role_code=req.role_code,
            scope_type=req.scope_type,
            scope_id=req.scope_id,
            assigned_by=admin_user.user_id,
            expires_at=req.expires_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/users/{user_id}/portfolio-access", response_model=ResourceAccessAssignmentResponse)
async def grant_portfolio_access(
    user_id: str,
    req: ResourceAccessAssignmentRequest,
    admin_user=Depends(require_permission("admin.portfolio_access.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Grants explicit portfolio access to a user (enforcing portfolio isolation)."""
    service = PortfolioScopeService(db)
    return await service.grant_portfolio_access(
        user_id=user_id,
        portfolio_id=req.resource_id,
        access_level=req.access_level,
        assigned_by=admin_user.user_id,
        expires_at=req.expires_at,
    )


@router.get("/users/{user_id}/effective-permissions", response_model=EffectivePermissionsResponse)
async def get_user_effective_permissions(
    user_id: str,
    auth_context=Depends(get_current_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves computed effective permissions, active roles, and portfolio scopes for a user."""
    req_user, _ = auth_context
    authz_service = AuthorizationService(db)

    # Allow reading self effective permissions; require admin.roles.read for others
    if req_user.user_id != user_id:
        is_allowed, _ = await authz_service.authorize(req_user.user_id, "admin.roles.read")
        if not is_allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: Admin permission required to inspect other users.")

    roles = await authz_service.get_effective_roles(user_id)
    perms, is_admin = await authz_service.get_effective_permissions(user_id)
    portfolios = await authz_service.portfolio_service.get_user_portfolio_scopes(user_id)

    return EffectivePermissionsResponse(
        user_id=user_id,
        roles=[r.role_code for r in roles],
        permissions=sorted(list(perms)),
        portfolio_scopes=["*"] if is_admin else sorted(list(portfolios)),
        is_admin=is_admin,
    )
