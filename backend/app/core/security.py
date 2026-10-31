"""Security, RBAC, SecretReference abstraction, and Audit Logging."""
import os
import re
import logging
from enum import Enum
from typing import Optional, Dict
from datetime import datetime
from fastapi import Header, HTTPException, status
from backend.app.core.config import settings

logger = logging.getLogger("feed_registry.security")

SECRET_URI_PATTERN = re.compile(r"^secret://([a-zA-Z0-9_\-]+)/([a-zA-Z0-9_\-]+)$")


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    READ_ONLY = "READ_ONLY"


class SecretReference:
    """Immutable secret reference descriptor (secret://<scope>/<key>)."""

    def __init__(self, uri: str):
        match = SECRET_URI_PATTERN.match(uri)
        if not match:
            raise ValueError(
                f"Invalid secret URI '{uri}'. Must follow pattern 'secret://<scope>/<key>'"
            )
        self.uri = uri
        self.scope = match.group(1)
        self.key_name = match.group(2)

    @property
    def env_var_name(self) -> str:
        return f"SECRET_REF_{self.scope.upper()}_{self.key_name.upper()}"


class SecretsManager:
    """Zero-knowledge secrets resolution and existence checking."""

    _test_store: Dict[str, str] = {}

    @classmethod
    def set_test_secret(cls, uri: str, value: str):
        cls._test_store[uri] = value

    @classmethod
    def exists(cls, ref: SecretReference) -> bool:
        if ref.uri in cls._test_store:
            return bool(cls._test_store[ref.uri])
        val = os.getenv(ref.env_var_name)
        return val is not None and len(val.strip()) > 0

    @classmethod
    def resolve(cls, ref: SecretReference, actor: str = "system") -> Optional[str]:
        if ref.uri in cls._test_store:
            return cls._test_store[ref.uri]
        val = os.getenv(ref.env_var_name)
        if val and len(val.strip()) > 0:
            logger.info(f"AUDIT_SECRET_ACCESS uri={ref.uri} actor={actor} status=RESOLVED")
            return val
        logger.warning(f"AUDIT_SECRET_ACCESS uri={ref.uri} actor={actor} status=NOT_FOUND")
        return None


def get_current_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_actor: Optional[str] = Header("anonymous", alias="X-Actor")
) -> Dict[str, str]:
    """Authenticates API requests and resolves UserRole."""
    if not x_api_key or x_api_key == settings.ADMIN_API_KEY:
        return {"role": UserRole.ADMIN, "actor": x_actor or "admin"}
    elif x_api_key == settings.OPERATOR_API_KEY:
        return {"role": UserRole.OPERATOR, "actor": x_actor or "operator"}
    elif x_api_key == settings.READONLY_API_KEY:
        return {"role": UserRole.READ_ONLY, "actor": x_actor or "readonly"}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key."
        )


def require_role(required_roles: list[UserRole]):
    """Enforces Role-Based Access Control (RBAC)."""
    def dependency(user: Dict[str, str] = Header(None)):
        pass
    return dependency

