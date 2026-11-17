from typing import Optional, Callable
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.infrastructure_platform.authentication.router import (
    get_current_authenticated_user,
)
from backend.app.modules.infrastructure_platform.authorization.services.authz_service import (
    AuthorizationService,
)


def require_permission(permission_code: str):
    """FastAPI Dependency enforcing granular action permission on authenticated principal."""
    async def dependency(
        request: Request,
        auth_context=Depends(get_current_authenticated_user),
        db: AsyncSession = Depends(get_db),
    ):
        user, _ = auth_context
        service = AuthorizationService(db)
        correlation_id = getattr(request.state, "request_id", None)

        is_allowed, reason = await service.authorize(
            user_id=user.user_id,
            permission_code=permission_code,
            resource_type="SYSTEM",
            correlation_id=correlation_id,
        )
        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: {reason}",
            )
        return user

    return dependency


def require_portfolio_access(permission_code: str, portfolio_param: str = "portfolio_id"):
    """FastAPI Dependency enforcing granular permission AND portfolio isolation."""
    async def dependency(
        request: Request,
        auth_context=Depends(get_current_authenticated_user),
        db: AsyncSession = Depends(get_db),
    ):
        user, _ = auth_context
        service = AuthorizationService(db)
        correlation_id = getattr(request.state, "request_id", None)

        # Extract portfolio_id from path parameters or query parameters
        portfolio_id = request.path_params.get(portfolio_param) or request.query_params.get(portfolio_param)
        if not portfolio_id:
            # Check JSON body if available
            try:
                body = await request.json()
                portfolio_id = body.get(portfolio_param)
            except Exception:
                portfolio_id = None

        if not portfolio_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required portfolio parameter: '{portfolio_param}'",
            )

        is_allowed, reason = await service.authorize(
            user_id=user.user_id,
            permission_code=permission_code,
            resource_type="PORTFOLIO",
            resource_id=portfolio_id,
            correlation_id=correlation_id,
        )
        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: {reason}",
            )
        return user

    return dependency
