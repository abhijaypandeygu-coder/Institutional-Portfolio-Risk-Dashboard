"""Security, RBAC, SecretReference abstraction, and Audit Logging."""
import os
import re
import logging
from enum import Enum
from typing import Optional, Dict, Union, List
from pydantic import BaseModel
from fastapi import Header, HTTPException, status, Depends
from backend.app.core.config import settings

logger = logging.getLogger("feed_registry.security")

SECRET_URI_PATTERN = re.compile(r"^secret://([a-zA-Z0-9_\-]+)/([a-zA-Z0-9_\-]+)$")


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    READ_ONLY = "READ_ONLY"


class AuthenticatedUser(BaseModel):
    username: str
    role: UserRole


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

    @classmethod
    def is_valid_uri(cls, uri: str) -> bool:
        return bool(SECRET_URI_PATTERN.match(uri))

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


ROLE_HIERARCHY = {
    UserRole.ADMIN: 3,
    UserRole.OPERATOR: 2,
    UserRole.READ_ONLY: 1,
}


async def get_current_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_actor: Optional[str] = Header(None, alias="X-Actor"),
) -> AuthenticatedUser:
    """Authenticates API requests using API Key."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required authentication header 'X-API-Key'.",
        )

    if x_api_key == settings.API_KEY_ADMIN:
        return AuthenticatedUser(username=x_actor or "admin_user", role=UserRole.ADMIN)
    elif x_api_key == settings.API_KEY_OPERATOR:
        return AuthenticatedUser(username=x_actor or "operator_user", role=UserRole.OPERATOR)
    elif x_api_key == settings.API_KEY_READ_ONLY:
        return AuthenticatedUser(username=x_actor or "readonly_user", role=UserRole.READ_ONLY)
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key provided.",
        )


def require_role(min_role: UserRole):
    """Enforces minimum required role based on role hierarchy."""
    async def role_checker(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        user_level = ROLE_HIERARCHY.get(user.role, 0)
        required_level = ROLE_HIERARCHY.get(min_role, 0)
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires '{min_role.value}' role or higher. Current role: '{user.role.value}'.",
            )
        return user
    return role_checker
