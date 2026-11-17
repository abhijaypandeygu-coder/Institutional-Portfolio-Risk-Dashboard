from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.infrastructure_platform.encryption.models.encryption_models import (
    KeyStatus,
    SecretStatus,
)


class SecretCreateRequest(BaseModel):
    secret_name: str = Field(..., min_length=3, max_length=128)
    secret_type: str = Field(..., description="API_KEY, DB_CREDENTIAL, OAUTH_TOKEN, WEBHOOK_SECRET")
    owner_module: str = Field(..., description="Owning module code, e.g. M01_FEED_REGISTRY")
    plaintext_value: str = Field(..., min_length=1, description="Secret payload to encrypt at rest")
    expires_at: Optional[datetime] = None


class SecretRotateRequest(BaseModel):
    new_plaintext_value: str = Field(..., min_length=1)
    expires_at: Optional[datetime] = None


class SecretMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    secret_id: str
    secret_name: str
    secret_type: str
    owner_module: str
    current_version: int
    status: SecretStatus
    key_id: str
    expires_at: Optional[datetime] = None
    last_rotated_at: datetime
    created_at: datetime


class KeyMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key_id: str
    key_version: int
    key_purpose: str
    algorithm: str
    kek_identifier: str
    status: KeyStatus
    created_at: datetime
    activated_at: datetime
    retired_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    policy_id: str
    policy_name: str
    classification: str
    algorithm: str
    key_rotation_days: int
    enforce_aad: bool
    status: str
    created_at: datetime


class SecurityEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    event_type: str
    severity: str
    resource_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    source_ip: Optional[str] = None
    actor_id: Optional[str] = None
    occurred_at: datetime


class EncryptionHealthResponse(BaseModel):
    status: str
    active_keys_count: int
    active_secrets_count: int
    kek_provider_status: str
    algorithm: str
    timestamp: datetime
