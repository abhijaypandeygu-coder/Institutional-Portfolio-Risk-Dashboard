import uuid
import base64
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.infrastructure_platform.encryption.models.encryption_models import (
    EncryptionKeyRecord,
    KeyStatus,
)
from backend.app.modules.infrastructure_platform.encryption.services.cryptography_provider import (
    CryptographyProvider,
)
from backend.app.modules.infrastructure_platform.encryption.services.kek_provider import (
    MasterKekProvider,
)


class KeyManagementService:
    """Manages DEK generation, KEK wrapping, key rotation, and version retrieval."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_key(self) -> Tuple[str, bytes]:
        """Resolves the current active DEK. Generates initial active key if none exists."""
        stmt = (
            select(EncryptionKeyRecord)
            .where(EncryptionKeyRecord.status == KeyStatus.ACTIVE)
            .order_by(EncryptionKeyRecord.key_version.desc())
        )
        res = await self.db.execute(stmt)
        record = res.scalars().first()

        if not record:
            record = await self.generate_new_key(key_version=1)

        kek = MasterKekProvider.get_master_kek()
        dek_hex = CryptographyProvider.decrypt(
            kek,
            record.wrapped_key_payload,
            expected_aad_context={"key_id": record.key_id, "type": "DEK_WRAPPING"},
        )
        return record.key_id, bytes.fromhex(dek_hex)

    async def get_key_by_id(self, key_id: str) -> bytes:
        """Unwraps a historical or active DEK by key_id."""
        stmt = select(EncryptionKeyRecord).where(EncryptionKeyRecord.key_id == key_id)
        res = await self.db.execute(stmt)
        record = res.scalar_one_or_none()
        if not record:
            raise ValueError(f"Encryption key '{key_id}' not found in registry.")

        if record.status == KeyStatus.REVOKED:
            raise ValueError(f"Encryption key '{key_id}' has been REVOKED. Decryption blocked.")

        kek = MasterKekProvider.get_master_kek()
        dek_hex = CryptographyProvider.decrypt(
            kek,
            record.wrapped_key_payload,
            expected_aad_context={"key_id": record.key_id, "type": "DEK_WRAPPING"},
        )
        return bytes.fromhex(dek_hex)

    async def generate_new_key(self, key_version: int = 1) -> EncryptionKeyRecord:
        """Generates a random 256-bit DEK, wraps it with Master KEK, and records metadata."""
        raw_dek = CryptographyProvider.generate_key()
        key_id = f"dek-{uuid.uuid4().hex[:12]}-v{key_version}"

        kek = MasterKekProvider.get_master_kek()
        wrapped_payload = CryptographyProvider.encrypt(
            kek,
            raw_dek.hex(),
            aad_context={"key_id": key_id, "type": "DEK_WRAPPING"},
            key_id="MASTER_KEK",
        )

        record = EncryptionKeyRecord(
            key_id=key_id,
            key_version=key_version,
            key_purpose="FIELD_ENCRYPTION",
            algorithm="AES-256-GCM",
            wrapped_key_payload=wrapped_payload,
            kek_identifier="MASTER_KEK_V1",
            status=KeyStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            activated_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def rotate_keys(self) -> EncryptionKeyRecord:
        """Retires current active key and generates a new active key version."""
        stmt = (
            select(EncryptionKeyRecord)
            .where(EncryptionKeyRecord.status == KeyStatus.ACTIVE)
        )
        res = await self.db.execute(stmt)
        active_keys = res.scalars().all()

        max_version = 0
        now = datetime.now(timezone.utc)
        for k in active_keys:
            if k.key_version > max_version:
                max_version = k.key_version
            k.status = KeyStatus.RETIRED
            k.retired_at = now

        new_key = await self.generate_new_key(key_version=max_version + 1)
        await self.db.commit()
        return new_key

    async def revoke_key(self, key_id: str) -> bool:
        """Immediately revokes an encryption key due to suspected compromise."""
        stmt = select(EncryptionKeyRecord).where(EncryptionKeyRecord.key_id == key_id)
        res = await self.db.execute(stmt)
        record = res.scalar_one_or_none()
        if not record:
            return False

        record.status = KeyStatus.REVOKED
        record.revoked_at = datetime.now(timezone.utc)
        await self.db.commit()
        return True

    async def list_keys(self) -> List[EncryptionKeyRecord]:
        res = await self.db.execute(
            select(EncryptionKeyRecord).order_by(EncryptionKeyRecord.created_at.desc())
        )
        return list(res.scalars().all())
