import base64
import os
import shutil
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.modules.reporting_attribution_audit.report_archive.models.archive_models import (
    ReportArchive,
    ReportArchiveType,
    ArchiveStatus,
    GenerationReason,
    ArtifactFormat,
    IntegrityStatus,
    LegalHoldStatus,
)
from backend.app.modules.reporting_attribution_audit.report_archive.schemas.archive_schemas import (
    ArchiveSubmissionRequest,
    ProvenanceInput,
    ModelVersionInput,
    DataVersionInput,
    ConfigVersionInput,
)
from backend.app.modules.reporting_attribution_audit.report_archive.services.report_archive_service import (
    ReportArchiveService,
)
from backend.app.modules.reporting_attribution_audit.report_archive.storage.artifact_storage_service import (
    ReportArtifactStorageService,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_STORAGE_DIR = "artifacts/test_reports"


@pytest.fixture(autouse=True)
def cleanup_test_storage():
    """Cleans up temporary filesystem test directory after execution."""
    os.makedirs(TEST_STORAGE_DIR, exist_ok=True)
    yield
    if os.path.exists(TEST_STORAGE_DIR):
        try:
            shutil.rmtree(TEST_STORAGE_DIR)
        except OSError:
            pass


@pytest.fixture
async def test_session():
    """Sets up an in-memory SQLite async database engine and tables."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def test_storage():
    return ReportArtifactStorageService(base_storage_dir=TEST_STORAGE_DIR)


def build_sample_submission(
    portfolio_id: str = "PORT-001",
    report_type: ReportArchiveType = ReportArchiveType.DAILY_RISK,
    period_start: datetime = None,
    period_end: datetime = None,
    run_id: str = "RUN-1001",
    supersedes_id: str = None,
) -> ArchiveSubmissionRequest:
    now = datetime.now(timezone.utc)
    p_start = period_start or datetime(2026, 11, 16, 0, 0, tzinfo=timezone.utc)
    p_end = period_end or datetime(2026, 11, 16, 23, 59, tzinfo=timezone.utc)

    dummy_content = b"PDF-1.4 Mock Report Content for Institutional Portfolio Risk Assessment."
    b64_content = base64.b64encode(dummy_content).decode("utf-8")

    return ArchiveSubmissionRequest(
        report_id=f"RPT-{run_id}",
        report_run_id=run_id,
        portfolio_id=portfolio_id,
        portfolio_name_snapshot="Apex Alpha Fund",
        report_type=report_type,
        report_title_snapshot="Institutional Daily Risk Assessment",
        report_definition_id="DEF-DAILY-RISK-V1",
        report_definition_version="1.0.0",
        period_start=p_start,
        period_end=p_end,
        valuation_timestamp=now,
        generated_at=now,
        generation_reason=GenerationReason.INITIAL if not supersedes_id else GenerationReason.DATA_CORRECTION,
        supersedes_version_id=supersedes_id,
        summary_nav=Decimal("15000000.50"),
        summary_var_value=Decimal("450000.00"),
        summary_es_value=Decimal("620000.00"),
        currency="USD",
        artifact_filename=f"{run_id}_report.pdf",
        artifact_format=ArtifactFormat.PDF,
        mime_type="application/pdf",
        content_base64=b64_content,
        provenance=ProvenanceInput(
            application_version="1.0.0",
            code_commit="94de82b",
            environment_id="production-local",
            execution_started_at=now - timedelta(seconds=12),
            execution_completed_at=now,
            trigger_source="SCHEDULED_RUN",
            requesting_actor_id="PORTFOLIO_MANAGER",
            report_parameters={"confidence_level": 0.99, "horizon_days": 1},
        ),
        models=[
            ModelVersionInput(
                model_id="MOD-GARCH-01",
                model_name="GARCH_VOLATILITY",
                model_version="1.2.0",
                implementation_version="2.1.0",
                parameter_set_id="PARAM-2026Q4",
            )
        ],
        data_sources=[
            DataVersionInput(
                source_type="MARKET_DATA",
                source_id="FEED-ALPHA-VANTAGE",
                snapshot_id="SNAP-20261116-EOD",
                data_as_of=now,
                quality_status="VERIFIED",
            )
        ],
        configurations=[
            ConfigVersionInput(
                configuration_id="CFG-RISK-01",
                configuration_version="1.0",
                configuration_type="RISK_METHODOLOGY",
                configuration_snapshot={"var_method": "HISTORICAL_SIMULATION", "lookback": 252},
            )
        ],
    )


@pytest.mark.asyncio
async def test_artifact_storage_safe_write_and_integrity(test_storage):
    """Test two-phase safe writing, SHA-256 computation, and tamper verification."""
    storage_key = test_storage.generate_storage_key("PORT-001", "ARC-TEST-01", "pdf")
    content = b"Binary sample report data for archival verification"

    stored_key, calculated_hash, file_size = test_storage.write_artifact_safe(storage_key, content)
    assert stored_key == storage_key
    assert file_size == len(content)

    # Read back and verify
    read_bytes = test_storage.read_artifact(stored_key)
    assert read_bytes == content

    # Verify integrity passes
    is_valid, h = test_storage.verify_integrity(stored_key, calculated_hash)
    assert is_valid is True
    assert h == calculated_hash

    # Verify tampering detection
    is_tampered_valid, _ = test_storage.verify_integrity(stored_key, "0000000000000000000000000000000000000000000000000000000000000000")
    assert is_tampered_valid is False


@pytest.mark.asyncio
async def test_report_versioning_and_provenance(test_session, test_storage):
    """Test monotonic version assignment (V1 -> V2) and supersession on regeneration."""
    service = ReportArchiveService(test_session, test_storage)

    # 1. Ingest V1
    req_v1 = build_sample_submission(run_id="RUN-1001")
    detail_v1 = await service.submit_report_for_archive(req_v1)
    assert detail_v1.version_number == 1
    assert detail_v1.status == ArchiveStatus.AVAILABLE
    assert detail_v1.provenance is not None
    assert len(detail_v1.provenance.models) == 1
    assert detail_v1.provenance.models[0].model_name == "GARCH_VOLATILITY"

    # 2. Ingest V2 (Superseding V1)
    req_v2 = build_sample_submission(run_id="RUN-1002", supersedes_id=detail_v1.archive_id)
    detail_v2 = await service.submit_report_for_archive(req_v2)
    assert detail_v2.version_number == 2
    assert detail_v2.status == ArchiveStatus.AVAILABLE
    assert detail_v2.supersedes_version_id == detail_v1.archive_id

    # Refresh V1 from database: should now be SUPERSEDED
    v1_reloaded = await service.get_archive_by_id(detail_v1.archive_id)
    assert v1_reloaded.status == ArchiveStatus.SUPERSEDED

    # 3. Retrieve Version History
    history = await service.get_version_history(detail_v2.archive_id)
    assert len(history) == 2
    assert [h.version_number for h in history] == [2, 1]


@pytest.mark.asyncio
async def test_version_comparison(test_session, test_storage):
    """Test structured comparison of financial summary metrics and model changes between archive versions."""
    service = ReportArchiveService(test_session, test_storage)

    req_v1 = build_sample_submission(run_id="RUN-1001")
    v1 = await service.submit_report_for_archive(req_v1)

    req_v2 = build_sample_submission(run_id="RUN-1002")
    req_v2.summary_nav = Decimal("15500000.50") # +500,000 NAV diff
    req_v2.models[0].model_version = "1.3.0" # Model upgrade
    v2 = await service.submit_report_for_archive(req_v2)

    comp = await service.compare_archive_versions(v1.archive_id, v2.archive_id)
    assert comp.nav_diff == Decimal("500000.00")
    assert any("upgraded" in c for c in comp.model_changes)


@pytest.mark.asyncio
async def test_legal_holds_and_retention_dry_run(test_session, test_storage):
    """Test compliance legal holds and non-mutating retention policy dry-run."""
    service = ReportArchiveService(test_session, test_storage)

    req = build_sample_submission(run_id="RUN-1001")
    v1 = await service.submit_report_for_archive(req)

    # Place under legal hold
    hold = await service.apply_legal_hold(v1.archive_id, "SEC regulatory inquiry 2026", "COMPLIANCE_HEAD")
    assert hold.status == LegalHoldStatus.ACTIVE

    v1_reloaded = await service.get_archive_by_id(v1.archive_id)
    assert v1_reloaded.has_active_legal_hold is True

    # Retention dry-run evaluation
    eval_resp = await service.evaluate_retention_dry_run()
    assert eval_resp.total_evaluated == 1
    assert eval_resp.held_count == 1
    assert eval_resp.items[0].has_legal_hold is True
    assert eval_resp.items[0].recommended_action == "PROTECTED_BY_LEGAL_HOLD"

    # Release legal hold
    await service.release_legal_hold(hold.hold_id, "Inquiry resolved", "COMPLIANCE_HEAD")
    v1_after_release = await service.get_archive_by_id(v1.archive_id)
    assert v1_after_release.has_active_legal_hold is False


@pytest.mark.asyncio
async def test_fastapi_report_archive_endpoints(test_session):
    """Test FastAPI endpoint routing: submit, search, metadata, and download."""
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        req = build_sample_submission(run_id="RUN-HTTP-01")
        post_resp = await ac.post("/api/v1/report-archive", json=req.model_dump(mode="json"))
        assert post_resp.status_code == 201
        data = post_resp.json()
        archive_id = data["archive_id"]
        assert data["version_number"] == 1
        assert data["portfolio_id"] == "PORT-001"

        # Search
        search_resp = await ac.get("/api/v1/report-archive?portfolio_id=PORT-001")
        assert search_resp.status_code == 200
        search_data = search_resp.json()
        assert search_data["total"] >= 1

        # Metadata
        meta_resp = await ac.get(f"/api/v1/report-archive/{archive_id}")
        assert meta_resp.status_code == 200
        assert meta_resp.json()["archive_id"] == archive_id

        # Download
        down_resp = await ac.get(f"/api/v1/report-archive/{archive_id}/download")
        assert down_resp.status_code == 200
        assert b"PDF-1.4 Mock Report Content" in down_resp.content

        # Verify integrity
        integ_resp = await ac.post(f"/api/v1/report-archive/{archive_id}/integrity")
        assert integ_resp.status_code == 200
        assert integ_resp.json()["integrity_status"] == "VERIFIED"

    app.dependency_overrides.clear()
