import uuid
from datetime import datetime, timezone
from typing import List, Optional, Set
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.infrastructure_platform.authorization.models.authz_models import (
    Role,
    Permission,
    RolePermission,
    UserRoleAssignment,
    AssignmentStatus,
    ScopeType,
)
from backend.app.modules.infrastructure_platform.authorization.services.permission_registry import (
    STANDARD_PERMISSIONS,
    STANDARD_ROLE_DEFINITIONS,
)


class RoleManagementService:
    """Manages role lifecycles, permission mappings, and seed initialization."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def initialize_standard_roles_and_permissions(self):
        """Idempotently seeds standard permissions and system roles if missing."""
        # 1. Seed Permissions
        res = await self.db.execute(select(Permission))
        existing_perms = {p.permission_code: p for p in res.scalars().all()}

        for p_def in STANDARD_PERMISSIONS:
            code = p_def["permission_code"]
            if code not in existing_perms:
                perm = Permission(
                    permission_id=f"perm-{uuid.uuid4().hex[:12]}",
                    permission_code=code,
                    permission_name=p_def["permission_name"],
                    description=p_def.get("description"),
                    module=p_def["module"],
                    resource_type=p_def["resource_type"],
                    action=p_def["action"],
                    category=p_def.get("category", "STANDARD"),
                    status="ACTIVE",
                    version=1,
                )
                self.db.add(perm)
                existing_perms[code] = perm

        await self.db.commit()

        # 2. Seed System Roles
        res = await self.db.execute(
            select(Role).options(selectinload(Role.permissions))
        )
        existing_roles = {r.role_code: r for r in res.scalars().all()}

        for role_code, r_def in STANDARD_ROLE_DEFINITIONS.items():
            if role_code not in existing_roles:
                role = Role(
                    role_id=f"role-{uuid.uuid4().hex[:12]}",
                    role_code=role_code,
                    role_name=r_def["role_name"],
                    description=r_def["description"],
                    is_system_role=r_def.get("is_system_role", True),
                    status="ACTIVE",
                    version=1,
                )
                self.db.add(role)
                await self.db.flush()
                existing_roles[role_code] = role

                # Map standard permissions
                for p_code in r_def["permissions"]:
                    if p_code in existing_perms:
                        perm_obj = existing_perms[p_code]
                        rp = RolePermission(
                            role_permission_id=f"rp-{uuid.uuid4().hex[:12]}",
                            role_id=role.role_id,
                            permission_id=perm_obj.permission_id,
                            created_by="SYSTEM_SEED",
                        )
                        self.db.add(rp)

        await self.db.commit()

    async def list_roles(self) -> List[Role]:
        res = await self.db.execute(select(Role).order_by(Role.role_name))
        return list(res.scalars().all())

    async def get_role_by_code(self, role_code: str) -> Optional[Role]:
        res = await self.db.execute(
            select(Role)
            .where(Role.role_code == role_code.upper())
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
        )
        return res.scalar_one_or_none()

    async def create_custom_role(
        self,
        role_code: str,
        role_name: str,
        description: Optional[str] = None,
        permission_codes: Optional[List[str]] = None,
        created_by: Optional[str] = None,
    ) -> Role:
        norm_code = role_code.strip().upper()
        existing = await self.get_role_by_code(norm_code)
        if existing:
            raise ValueError(f"Role with code '{norm_code}' already exists.")

        role = Role(
            role_id=f"role-{uuid.uuid4().hex[:12]}",
            role_code=norm_code,
            role_name=role_name,
            description=description,
            is_system_role=False,
            status="ACTIVE",
            version=1,
        )
        self.db.add(role)
        await self.db.flush()

        if permission_codes:
            for p_code in permission_codes:
                p_res = await self.db.execute(
                    select(Permission).where(Permission.permission_code == p_code)
                )
                perm = p_res.scalar_one_or_none()
                if perm:
                    rp = RolePermission(
                        role_permission_id=f"rp-{uuid.uuid4().hex[:12]}",
                        role_id=role.role_id,
                        permission_id=perm.permission_id,
                        created_by=created_by,
                    )
                    self.db.add(rp)

        await self.db.commit()
        await self.db.refresh(role)
        return role

    async def update_role_permissions(
        self,
        role_id: str,
        permission_codes: List[str],
        updated_by: Optional[str] = None,
    ) -> Role:
        res = await self.db.execute(
            select(Role)
            .where(Role.role_id == role_id)
            .options(selectinload(Role.permissions))
        )
        role = res.scalar_one_or_none()
        if not role:
            raise ValueError("Role not found.")

        # Remove existing mappings
        await self.db.execute(
            delete(RolePermission).where(RolePermission.role_id == role_id)
        )

        # Add new mappings
        for p_code in set(permission_codes):
            p_res = await self.db.execute(
                select(Permission).where(Permission.permission_code == p_code)
            )
            perm = p_res.scalar_one_or_none()
            if perm:
                rp = RolePermission(
                    role_permission_id=f"rp-{uuid.uuid4().hex[:12]}",
                    role_id=role.role_id,
                    permission_id=perm.permission_id,
                    created_by=updated_by,
                )
                self.db.add(rp)

        role.version += 1
        await self.db.commit()
        await self.db.refresh(role)
        return role

    async def assign_role_to_user(
        self,
        user_id: str,
        role_code: str,
        scope_type: ScopeType = ScopeType.GLOBAL,
        scope_id: Optional[str] = None,
        assigned_by: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> UserRoleAssignment:
        role = await self.get_role_by_code(role_code)
        if not role:
            raise ValueError(f"Role '{role_code}' does not exist.")

        # Escalation prevention: users cannot assign ADMINISTRATOR role unless authorized
        assignment = UserRoleAssignment(
            assignment_id=f"asgn-{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            role_id=role.role_id,
            scope_type=scope_type,
            scope_id=scope_id,
            status=AssignmentStatus.ACTIVE,
            effective_from=datetime.now(timezone.utc),
            expires_at=expires_at,
            assigned_by=assigned_by,
        )
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment
