from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.app.core.database import get_db
from backend.app.modules.infrastructure_platform.authorization.dependencies import (
    require_permission,
)
from backend.app.modules.infrastructure_platform.encryption.models.encryption_models import (
    EncryptionKeyRecord,
    ManagedSecretRecord,
    SecurityAuditEventRecord,
    EncryptionPolicyRecord,
    KeyStatus,
    SecretStatus,
)
from backend.app.modules.infrastructure_platform.encryption.schemas.encryption_schemas import (
    SecretCreateRequest,
    SecretRotateRequest,
    SecretMetadataResponse,
    KeyMetadataResponse,
    PolicyResponse,
    SecurityEventResponse,
    EncryptionHealthResponse,
)
from backend.app.modules.infrastructure_platform.encryption.services.key_management_service import (
    KeyManagementService,
)
from backend.app.modules.infrastructure_platform.encryption.services.secret_management_service import (
    SecretManagementService,
)

router = APIRouter(prefix="/api/v1/security", tags=["M15.06 Encryption & Secrets Management"])


@router.get("/health", response_model=EncryptionHealthResponse)
async def get_encryption_subsystem_health(
    admin_user=Depends(require_permission("admin.roles.read")),
    db: AsyncSession = Depends(get_db),
):
    """Provides operational status of the cryptographic subsystem without exposing key material."""
    keys_res = await db.execute(
        select(func.count(EncryptionKeyRecord.id)).where(EncryptionKeyRecord.status == KeyStatus.ACTIVE)
    )
    active_keys = keys_res.scalar() or 0

    secrets_res = await db.execute(
        select(func.count(ManagedSecretRecord.id)).where(ManagedSecretRecord.status == SecretStatus.ACTIVE)
    )
    active_secrets = secrets_res.scalar() or 0

    return EncryptionHealthResponse(
        status="OPERATIONAL",
        active_keys_count=active_keys,
        active_secrets_count=active_secrets,
        kek_provider_status="AVAILABLE",
        algorithm="AES-256-GCM",
        timestamp=datetime.now(timezone.utc),
    )


# --- Secrets Management Endpoints ---

@router.get("/secrets", response_model=List[SecretMetadataResponse])
async def list_secrets(
    admin_user=Depends(require_permission("admin.roles.read")),
    db: AsyncSession = Depends(get_db),
):
    """Lists registered application secret metadata (never plaintext or ciphertext)."""
    service = SecretManagementService(db)
    return await service.list_secrets()


@router.post("/secrets", response_model=SecretMetadataResponse, status_code=status.HTTP_201_CREATED)
async def create_secret(
    req: SecretCreateRequest,
    admin_user=Depends(require_permission("admin.roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Encrypts and registers a new managed secret using authenticated AES-256-GCM."""
    service = SecretManagementService(db)
    return await service.create_secret(
        secret_name=req.secret_name,
        secret_type=req.secret_type,
        owner_module=req.owner_module,
        plaintext_value=req.plaintext_value,
        expires_at=req.expires_at,
        actor_id=admin_user.user_id,
    )


@router.post("/secrets/{secret_id}/rotate", response_model=SecretMetadataResponse)
async def rotate_secret(
    secret_id: str,
    req: SecretRotateRequest,
    admin_user=Depends(require_permission("admin.roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Rotates a secret value, archiving prior version and encrypting new value under active DEK."""
    service = SecretManagementService(db)
    try:
        return await service.rotate_secret(
            secret_id=secret_id,
            new_plaintext_value=req.new_plaintext_value,
            expires_at=req.expires_at,
            actor_id=admin_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/secrets/{secret_id}/revoke")
async def revoke_secret(
    secret_id: str,
    admin_user=Depends(require_permission("admin.roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Immediately revokes an active secret."""
    service = SecretManagementService(db)
    success = await service.revoke_secret(secret_id=secret_id, actor_id=admin_user.user_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found.")
    return {"status": "SUCCESS", "message": f"Secret '{secret_id}' has been revoked."}


# --- Key Lifecycle Management Endpoints ---

@router.get("/keys", response_model=List[KeyMetadataResponse])
async def list_keys(
    admin_user=Depends(require_permission("admin.roles.read")),
    db: AsyncSession = Depends(get_db),
):
    """Lists registered DEK metadata."""
    service = KeyManagementService(db)
    return await service.list_keys()


@router.post("/keys/rotate", response_model=KeyMetadataResponse)
async def rotate_keys(
    admin_user=Depends(require_permission("admin.roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Retires active key version and provisions a new versioned DEK."""
    service = KeyManagementService(db)
    return await service.rotate_keys()


@router.post("/keys/{key_id}/revoke")
async def revoke_key(
    key_id: str,
    admin_user=Depends(require_permission("admin.roles.manage")),
    db: AsyncSession = Depends(get_db),
):
    """Revokes a compromised key, disabling any further encryption or decryption under this key."""
    service = KeyManagementService(db)
    success = await service.revoke_key(key_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Key not found.")
    return {"status": "SUCCESS", "message": f"Key '{key_id}' has been revoked."}


# --- Security Events Endpoints ---

@router.get("/events", response_model=List[SecurityEventResponse])
async def list_security_events(
    admin_user=Depends(require_permission("admin.roles.read")),
    db: AsyncSession = Depends(get_db),
):
    """Lists cryptographic and key lifecycle security events."""
    res = await db.execute(
        select(SecurityAuditEventRecord).order_by(SecurityAuditEventRecord.occurred_at.desc()).limit(100)
    )
    return list(res.scalars().all())
