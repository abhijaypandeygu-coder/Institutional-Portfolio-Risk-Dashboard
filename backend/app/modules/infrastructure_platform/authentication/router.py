from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.infrastructure_platform.authentication.schemas.auth_schemas import (
    LoginRequest,
    LoginResponse,
    UserProfileResponse,
    SessionResponse,
    ChangePasswordRequest,
    SessionSummaryResponse,
)
from backend.app.modules.infrastructure_platform.authentication.services.auth_service import (
    AuthenticationService,
)

router = APIRouter(prefix="/api/v1/auth", tags=["M15.04 Authentication"])

SESSION_COOKIE_NAME = "institutional_session"


async def get_current_authenticated_user(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Dependency extracting token from Authorization header or secure cookie, returning (user, session)."""
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ")[1].strip()
    elif SESSION_COOKIE_NAME in request.cookies:
        token = request.cookies[SESSION_COOKIE_NAME]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing session credentials.",
        )

    service = AuthenticationService(db)
    result = await service.validate_session(token)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid, expired, or revoked.",
        )
    return result


@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticates local credentials, generates an opaque session, and sets secure HttpOnly cookie."""
    service = AuthenticationService(db)
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    try:
        user, session, raw_token = await service.authenticate_user(
            login_identifier=req.username,
            password=req.password,
            ip_address=client_ip,
            user_agent=user_agent,
        )

        # Set secure HttpOnly session cookie
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=raw_token,
            httponly=True,
            samesite="lax",
            secure=False, # True in production HTTPS
            max_age=12 * 3600,
        )

        return LoginResponse(
            authenticated=True,
            session_token=raw_token,
            user=UserProfileResponse(
                user_id=user.user_id,
                username=user.login_identifier,
                display_name=user.display_name,
                role=user.role,
                account_status=user.account_status,
                last_login_at=user.last_login_at,
            ),
            session=SessionResponse(
                session_id=session.session_id,
                status=session.status,
                expires_at=session.expires_at,
                last_activity_at=session.last_activity_at,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/logout")
async def logout(
    response: Response,
    auth_context=Depends(get_current_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Revokes active session on server and purges session cookie."""
    user, session = auth_context
    service = AuthenticationService(db)
    await service.revoke_session(session.session_id, reason="USER_LOGOUT")
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"status": "SUCCESS", "message": "Successfully logged out."}


@router.get("/me", response_model=UserProfileResponse)
async def get_current_profile(
    auth_context=Depends(get_current_authenticated_user),
):
    """Retrieves authenticated user profile."""
    user, _ = auth_context
    return UserProfileResponse(
        user_id=user.user_id,
        username=user.login_identifier,
        display_name=user.display_name,
        role=user.role,
        account_status=user.account_status,
        last_login_at=user.last_login_at,
    )
