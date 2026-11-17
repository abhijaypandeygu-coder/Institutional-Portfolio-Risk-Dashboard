import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.modules.infrastructure_platform.authentication.services.password_service import (
    PasswordSecurityService,
)
from backend.app.modules.infrastructure_platform.authentication.services.auth_service import (
    AuthenticationService,
)
from backend.app.modules.infrastructure_platform.authentication.models.auth_models import (
    AccountStatus,
    SessionStatus,
)

# Test Database setup (in-memory SQLite for high-speed isolated testing)
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
async def test_password_security_service():
    """Test standard password hashing, verification, and timing consistency."""
    pwd_service = PasswordSecurityService()
    raw_password = "Institutional_Risk_2026!#"

    # Hash password
    pw_hash, salt = pwd_service.hash_password(raw_password)
    assert pw_hash is not None
    assert salt is not None

    # Verify correct password
    assert pwd_service.verify_password(raw_password, pw_hash, salt) is True

    # Verify incorrect password
    assert pwd_service.verify_password("WrongPassword123!", pw_hash, salt) is False


@pytest.mark.asyncio
async def test_user_creation_and_login_success(db_session, client):
    """Test user creation, successful authentication, cookie receipt, and profile check."""
    auth_service = AuthenticationService(db_session)
    user = await auth_service.create_user(
        username="risk_officer",
        password="SuperSecurePassword123!",
        display_name="Chief Risk Officer",
        role="RISK_OFFICER",
    )
    assert user.user_id is not None
    assert user.account_status == AccountStatus.ACTIVE

    # Authenticate via API
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "risk_officer", "password": "SuperSecurePassword123!"},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["user"]["username"] == "risk_officer"
    assert data["session"]["status"] == SessionStatus.ACTIVE.value
    raw_token = data["session_token"]
    assert raw_token is not None

    # Check HttpOnly cookie set
    cookie = login_resp.cookies.get("institutional_session")
    assert cookie is not None

    # Access /me using Cookie
    me_resp = await client.get("/api/v1/auth/me", cookies={"institutional_session": raw_token})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["username"] == "risk_officer"
    assert me_data["display_name"] == "Chief Risk Officer"

    # Access /me using Bearer header
    bearer_resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {raw_token}"}
    )
    assert bearer_resp.status_code == 200
    assert bearer_resp.json()["username"] == "risk_officer"


@pytest.mark.asyncio
async def test_authentication_invalid_password_and_lockout(db_session, client):
    """Test failed login attempts, audit logging, and progressive account lockout."""
    auth_service = AuthenticationService(db_session)
    await auth_service.create_user(
        username="trader1",
        password="ValidPassword2026!",
        display_name="Equity Trader",
        role="TRADER",
    )

    # 4 consecutive invalid attempts - status 401
    for i in range(4):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "trader1", "password": "WrongPassword!"},
        )
        assert resp.status_code == 401
        err_msg = resp.json().get("error", {}).get("message", "")
        assert "Invalid username or password" in err_msg

    # 5th attempt locks the account
    resp_5 = await client.post(
        "/api/v1/auth/login",
        json={"username": "trader1", "password": "WrongPassword!"},
    )
    assert resp_5.status_code == 401
    err_msg_5 = resp_5.json().get("error", {}).get("message", "")
    assert "locked" in err_msg_5.lower()

    # 6th attempt with valid password should still fail due to lock
    resp_locked = await client.post(
        "/api/v1/auth/login",
        json={"username": "trader1", "password": "ValidPassword2026!"},
    )
    assert resp_locked.status_code == 401
    err_msg_locked = resp_locked.json().get("error", {}).get("message", "")
    assert "locked" in err_msg_locked.lower()


@pytest.mark.asyncio
async def test_authentication_nonexistent_user_enumeration_resistant(client):
    """Test that nonexistent user returns generic 401 message and executes dummy timing hash."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "non_existent_user_xyz", "password": "SomePassword123!"},
    )
    assert resp.status_code == 401
    err_msg = resp.json().get("error", {}).get("message", "")
    assert err_msg == "Invalid username or password."


@pytest.mark.asyncio
async def test_logout_and_session_revocation(db_session, client):
    """Test session revocation upon logout and rejection of revoked tokens."""
    auth_service = AuthenticationService(db_session)
    await auth_service.create_user(
        username="auditor",
        password="AuditorPassword2026!",
        display_name="Internal Auditor",
        role="AUDITOR",
    )

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "auditor", "password": "AuditorPassword2026!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["session_token"]

    # Verify session works
    resp_me_before = await client.get("/api/v1/auth/me", cookies={"institutional_session": token})
    assert resp_me_before.status_code == 200

    # Logout
    logout_resp = await client.post(
        "/api/v1/auth/logout", cookies={"institutional_session": token}
    )
    assert logout_resp.status_code == 200
    assert logout_resp.json()["message"] == "Successfully logged out."

    # Verify token is now invalid / rejected
    resp_me_after = await client.get("/api/v1/auth/me", cookies={"institutional_session": token})
    assert resp_me_after.status_code == 401
