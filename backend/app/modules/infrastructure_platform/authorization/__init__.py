from backend.app.modules.infrastructure_platform.authorization.router import router
from backend.app.modules.infrastructure_platform.authorization.dependencies import (
    require_permission,
    require_portfolio_access,
)

__all__ = ["router", "require_permission", "require_portfolio_access"]
