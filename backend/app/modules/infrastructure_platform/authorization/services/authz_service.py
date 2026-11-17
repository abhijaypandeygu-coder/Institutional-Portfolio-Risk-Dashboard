import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional, Set, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.infrastructure_platform.authorization.models.authz_models import (
    Role,
    Permission,
    RolePermission,
    UserRoleAssignment,
    AuthorizationDecisionRecord,
    AssignmentStatus,
    ScopeType,
    AuthDecisionType,
)
from backend.app.modules.infrastructure_platform.authorization.services.portfolio_scope_service import (
    PortfolioScopeService,
)
from backend.app.modules.reporting_attribution_audit.audit_trail.services.audit_trail_service import (
    AuditTrailService,
)
from backend.app.modules.reporting_attribution_audit.audit_trail.schemas.audit_schemas import (
    AuditEventCreateRequest,
    AuditActorInput,
    ActorType,
    EventCategory,
)

logger = logging.getLogger("m15_05.authorization")


class AuthorizationService:
    """Institutional central policy engine enforcing RBAC, portfolio isolation, and least privilege."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.portfolio_service = PortfolioScopeService(db)
        self.audit_service = AuditTrailService(db)

    async def _record_decision(
        self,
        decision: AuthDecisionType,
        reason_code: str,
        user_id: Optional[str],
        permission_code: str,
        resource_type: str = "SYSTEM",
        resource_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        """Persists structured authorization decision and records security denial to Audit Trail."""
        now = datetime.now(timezone.utc)
        record = AuthorizationDecisionRecord(
            decision_id=f"dec-{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            module=permission_code.split(".")[0] if "." in permission_code else "system",
            action=permission_code.split(".")[-1] if "." in permission_code else "access",
            decision=decision,
            reason_code=reason_code,
            policy_version=1,
            correlation_id=correlation_id,
            evaluated_at=now,
        )
        self.db.add(record)
        await self.db.commit()

        # Audit denials or critical administrative events
        if decision == AuthDecisionType.DENY:
            try:
                audit_req = AuditEventCreateRequest(
                    category=EventCategory.SECURITY,
                    action="AUTHORIZATION_DENIED",
                    module="AUTHORIZATION",
                    actor=AuditActorInput(
                        actor_type=ActorType.USER if user_id else ActorType.SYSTEM,
                        actor_id=user_id or "anonymous",
                    ),
                    target_id=resource_id or permission_code,
                    target_type=resource_type,
                    payload_summary=f"Access denied for action '{permission_code}'. Reason: {reason_code}",
                )
                await self.audit_service.record_event(audit_req)
            except Exception as e:
                logger.warning(f"Failed to record authorization denial to audit trail: {e}")

    async def get_effective_roles(self, user_id: str) -> List[Role]:
        """Resolves active, unexpired roles assigned to user."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(UserRoleAssignment)
            .where(
                and_(
                    UserRoleAssignment.user_id == user_id,
                    UserRoleAssignment.status == AssignmentStatus.ACTIVE,
                    UserRoleAssignment.effective_from <= now,
                )
            )
            .options(
                selectinload(UserRoleAssignment.role)
                .selectinload(Role.permissions)
                .selectinload(RolePermission.permission)
            )
        )
        res = await self.db.execute(stmt)
        assignments = res.scalars().all()

        roles = []
        for asgn in assignments:
            if asgn.expires_at and asgn.expires_at < now:
                continue
            if asgn.role and asgn.role.status == "ACTIVE":
                roles.append(asgn.role)
        return roles

    async def get_effective_permissions(self, user_id: str) -> Tuple[Set[str], bool]:
        """Returns set of all effective permission codes and is_admin flag."""
        roles = await self.get_effective_roles(user_id)
        perms: Set[str] = set()
        is_admin = False

        for r in roles:
            if r.role_code == "ADMINISTRATOR":
                is_admin = True
            for rp in r.permissions:
                if rp.permission and rp.permission.status == "ACTIVE":
                    perms.add(rp.permission.permission_code)
        return perms, is_admin

    async def authorize(
        self,
        user_id: Optional[str],
        permission_code: str,
        resource_type: str = "GLOBAL",
        resource_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Evaluates authorization decision using deny-by-default logic:
        1. User must be authenticated and valid.
        2. User must possess the granular permission.
        3. If resource is a PORTFOLIO, verify portfolio isolation scope (unless ADMIN).
        """
        if not user_id:
            await self._record_decision(
                AuthDecisionType.DENY, "UNAUTHENTICATED", None, permission_code, resource_type, resource_id, correlation_id
            )
            return False, "User is not authenticated."

        effective_perms, is_admin = await self.get_effective_permissions(user_id)

        # 1. Permission check
        if permission_code not in effective_perms and not is_admin:
            await self._record_decision(
                AuthDecisionType.DENY, "MISSING_PERMISSION", user_id, permission_code, resource_type, resource_id, correlation_id
            )
            return False, f"Missing required permission: '{permission_code}'"

        # 2. Portfolio isolation check
        if resource_type.upper() == "PORTFOLIO" and resource_id:
            # Administrators have global authority, other roles require explicit portfolio assignment
            if not is_admin:
                has_access = await self.portfolio_service.has_portfolio_access(user_id, resource_id)
                if not has_access:
                    await self._record_decision(
                        AuthDecisionType.DENY, "PORTFOLIO_SCOPE_DENIED", user_id, permission_code, resource_type, resource_id, correlation_id
                    )
                    return False, f"Access to portfolio '{resource_id}' is restricted."

        await self._record_decision(
            AuthDecisionType.ALLOW, "AUTHORIZED", user_id, permission_code, resource_type, resource_id, correlation_id
        )
        return True, "Authorized"
