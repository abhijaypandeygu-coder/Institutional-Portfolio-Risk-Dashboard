import json
import logging
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
from backend.app.modules.infrastructure_platform.logging.services.redaction_service import (
    LogRedactionService,
    REDACTED_PLACEHOLDER,
)
from backend.app.modules.infrastructure_platform.logging.services.correlation_context import (
    CorrelationContext,
)
from backend.app.modules.infrastructure_platform.logging.formatters.json_formatter import (
    JsonLogFormatter,
)
from backend.app.modules.infrastructure_platform.logging.handlers.log_manager import (
    setup_application_logging,
    get_structured_logger,
)
from backend.app.modules.infrastructure_platform.logging.services.log_search_service import (
    LogSearchService,
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


def test_log_redaction_service():
    """Verify passwords, tokens, API keys, and auth headers are sanitized."""
    sensitive_payload = {
        "user_id": "usr-1234",
        "username": "trader1",
        "password": "SuperSecretPassword123!",
        "api_key": "ALPHA_VANTAGE_LIVE_KEY_9988",
        "nested": {
            "token": "jwt.header.payload.signature",
            "safe_field": 42,
        },
        "connection_str": "postgresql://admin:password=MyDbPass123@localhost:5432/hft",
        "auth_header": "Bearer secret_session_token_xyz",
    }

    clean = LogRedactionService.sanitize(sensitive_payload)
    assert clean["password"] == REDACTED_PLACEHOLDER
    assert clean["api_key"] == REDACTED_PLACEHOLDER
    assert clean["nested"]["token"] == REDACTED_PLACEHOLDER
    assert clean["nested"]["safe_field"] == 42
    assert "MyDbPass123" not in clean["connection_str"]
    assert "secret_session_token_xyz" not in clean["auth_header"]


def test_json_formatter_and_correlation_context():
    """Verify structured JSON serialization and async correlation context binding."""
    CorrelationContext.set_correlation_id("corr-test-999")
    CorrelationContext.set_request_id("req-test-111")

    formatter = JsonLogFormatter()
    logger = logging.getLogger("test.logger")
    record = logger.makeRecord(
        name="test.logger",
        level=logging.INFO,
        fn="test_file.py",
        lno=10,
        msg="Execution test message",
        args=(),
        exc_info=None,
    )

    formatted_json = formatter.format(record)
    data = json.loads(formatted_json)

    assert data["level"] == "INFO"
    assert data["message"] == "Execution test message"
    assert data["correlation_id"] == "corr-test-999"
    assert data["request_id"] == "req-test-111"
    assert data["schema_version"] == "1.0"

    CorrelationContext.clear()


@pytest.mark.asyncio
async def test_middleware_request_correlation_headers(client):
    """Verify that incoming requests receive X-Correlation-ID and X-Request-ID headers."""
    resp = await client.get("/health/live", headers={"X-Correlation-ID": "corr-client-header-44"})
    assert resp.status_code == 200
    assert resp.headers.get("X-Correlation-ID") == "corr-client-header-44"
    assert resp.headers.get("X-Request-ID") is not None


@pytest.mark.asyncio
async def test_logging_api_health_and_search(db_session, client):
    """Verify administrative logging health and search endpoints under M15.05 RBAC."""
    setup_application_logging()
    test_logger = get_structured_logger("app.m07.risk")
    test_logger.info("Test operational message for search verification")

    auth_service = AuthenticationService(db_session)
    role_service = RoleManagementService(db_session)

    admin_user = await auth_service.create_user(
        username="sre_logs_admin",
        password="SreLogsAdminPassword2026!",
        display_name="Logs Administrator",
    )
    await role_service.assign_role_to_user(admin_user.user_id, "ADMINISTRATOR")

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "sre_logs_admin", "password": "SreLogsAdminPassword2026!"},
    )
    token = login_resp.json()["session_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Health check
    health_resp = await client.get("/api/v1/logging/health", headers=headers)
    assert health_resp.status_code == 200
    assert health_resp.json()["redaction_engine"] == "ACTIVE"

    # 2. Search logs
    search_resp = await client.get("/api/v1/logging/search?limit=10", headers=headers)
    assert search_resp.status_code == 200
    assert isinstance(search_resp.json(), list)
