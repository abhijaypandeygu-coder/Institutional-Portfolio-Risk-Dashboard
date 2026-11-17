import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app
from backend.app.modules.infrastructure_platform.backend_api.middleware import (
    REQUEST_ID_HEADER,
    PROCESS_TIME_HEADER,
)


@pytest.mark.asyncio
async def test_m15_01_request_tracing_middleware():
    """Verify that every HTTP response has X-Request-ID, X-Process-Time, and security headers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Request with client-supplied request ID
        resp = await ac.get("/api/v1/health", headers={REQUEST_ID_HEADER: "req-client-trace-123"})
        assert resp.status_code == 200
        assert resp.headers.get(REQUEST_ID_HEADER) == "req-client-trace-123"
        assert PROCESS_TIME_HEADER in resp.headers
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"

        # Request without request ID: verify auto-generation
        resp2 = await ac.get("/api/v1/health")
        assert resp2.status_code == 200
        gen_id = resp2.headers.get(REQUEST_ID_HEADER)
        assert gen_id is not None
        assert gen_id.startswith("req-")


@pytest.mark.asyncio
async def test_m15_01_standard_error_envelope_404():
    """Verify 404 responses conform to the standard institutional error envelope."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/non_existent_resource_endpoint")
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "RESOURCE_NOT_FOUND"
        assert "message" in data["error"]
        assert "request_id" in data["error"]


@pytest.mark.asyncio
async def test_m15_01_standard_error_envelope_validation_422():
    """Verify schema validation failures return field-level details in the standard error envelope."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # POST with invalid JSON payload
        resp = await ac.post("/api/v1/report-archive", json={"invalid": "payload"})
        assert resp.status_code == 422
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "message" in data["error"]
        assert "request_id" in data["error"]
        assert len(data["error"]["details"]) > 0


@pytest.mark.asyncio
async def test_m15_01_platform_health_and_catalog():
    """Verify core platform endpoints: /api/v1/health and /api/v1/catalog."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Health
        resp_health = await ac.get("/api/v1/health")
        assert resp_health.status_code == 200
        data_health = resp_health.json()
        assert "data" in data_health
        assert "meta" in data_health
        assert data_health["data"]["status"] == "healthy"
        assert data_health["meta"]["version"] == "v1"

        # Catalog
        resp_cat = await ac.get("/api/v1/catalog")
        assert resp_cat.status_code == 200
        data_cat = resp_cat.json()
        assert "data" in data_cat
        assert "resource_groups" in data_cat["data"]
        assert "portfolio" in data_cat["data"]["resource_groups"]
        assert "risk" in data_cat["data"]["resource_groups"]
        assert "archive" in data_cat["data"]["resource_groups"]


@pytest.mark.asyncio
async def test_m15_01_openapi_documentation_accessible():
    """Verify OpenAPI JSON and documentation endpoints are available."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp_openapi = await ac.get("/openapi.json")
        assert resp_openapi.status_code == 200
        schema = resp_openapi.json()
        assert "openapi" in schema
        assert "info" in schema
        assert schema["info"]["version"] == "1.0.0"
        assert "/api/v1/health" in schema["paths"]
        assert "/api/v1/catalog" in schema["paths"]
