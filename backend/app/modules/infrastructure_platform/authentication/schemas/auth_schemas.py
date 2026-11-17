from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.infrastructure_platform.authentication.models.auth_models import (
    AccountStatus,
    SessionStatus,
)


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username or email address")
    password: str = Field(..., description="Plaintext password submitted for verification")


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    username: str
    display_name: str
    role: str
    account_status: AccountStatus
    last_login_at: Optional[datetime] = None


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    status: SessionStatus
    expires_at: datetime
    last_activity_at: datetime


class LoginResponse(BaseModel):
    authenticated: bool
    session_token: Optional[str] = Field(None, description="Raw session token returned for API / Bearer header clients")
    user: UserProfileResponse
    session: SessionResponse


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=12, description="New password meeting minimum 12 chars")


class SessionSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    status: SessionStatus
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    is_current: bool = False
