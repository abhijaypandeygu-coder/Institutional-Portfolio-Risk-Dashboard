import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.modules.infrastructure_platform.authentication.services.auth_service import (
    AuthenticationService,
)
from backend.app.modules.infrastructure_platform.authorization.services.role_service import (
    RoleManagementService,
)
from backend.app.modules.infrastructure_platform.authorization.services.portfolio_scope_service import (
    PortfolioScopeService,
)
from backend.app.modules.infrastructure_platform.authorization.services.authz_service import (
    AuthorizationService,
)
from backend.app.modules.infrastructure_platform.authorization.models.authz_models import (
    ScopeType,
    AuthDecisionType,
)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        # Seed standard roles and permissions
        role_service = RoleManagementService(session)
        await role_service.initialize_standard_roles_and_permissions()
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_standard_roles_and_permission_seeding(db_session):
    """Verify that VIEWER, ANALYST, OPERATOR, ADMINISTRATOR roles and standard permissions are seeded."""
    role_service = RoleManagementService(db_session)
    roles = await role_service.list_roles()
    role_codes = {r.role_code for r in roles}
    assert "VIEWER" in role_codes
    assert "ANALYST" in role_codes
    assert "OPERATOR" in role_codes
    assert "ADMINISTRATOR" in role_codes

    analyst_role = await role_service.get_role_by_code("ANALYST")
    assert analyst_role is not None
    perm_codes = {rp.permission.permission_code for rp in analyst_role.permissions if rp.permission}
    assert "risk.analytics.execute" in perm_codes
    assert "scenario.execute" in perm_codes
    assert "admin.roles.manage" not in perm_codes


@pytest.mark.asyncio
async def test_rbac_authorization_checks(db_session):
    """Verify RBAC permissions for Viewer vs Analyst vs Administrator."""
    auth_service = AuthenticationService(db_session)
    role_service = RoleManagementService(db_session)
    authz_service = AuthorizationService(db_session)

    # 1. Create a Viewer user
    viewer_user = await auth_service.create_user(
        username="viewer1",
        password="ViewerPassword2026!",
        display_name="Viewer One",
    )
    await role_service.assign_role_to_user(viewer_user.user_id, "VIEWER")

    # Viewer can read portfolio metrics
    allowed, _ = await authz_service.authorize(viewer_user.user_id, "portfolio.read")
    assert allowed is True

    # Viewer CANNOT run risk analytics
    allowed, reason = await authz_service.authorize(viewer_user.user_id, "risk.analytics.execute")
    assert allowed is False
    assert "Missing required permission" in reason

    # 2. Create an Analyst user
    analyst_user = await auth_service.create_user(
        username="analyst1",
        password="AnalystPassword2026!",
        display_name="Analyst One",
    )
    await role_service.assign_role_to_user(analyst_user.user_id, "ANALYST")

    # Analyst can run risk analytics
    allowed, _ = await authz_service.authorize(analyst_user.user_id, "risk.analytics.execute")
    assert allowed is True

    # Analyst CANNOT manage admin roles
    allowed, _ = await authz_service.authorize(analyst_user.user_id, "admin.roles.manage")
    assert allowed is False


@pytest.mark.asyncio
async def test_portfolio_isolation(db_session):
    """Verify portfolio-level access isolation: user cannot access unassigned portfolios."""
    auth_service = AuthenticationService(db_session)
    role_service = RoleManagementService(db_session)
    scope_service = PortfolioScopeService(db_session)
    authz_service = AuthorizationService(db_session)

    user = await auth_service.create_user(
        username="pm_asia",
        password="PmPassword2026!",
        display_name="PM Asia",
    )
    await role_service.assign_role_to_user(user.user_id, "OPERATOR")

    # Grant access to PORTFOLIO_ASIA only
    await scope_service.grant_portfolio_access(user.user_id, "PORTFOLIO_ASIA", access_level="WRITE")

    # Accessing PORTFOLIO_ASIA is allowed
    allowed, _ = await authz_service.authorize(
        user.user_id,
        permission_code="portfolio.positions.read",
        resource_type="PORTFOLIO",
        resource_id="PORTFOLIO_ASIA",
    )
    assert allowed is True

    # Accessing unassigned PORTFOLIO_US is DENIED
    allowed, reason = await authz_service.authorize(
        user.user_id,
        permission_code="portfolio.positions.read",
        resource_type="PORTFOLIO",
        resource_id="PORTFOLIO_US",
    )
    assert allowed is False
    assert "restricted" in reason.lower()


@pytest.mark.asyncio
async def test_self_escalation_prevention(db_session, client):
    """Verify that a user cannot assign an ADMINISTRATOR role to themselves via API."""
    auth_service = AuthenticationService(db_session)
    role_service = RoleManagementService(db_session)

    admin_user = await auth_service.create_user(
        username="admin_user",
        password="AdminPassword2026!",
        display_name="Admin User",
    )
    await role_service.assign_role_to_user(admin_user.user_id, "ADMINISTRATOR")

    # Login admin
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin_user", "password": "AdminPassword2026!"},
    )
    token = login_resp.json()["session_token"]

    # Attempt to self-assign another administrator role
    resp = await client.post(
        f"/api/v1/authz/users/{admin_user.user_id}/roles",
        json={"role_code": "ADMINISTRATOR", "scope_type": "GLOBAL"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    err_msg = resp.json().get("error", {}).get("message", "")
    assert "Self-escalation prevention" in err_msg


@pytest.mark.asyncio
async def test_api_permission_enforcement(db_session, client):
    """Verify API endpoint protection with 401 unauthenticated and 403 forbidden responses."""
    auth_service = AuthenticationService(db_session)
    role_service = RoleManagementService(db_session)

    # 1. Unauthenticated request to protected admin endpoint -> 401
    unauth_resp = await client.get("/api/v1/authz/roles")
    assert unauth_resp.status_code == 401

    # 2. Authenticated Viewer requesting admin endpoint -> 403
    viewer = await auth_service.create_user(
        username="simple_viewer",
        password="ViewerPassword2026!",
        display_name="Simple Viewer",
    )
    await role_service.assign_role_to_user(viewer.user_id, "VIEWER")

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "simple_viewer", "password": "ViewerPassword2026!"},
    )
    token = login_resp.json()["session_token"]

    forbidden_resp = await client.get(
        "/api/v1/authz/roles",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert forbidden_resp.status_code == 403
    err_msg = forbidden_resp.json().get("error", {}).get("message", "")
    assert "Forbidden" in err_msg
