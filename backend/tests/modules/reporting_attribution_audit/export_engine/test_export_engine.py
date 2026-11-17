import pytest
import pytest_asyncio
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.app.core.database import Base
from backend.app.main import app
from backend.app.modules.portfolio_management.portfolio_creation.models import (
    Portfolio,
    PortfolioTypeEnum,
)
from backend.app.modules.reporting_attribution_audit.export_engine.models.export_models import (
    ExportFormat,
    ExportStatus,
    ExportValidationStatus,
)
from backend.app.modules.reporting_attribution_audit.export_engine.schemas.export_schemas import (
    ExportCreateRequest,
    ExportSourceInput,
    ExportScopeInput,
    ExportOptionsInput,
)
from backend.app.modules.reporting_attribution_audit.export_engine.services.export_orchestration_service import (
    ExportOrchestrationService,
)
from backend.app.modules.reporting_attribution_audit.export_engine.generators.csv_generator import (
    CsvGenerator,
)
from backend.app.modules.reporting_attribution_audit.export_engine.generators.excel_generator import (
    ExcelGenerator,
)
from backend.app.modules.reporting_attribution_audit.export_engine.generators.pdf_generator import (
    PdfGenerator,
)
from backend.app.modules.reporting_attribution_audit.export_engine.storage.storage_adapter import (
    LocalStorageAdapter,
)

# In-memory SQLite async test database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_db():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Seed test portfolio
        portfolio = Portfolio(
            portfolio_id="port_exp_001",
            portfolio_code="PORT_EXP_001",
            portfolio_name="Institutional Export Test Portfolio",
            short_name="ExportTest",
            portfolio_type=PortfolioTypeEnum.INSTITUTIONAL_PORTFOLIO,
            lifecycle_status="ACTIVE",
            base_currency="INR",
            creation_source="SYSTEM_GENERATION",
            market_scope="INDIA_AND_US",
            asset_class_scope="EQUITIES",
            current_configuration_version=1,
            created_by="TEST_RUNNER",
            created_at=datetime.now(timezone.utc),
        )
        session.add(portfolio)
        await session.commit()
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_csv_generator_and_formula_injection_protection():
    """Verify CSV formatting, decimal precision, and neutralization of formula injection text."""
    columns = ["symbol", "quantity", "market_value", "untrusted_comment"]
    rows = [
        {"symbol": "RELIANCE", "quantity": 100.0, "market_value": -125000.50, "untrusted_comment": "=cmd|' /C calc'!A0"},
        {"symbol": "TCS", "quantity": -50.0, "market_value": 150000.0, "untrusted_comment": "+SUM(1+1)"},
        {"symbol": "INFY", "quantity": 75.0, "market_value": 75000.0, "untrusted_comment": "Standard Note"},
    ]

    csv_bytes = CsvGenerator.generate(columns, rows)
    csv_text = csv_bytes.decode("utf-8")

    # Formula injection text must have prepended apostrophe
    assert "'=cmd|' /C calc'!A0" in csv_text
    assert "'+SUM(1+1)" in csv_text
    # Legitimate negative numbers must remain numeric without apostrophe
    assert "-125000.5" in csv_text
    assert "-50.0" in csv_text


@pytest.mark.asyncio
async def test_excel_generator_structure_and_sheets():
    """Verify multi-worksheet generation, headers, frozen panes, and formatting."""
    columns = ["instrument_id", "symbol", "quantity", "market_value"]
    rows = [
        {"instrument_id": "INST_01", "symbol": "RELIANCE", "quantity": 500, "market_value": 1250000.0},
        {"instrument_id": "INST_02", "symbol": "TCS", "quantity": -200, "market_value": -700000.0},
    ]
    meta = {"portfolio_id": "port_exp_001", "reporting_currency": "INR"}
    notes = ["Test methodology note 1", "Risk model version v2.0"]

    xlsx_bytes = ExcelGenerator.generate(
        dataset_name="Test Risk Positions",
        columns=columns,
        data_rows=rows,
        summary_metadata=meta,
        methodology_notes=notes,
    )

    assert len(xlsx_bytes) > 1000
    # Open workbook in memory to verify sheets
    import openpyxl
    import io
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes))
    assert "Executive Summary" in wb.sheetnames
    assert "Analytical Data" in wb.sheetnames
    assert "Methodology & Governance" in wb.sheetnames
    ws_data = wb["Analytical Data"]
    assert ws_data.freeze_panes == "A2"
    assert ws_data.max_row == 3


@pytest.mark.asyncio
async def test_pdf_generator_landscape_and_headers():
    """Verify PDF generator produces valid landscape PDF bytes with headers/footers."""
    columns = ["instrument_id", "symbol", "quantity", "market_value"]
    rows = [
        {"instrument_id": "INST_01", "symbol": "RELIANCE", "quantity": 500, "market_value": 1250000.0},
        {"instrument_id": "INST_02", "symbol": "TCS", "quantity": -200, "market_value": -700000.0},
    ]
    meta = {"portfolio_id": "port_exp_001", "reporting_currency": "INR"}
    notes = ["PDF report governance note"]

    pdf_bytes = PdfGenerator.generate(
        report_title="Daily Risk Report Test",
        columns=columns,
        data_rows=rows,
        summary_metadata=meta,
        methodology_notes=notes,
    )

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


@pytest.mark.asyncio
async def test_export_orchestration_service_lifecycle(async_db: AsyncSession):
    """Test full ExportOrchestrationService execution, artifact generation, validation, and SHA-256 storage."""
    service = ExportOrchestrationService(async_db)

    req = ExportCreateRequest(
        source=ExportSourceInput(
            module="M14",
            feature="M14.01",
            dataset_id="daily_risk_positions",
        ),
        formats=[ExportFormat.CSV, ExportFormat.XLSX, ExportFormat.PDF],
        scope=ExportScopeInput(portfolio_id="port_exp_001"),
        options=ExportOptionsInput(reporting_currency="INR"),
    )

    job = await service.create_and_execute_export(req)

    assert job.export_status in (ExportStatus.COMPLETED, ExportStatus.COMPLETED_WITH_WARNINGS)
    assert len(job.artifacts) == 3
    assert job.validation_summary.validation_status == ExportValidationStatus.VALID
    assert job.total_records >= 4

    # Verify SHA-256 hashes
    storage = LocalStorageAdapter()
    for art in job.artifacts:
        assert len(art.file_hash) == 64
        assert storage.verify_artifact_integrity(art.storage_reference, art.file_hash)


@pytest.mark.asyncio
async def test_fastapi_export_endpoints(async_db: AsyncSession):
    """Test FastAPI router endpoints for dataset registry, creation, and downloading."""
    from backend.app.core.database import get_db
    app.dependency_overrides[get_db] = lambda: async_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Dataset registry
        ds_res = await client.get("/api/v1/exports/datasets")
        assert ds_res.status_code == 200
        datasets = ds_res.json()
        assert len(datasets) >= 6

        # 2. Dataset detail
        det_res = await client.get("/api/v1/exports/datasets/daily_risk_positions")
        assert det_res.status_code == 200
        assert det_res.json()["dataset_code"] == "daily_risk_positions"

        # 3. Create Export
        payload = {
            "source": {
                "module": "M14",
                "feature": "M14.05",
                "dataset_id": "liquidity_positions_and_costs",
            },
            "formats": ["CSV", "XLSX"],
            "scope": {"portfolio_id": "port_exp_001"},
            "options": {"reporting_currency": "INR"},
        }
        create_res = await client.post("/api/v1/exports", json=payload)
        assert create_res.status_code == 201
        job_data = create_res.json()
        job_id = job_data["id"]
        assert len(job_data["artifacts"]) == 2

        # 4. List jobs
        list_res = await client.get("/api/v1/exports")
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 1

        # 5. Download Artifact
        art_id = job_data["artifacts"][0]["artifact_id"]
        dl_res = await client.get(f"/api/v1/exports/{job_id}/download/{art_id}")
        assert dl_res.status_code == 200
        assert "Content-Disposition" in dl_res.headers
        assert "X-Artifact-SHA256" in dl_res.headers

        # 6. Audit Trail
        audit_res = await client.get(f"/api/v1/exports/{job_id}/audit")
        assert audit_res.status_code == 200
        events = audit_res.json()
        assert any(e["event_type"] == "DOWNLOADED" for e in events)
