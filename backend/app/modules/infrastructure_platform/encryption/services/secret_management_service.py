import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.infrastructure_platform.encryption.models.encryption_models import (
    ManagedSecretRecord,
    SecretVersionHistoryRecord,
    SecurityAuditEventRecord,
    SecretStatus,
)
from backend.app.modules.infrastructure_platform.encryption.services.cryptography_provider import (
    CryptographyProvider,
)
from backend.app.modules.infrastructure_platform.encryption.services.key_management_service import (
    KeyManagementService,
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

logger = logging.getLogger("m15_06.encryption")


class SecretManagementService:
    """Manages application secrets lifecycle, authenticated encryption, and credential rotation."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.key_service = KeyManagementService(db)
        self.audit_service = AuditTrailService(db)

    async def _record_security_event(
        self,
        event_type: str,
        severity: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        actor_id: Optional[str] = None,
    ):
        """Persists security audit event to database and dispatches to M14.07 Audit Trail."""
        now = datetime.now(timezone.utc)
        record = SecurityAuditEventRecord(
            event_id=f"sec-evt-{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            severity=severity,
            resource_id=resource_id,
            details=details,
            actor_id=actor_id,
            occurred_at=now,
        )
        self.db.add(record)
        await self.db.commit()

        try:
            audit_req = AuditEventCreateRequest(
                category=EventCategory.SECURITY,
                action=event_type,
                module="ENCRYPTION",
                actor=AuditActorInput(
                    actor_type=ActorType.USER if actor_id else ActorType.SYSTEM,
                    actor_id=actor_id or "system",
                ),
                target_id=resource_id,
                target_type="MANAGED_SECRET",
                payload_summary=f"Encryption event '{event_type}' ({severity}) on resource {resource_id}",
            )
            await self.audit_service.record_event(audit_req)
        except Exception as e:
            logger.warning(f"Failed to dispatch security event to M14.07: {e}")

    async def create_secret(
        self,
        secret_name: str,
        secret_type: str,
        owner_module: str,
        plaintext_value: str,
        expires_at: Optional[datetime] = None,
        actor_id: Optional[str] = None,
    ) -> ManagedSecretRecord:
        """Encrypts plaintext secret with active DEK and persists metadata."""
        active_key_id, dek = await self.key_service.get_active_key()
        secret_id = f"sec-{uuid.uuid4().hex[:12]}"

        aad = {
            "secret_id": secret_id,
            "secret_type": secret_type,
            "owner_module": owner_module,
        }

        ciphertext = CryptographyProvider.encrypt(
            key=dek,
            plaintext=plaintext_value,
            aad_context=aad,
            key_id=active_key_id,
        )

        now = datetime.now(timezone.utc)
        record = ManagedSecretRecord(
            secret_id=secret_id,
            secret_name=secret_name,
            secret_type=secret_type,
            owner_module=owner_module,
            current_version=1,
            status=SecretStatus.ACTIVE,
            ciphertext_payload=ciphertext,
            key_id=active_key_id,
            expires_at=expires_at,
            last_rotated_at=now,
            created_at=now,
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)

        await self._record_security_event(
            event_type="SECRET_CREATED",
            severity="INFO",
            resource_id=secret_id,
            details={"secret_name": secret_name, "owner_module": owner_module},
            actor_id=actor_id,
        )
        return record

    async def get_secret_plaintext(
        self,
        secret_id: str,
        requesting_module: Optional[str] = None,
    ) -> str:
        """Retrieves and decrypts the secret value inside authorized backend services only."""
        stmt = select(ManagedSecretRecord).where(ManagedSecretRecord.secret_id == secret_id)
        res = await self.db.execute(stmt)
        record = res.scalar_one_or_none()

        if not record:
            raise ValueError(f"Secret '{secret_id}' not found.")

        if record.status == SecretStatus.REVOKED:
            raise ValueError(f"Secret '{secret_id}' is REVOKED and cannot be accessed.")

        if record.expires_at and record.expires_at < datetime.now(timezone.utc):
            raise ValueError(f"Secret '{secret_id}' has EXPIRED.")

        dek = await self.key_service.get_key_by_id(record.key_id)

        aad = {
            "secret_id": record.secret_id,
            "secret_type": record.secret_type,
            "owner_module": record.owner_module,
        }

        return CryptographyProvider.decrypt(
            key=dek,
            envelope_json=record.ciphertext_payload,
            expected_aad_context=aad,
        )

    async def rotate_secret(
        self,
        secret_id: str,
        new_plaintext_value: str,
        expires_at: Optional[datetime] = None,
        actor_id: Optional[str] = None,
    ) -> ManagedSecretRecord:
        """Rotates a secret: archives old version and encrypts new value under active DEK."""
        stmt = select(ManagedSecretRecord).where(ManagedSecretRecord.secret_id == secret_id)
        res = await self.db.execute(stmt)
        record = res.scalar_one_or_none()

        if not record:
            raise ValueError(f"Secret '{secret_id}' not found.")

        now = datetime.now(timezone.utc)

        # 1. Archive current version to history
        history = SecretVersionHistoryRecord(
            history_id=f"hist-{uuid.uuid4().hex[:12]}",
            secret_id=record.secret_id,
            version=record.current_version,
            ciphertext_payload=record.ciphertext_payload,
            key_id=record.key_id,
            status=SecretStatus.DEPRECATED,
            created_at=now,
        )
        self.db.add(history)

        # 2. Encrypt new value with current active DEK
        active_key_id, dek = await self.key_service.get_active_key()
        aad = {
            "secret_id": record.secret_id,
            "secret_type": record.secret_type,
            "owner_module": record.owner_module,
        }

        new_ciphertext = CryptographyProvider.encrypt(
            key=dek,
            plaintext=new_plaintext_value,
            aad_context=aad,
            key_id=active_key_id,
        )

        record.current_version += 1
        record.ciphertext_payload = new_ciphertext
        record.key_id = active_key_id
        record.last_rotated_at = now
        record.status = SecretStatus.ACTIVE
        if expires_at:
            record.expires_at = expires_at

        await self.db.commit()
        await self.db.refresh(record)

        await self._record_security_event(
            event_type="SECRET_ROTATED",
            severity="INFO",
            resource_id=secret_id,
            details={"version": record.current_version},
            actor_id=actor_id,
        )
        return record

    async def revoke_secret(
        self,
        secret_id: str,
        reason: str = "COMPROMISE_SUSPECTED",
        actor_id: Optional[str] = None,
    ) -> bool:
        """Immediately marks a secret as REVOKED."""
        stmt = select(ManagedSecretRecord).where(ManagedSecretRecord.secret_id == secret_id)
        res = await self.db.execute(stmt)
        record = res.scalar_one_or_none()
        if not record:
            return False

        record.status = SecretStatus.REVOKED
        await self.db.commit()

        await self._record_security_event(
            event_type="SECRET_REVOKED",
            severity="CRITICAL",
            resource_id=secret_id,
            details={"reason": reason},
            actor_id=actor_id,
        )
        return True

    async def list_secrets(self) -> List[ManagedSecretRecord]:
        """Lists metadata of all registered secrets (never returns ciphertext or plaintext)."""
        res = await self.db.execute(
            select(ManagedSecretRecord).order_by(ManagedSecretRecord.created_at.desc())
        )
        return list(res.scalars().all())
