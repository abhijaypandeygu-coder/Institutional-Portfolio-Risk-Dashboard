"""
Integration Tests for Testing Infrastructure REST APIs and Orchestration.
Validates profile listing, run triggering, regression checking, and quality gate evaluation.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_test_profiles_api():
    """Validates that all approved execution profiles are returned with safe parameters."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/testing/profiles")
        assert resp.status_code == 200
        profiles = resp.json()
        assert len(profiles) >= 5
        profile_ids = [p["profile_id"] for p in profiles]
        assert "unit" in profile_ids
        assert "integration" in profile_ids
        assert "regression" in profile_ids
        assert "performance" in profile_ids


@pytest.mark.asyncio
@pytest.mark.integration
async def test_run_regression_verification_api():
    """Validates live regression comparison endpoint against approved baselines."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/testing/regression/comparisons")
        assert resp.status_code == 200
        data = resp.json()
        assert data["baseline_id"] == "BASELINE_INSTITUTIONAL_V1"
        assert data["total_checks"] > 0
        assert data["passed_checks"] == data["total_checks"]
        assert data["failed_checks"] == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_evaluate_quality_gates_api():
    """Validates institutional quality gate evaluation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/testing/quality-gates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gate_name"] == "Institutional Release Gate"
        assert data["overall_status"] in ["PASSED", "WARNING", "FAILED"]
        assert len(data["criteria_evaluated"]) >= 3


@pytest.mark.asyncio
@pytest.mark.integration
async def test_coverage_overview_api():
    """Validates coverage reporting endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/testing/coverage")
        assert resp.status_code == 200
        cov = resp.json()
        assert cov["total_coverage"] >= 75.0
        assert "M05_portfolio_management" in cov["module_coverage"]
