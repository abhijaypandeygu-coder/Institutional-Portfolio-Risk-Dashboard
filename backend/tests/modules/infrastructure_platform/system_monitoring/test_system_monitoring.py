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
from backend.app.modules.infrastructure_platform.system_monitoring.services.resource_collector import (
    SystemResourceCollector,
)
from backend.app.modules.infrastructure_platform.system_monitoring.services.database_collector import (
    DatabaseMonitoringCollector,
)
from backend.app.modules.infrastructure_platform.system_monitoring.services.health_check_service import (
    HealthCheckService,
)
from backend.app.modules.infrastructure_platform.system_monitoring.models.monitoring_models import (
    HealthStatus,
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


@pytest.mark.asyncio
async def test_resource_collectors():
    """Verify CPU and Memory collectors return non-zero, valid measurements with units."""
    cpu = SystemResourceCollector.collect_cpu_metrics()
    assert cpu.system_cpu_utilization_pct >= 0.0
    assert cpu.core_count_logical >= 1

    mem = SystemResourceCollector.collect_memory_metrics()
    assert mem.total_physical_mb > 0
    assert mem.used_mb > 0
    assert mem.utilization_pct > 0.0
    assert mem.process_rss_mb > 0.0


@pytest.mark.asyncio
async def test_database_monitoring_collector(db_session):
    """Verify database collector evaluates query latency and connection pool metrics."""
    collector = DatabaseMonitoringCollector(db_session)
    metrics = await collector.collect_database_metrics()
    assert metrics.status == HealthStatus.HEALTHY
    assert metrics.query_latency_avg_ms >= 0.0
    assert metrics.pool_size >= 1


@pytest.mark.asyncio
async def test_health_check_service_readiness(db_session):
    """Verify readiness evaluation on database and cryptographic dependencies."""
    service = HealthCheckService(db_session)
    readiness = await service.evaluate_readiness()
    assert readiness.ready is True
    assert readiness.status == HealthStatus.HEALTHY
    assert "database" in readiness.dependencies
    assert readiness.dependencies["database"].status == HealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_liveness_and_readiness_endpoints(client):
    """Verify public lightweight probes /health/live and /health/ready."""
    live_resp = await client.get("/health/live")
    assert live_resp.status_code == 200
    live_data = live_resp.json()
    assert live_data["status"] == "ALIVE"
    assert live_data["uptime_seconds"] >= 0.0

    ready_resp = await client.get("/health/ready")
    assert ready_resp.status_code == 200
    ready_data = ready_resp.json()
    assert ready_data["ready"] is True
    assert ready_data["status"] == HealthStatus.HEALTHY.value


@pytest.mark.asyncio
async def test_monitoring_overview_api(db_session, client):
    """Verify authenticated administrative monitoring endpoint."""
    auth_service = AuthenticationService(db_session)
    role_service = RoleManagementService(db_session)

    admin_user = await auth_service.create_user(
        username="sre_admin",
        password="SreAdminPassword2026!",
        display_name="Site Reliability Engineer",
    )
    await role_service.assign_role_to_user(admin_user.user_id, "ADMINISTRATOR")

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "sre_admin", "password": "SreAdminPassword2026!"},
    )
    token = login_resp.json()["session_token"]
    headers = {"Authorization": f"Bearer {token}"}

    overview_resp = await client.get("/api/v1/monitoring/overview", headers=headers)
    assert overview_resp.status_code == 200
    data = overview_resp.json()
    assert data["overall_status"] == HealthStatus.HEALTHY.value
    assert data["cpu"]["core_count_logical"] >= 1
    assert data["memory"]["total_physical_mb"] > 0
    assert data["database"]["status"] == HealthStatus.HEALTHY.value
