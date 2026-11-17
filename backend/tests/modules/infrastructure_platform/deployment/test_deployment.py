"""
Automated Integration and Unit Tests for M15.11 Deployment Module.
Validates environment preflight validation, safety boundaries, release manifest generation,
and REST API endpoints.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.modules.infrastructure_platform.deployment.services import (
    EnvironmentValidator,
    ServiceOrchestrator,
    ReleaseManager,
)
from backend.app.modules.infrastructure_platform.deployment.models.deployment_models import (
    ServiceLifecycleStatus,
)


@pytest.mark.unit
def test_environment_validator_python_version():
    """Validates Python version compatibility evaluation."""
    res = EnvironmentValidator.validate_python_version()
    assert res["compatible"] is True
    assert "3.10" in res["version"] or "3." in res["version"]


@pytest.mark.unit
def test_database_safety_guardrails():
    """Ensures production database URLs are blocked from local execution."""
    safe_res = EnvironmentValidator.validate_database_safety("sqlite+aiosqlite:///./feed_registry.db")
    assert safe_res["url_safe"] is True

    unsafe_res = EnvironmentValidator.validate_database_safety("postgresql+asyncpg://admin:pass@production-db.internal:5432/live_data")
    assert unsafe_res["url_safe"] is False


@pytest.mark.unit
def test_service_orchestrator_application_status():
    """Validates application readiness coordination across registered services."""
    states = ServiceOrchestrator.get_service_states()
    assert len(states) >= 3
    service_codes = [s["service_code"] for s in states]
    assert "database" in service_codes
    assert "backend_api" in service_codes

    overall = ServiceOrchestrator.get_overall_application_status()
    assert overall in [ServiceLifecycleStatus.READY, ServiceLifecycleStatus.DEGRADED]


@pytest.mark.unit
def test_release_manifest_generation():
    """Validates machine-readable release manifest completeness."""
    manifest = ReleaseManager.generate_release_manifest()
    assert manifest["application_version"] == "1.0.0"
    assert "BUILD-" in manifest["build_identifier"]
    assert "expected_schema_revision" in manifest
    assert "runtime_requirements" in manifest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_deployment_validate_api():
    """Validates GET /api/v1/deployment/validate endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/deployment/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is True
        assert data["database_url_safe"] is True
        assert "port_availability" in data


@pytest.mark.asyncio
@pytest.mark.integration
async def test_deployment_status_api():
    """Validates GET /api/v1/deployment/status endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/deployment/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["application_version"] == "1.0.0"
        assert len(data["services"]) >= 3
        assert data["environment_safe"] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_deployment_manifest_api():
    """Validates GET /api/v1/deployment/releases/manifest endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/deployment/releases/manifest")
        assert resp.status_code == 200
        manifest = resp.json()
        assert manifest["application_version"] == "1.0.0"
