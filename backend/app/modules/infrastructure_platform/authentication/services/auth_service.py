import hashlib
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.infrastructure_platform.authentication.models.auth_models import (
    UserIdentity,
    UserCredential,
    UserSession,
    AuthenticationEventRecord,
    AccountStatus,
    SessionStatus,
    AuthEventType,
)
from backend.app.modules.infrastructure_platform.authentication.services.password_service import (
    PasswordSecurityService,
)
from backend.app.modules.reporting_attribution_audit.audit_trail.services.audit_trail_service import (
    AuditTrailService,
)
from backend.app.modules.reporting_attribution_audit.audit_trail.schemas.audit_schemas import (
    AuditEventCreateRequest,
    AuditActorInput,
)
from backend.app.modules.reporting_attribution_audit.audit_trail.models.audit_models import (
    EventCategory,
    EventSeverity,
    EventOutcome,
    ActorType,
)


class AuthenticationService:
    """Core institutional service managing user logins, password verification, session tokens, and security audits."""

    SESSION_LIFETIME_HOURS = 12
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_MINUTES = 15

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit_service = AuditTrailService(db)

    async def _record_event(
        self,
        event_type: AuthEventType,
        user_id: Optional[str],
        login_identifier: str,
        outcome: str,
        failure_reason: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Persists authentication security event and dispatches to M14.07 Audit Trail."""
        now = datetime.now(timezone.utc)
        evt = AuthenticationEventRecord(
            event_id=f"auth-evt-{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            user_id=user_id,
            login_identifier_snapshot=login_identifier,
            session_id=session_id,
            outcome=outcome,
            failure_reason=failure_reason,
            source_ip=ip_address,
            user_agent=user_agent,
            occurred_at=now,
        )
        self.db.add(evt)
        await self.db.commit()

        # Audit integration
        try:
            audit_req = AuditEventCreateRequest(
                category=EventCategory.USER_ACTION,
                action=event_type.value,
                module="AUTHENTICATION",
                actor=AuditActorInput(
                    actor_type=ActorType.USER if user_id else ActorType.SYSTEM,
                    actor_id=user_id or "anonymous",
                    ip_address=ip_address,
                    user_agent=user_agent,
                ),
                target_type="USER",
                target_id=user_id or login_identifier,
                severity=EventSeverity.INFO if outcome == "SUCCESS" else EventSeverity.WARNING,
                outcome=EventOutcome.SUCCESS if outcome == "SUCCESS" else EventOutcome.FAILURE,
                details={"reason": failure_reason, "identifier": login_identifier},
                occurred_at=now,
            )
            await self.audit_service.record_audit_event(audit_req)
        except Exception:
            pass

    async def authenticate_user(
        self,
        login_identifier: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[UserIdentity, UserSession, str]:
        """Validates credentials, checks account status, creates an opaque session, and returns (user, session, raw_token).
        
        Raises:
            ValueError on invalid credentials or locked account with generic enumeration-resistant messages.
        """
        normalized_id = login_identifier.strip().lower()
        now = datetime.now(timezone.utc)

        stmt = (
            select(UserIdentity)
            .where(UserIdentity.normalized_login_identifier == normalized_id)
            .options(selectinload(UserIdentity.credential))
        )
        res = await self.db.execute(stmt)
        user = res.scalar_one_or_none()

        # Constant-time mitigation against account enumeration: dummy hash verification if user missing
        if not user or not user.credential:
            PasswordSecurityService.verify_password("dummy_password", "00" * 64, "00" * 16)
            await self._record_event(
                event_type=AuthEventType.LOGIN_FAILURE,
                user_id=None,
                login_identifier=login_identifier,
                outcome="FAILURE",
                failure_reason="INVALID_CREDENTIALS",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise ValueError("Invalid username or password.")

        # Check account lock status
        if user.account_status == AccountStatus.LOCKED and user.locked_until:
            # Handle naive/aware compatibility
            locked_until_utc = user.locked_until.replace(tzinfo=timezone.utc) if user.locked_until.tzinfo is None else user.locked_until
            if now < locked_until_utc:
                await self._record_event(
                    event_type=AuthEventType.LOGIN_FAILURE,
                    user_id=user.user_id,
                    login_identifier=login_identifier,
                    outcome="FAILURE",
                    failure_reason="ACCOUNT_LOCKED",
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                raise ValueError("Account is temporarily locked due to multiple failed attempts. Try again later.")
            else:
                user.account_status = AccountStatus.ACTIVE
                user.failed_login_attempts = 0
                user.locked_until = None

        if user.account_status != AccountStatus.ACTIVE:
            await self._record_event(
                event_type=AuthEventType.LOGIN_FAILURE,
                user_id=user.user_id,
                login_identifier=login_identifier,
                outcome="FAILURE",
                failure_reason=f"ACCOUNT_{user.account_status.value}",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise ValueError("Account is not active. Contact your administrator.")

        # Verify password hash
        is_valid = PasswordSecurityService.verify_password(
            password=password,
            expected_hash=user.credential.password_hash,
            salt=user.credential.salt,
        )

        if not is_valid:
            user.failed_login_attempts += 1
            is_now_locked = False
            if user.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
                user.account_status = AccountStatus.LOCKED
                user.locked_until = now + timedelta(minutes=self.LOCKOUT_MINUTES)
                is_now_locked = True
            await self.db.commit()

            await self._record_event(
                event_type=AuthEventType.LOGIN_FAILURE,
                user_id=user.user_id,
                login_identifier=login_identifier,
                outcome="FAILURE",
                failure_reason="ACCOUNT_LOCKED" if is_now_locked else "INVALID_CREDENTIALS",
                ip_address=ip_address,
                user_agent=user_agent,
            )
            if is_now_locked:
                raise ValueError("Account is temporarily locked due to multiple failed attempts. Try again later.")
            raise ValueError("Invalid username or password.")

        # Success: reset failed attempts
        user.failed_login_attempts = 0
        user.last_login_at = now

        # Create session
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        session_id = f"sess-{uuid.uuid4().hex[:16]}"
        expires_at = now + timedelta(hours=self.SESSION_LIFETIME_HOURS)

        session = UserSession(
            session_id=session_id,
            user_id=user.user_id,
            session_token_hash=token_hash,
            status=SessionStatus.ACTIVE,
            ip_address=ip_address,
            user_agent=user_agent,
            last_activity_at=now,
            expires_at=expires_at,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        await self.db.refresh(user)

        await self._record_event(
            event_type=AuthEventType.LOGIN_SUCCESS,
            user_id=user.user_id,
            login_identifier=login_identifier,
            outcome="SUCCESS",
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return user, session, raw_token

    async def validate_session(self, raw_token: str) -> Optional[Tuple[UserIdentity, UserSession]]:
        """Validates opaque session token hash, enforces expiration, and touches last_activity_at."""
        if not raw_token:
            return None

        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc)

        stmt = (
            select(UserSession)
            .where(
                and_(
                    UserSession.session_token_hash == token_hash,
                    UserSession.status == SessionStatus.ACTIVE,
                )
            )
            .options(selectinload(UserSession.user))
        )
        res = await self.db.execute(stmt)
        session = res.scalar_one_or_none()
        if not session or not session.user:
            return None

        # Expiry check
        exp_utc = session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at
        if now > exp_utc or session.user.account_status != AccountStatus.ACTIVE:
            session.status = SessionStatus.EXPIRED
            await self.db.commit()
            return None

        # Touch last activity
        session.last_activity_at = now
        await self.db.commit()
        return session.user, session

    async def revoke_session(self, session_id: str, reason: str = "USER_LOGOUT") -> bool:
        """Revokes an active session immediately."""
        stmt = select(UserSession).where(UserSession.session_id == session_id)
        res = await self.db.execute(stmt)
        sess = res.scalar_one_or_none()
        if not sess:
            return False

        sess.status = SessionStatus.REVOKED
        sess.revoked_at = datetime.now(timezone.utc)
        sess.revocation_reason = reason
        await self.db.commit()

        await self._record_event(
            event_type=AuthEventType.LOGOUT,
            user_id=sess.user_id,
            login_identifier="",
            outcome="SUCCESS",
            session_id=session_id,
            failure_reason=reason,
        )
        return True

    async def create_user(
        self,
        username: str,
        password: str,
        display_name: str,
        role: str = "OPERATOR",
    ) -> UserIdentity:
        """Helper to provision a user with an scrypt credential."""
        norm = username.strip().lower()
        user_id = f"usr-{uuid.uuid4().hex[:10]}"
        pwd_hash, salt = PasswordSecurityService.hash_password(password)

        user = UserIdentity(
            user_id=user_id,
            login_identifier=username,
            normalized_login_identifier=norm,
            display_name=display_name,
            role=role,
            account_status=AccountStatus.ACTIVE,
        )
        self.db.add(user)

        cred = UserCredential(
            credential_id=f"cred-{uuid.uuid4().hex[:10]}",
            user_id=user_id,
            password_hash=pwd_hash,
            salt=salt,
            hash_algorithm="scrypt",
        )
        self.db.add(cred)

        await self.db.commit()
        await self.db.refresh(user)
        return user
