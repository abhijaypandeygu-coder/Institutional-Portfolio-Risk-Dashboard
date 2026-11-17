import pytest
import pytest_asyncio
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.modules.reporting_attribution_audit.audit_trail.models.audit_models import (
    ActorType,
    EventCategory,
    EventSeverity,
    EventOutcome,
    IntegrityVerificationStatus,
    AuditEvent,
)
from backend.app.modules.reporting_attribution_audit.audit_trail.schemas.audit_schemas import (
    AuditEventCreateRequest,
    AuditActorInput,
    ConfigurationChangeInput,
    ApprovalDetailsInput,
)
from backend.app.modules.reporting_attribution_audit.audit_trail.services.audit_trail_service import (
    AuditTrailService,
)
from backend.app.modules.reporting_attribution_audit.audit_trail.integrity.hasher import (
    CanonicalEventSerializer,
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
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_canonical_serializer_and_hash_calculation():
    """Verify deterministic canonical serialization and SHA-256 hash chaining."""
    event1 = {
        "event_id": "EVT-TEST-001",
        "event_type": "RISK_LIMIT_CHANGED",
        "event_category": "CONFIGURATION_CHANGE",
        "severity": "WARNING",
        "actor_type": "USER",
        "actor_id": "risk_officer_01",
        "source_module": "M11",
        "target_type": "RISK_LIMIT",
        "target_id": "LIMIT_MAX_VAR",
        "action": "UPDATE",
        "outcome": "SUCCESS",
        "occurred_at": "2026-11-17T10:00:00Z",
        "chain_sequence": 1,
        "payload": {"max_var": 450000.0},
    }
    prev_hash = "GENESIS_BLOCK_00000000000000000000000000000000000000000000000000000000"
    can_str1 = CanonicalEventSerializer.canonicalize(event1)
    hash1 = CanonicalEventSerializer.compute_event_hash(can_str1, prev_hash)

    assert len(hash1) == 64
    assert hash1 == CanonicalEventSerializer.compute_event_hash(can_str1, prev_hash)


@pytest.mark.asyncio
async def test_audit_event_ingestion_and_chaining(async_db: AsyncSession):
    """Test append-only event recording, automatic sequence increment, and hash chaining."""
    service = AuditTrailService(async_db)

    # 1. First event
    req1 = AuditEventCreateRequest(
        event_type="PORTFOLIO_CREATED",
        event_category=EventCategory.USER_ACTION,
        severity=EventSeverity.INFO,
        actor=AuditActorInput(type=ActorType.USER, id="pm_alpha", role="PORTFOLIO_MANAGER"),
        source_module="M05",
        target_type="PORTFOLIO",
        target_id="PORT_001",
        action="CREATE",
        reason="New quantitative long/short equity portfolio",
        correlation_id="WF_PORT_INIT",
    )
    e1 = await service.record_audit_event(req1)
    assert e1.chain_sequence == 1
    assert e1.previous_hash.startswith("GENESIS_BLOCK")
    assert len(e1.integrity_hash) == 64

    # 2. Second event chained to first
    req2 = AuditEventCreateRequest(
        event_type="RISK_LIMIT_CHANGED",
        event_category=EventCategory.CONFIGURATION_CHANGE,
        severity=EventSeverity.WARNING,
        actor=AuditActorInput(type=ActorType.USER, id="cro_user", role="CHIEF_RISK_OFFICER"),
        source_module="M11",
        target_type="RISK_LIMIT",
        target_id="POL_VAR_LIMIT",
        action="UPDATE",
        reason="Tightened gross exposure mandate",
        correlation_id="WF_PORT_INIT",
        configuration_change=ConfigurationChangeInput(
            configuration_id="POL_VAR_LIMIT",
            configuration_type="RISK_LIMIT",
            owning_module="M11",
            previous_version=1,
            new_version=2,
            effective_at=datetime.now(timezone.utc),
            changed_fields=["max_gross_exposure"],
            old_values_redacted={"max_gross_exposure": 150.0},
            new_values_redacted={"max_gross_exposure": 125.0},
        ),
    )
    e2 = await service.record_audit_event(req2)
    assert e2.chain_sequence == 2
    assert e2.previous_hash == e1.integrity_hash
    assert e2.configuration_change is not None
    assert e2.configuration_change.new_version == 2


@pytest.mark.asyncio
async def test_audit_chain_integrity_verification(async_db: AsyncSession):
    """Test cryptographic SHA-256 integrity verification across the chain."""
    service = AuditTrailService(async_db)

    # Seed 3 chained events
    for i in range(1, 4):
        req = AuditEventCreateRequest(
            event_type=f"JOB_EXECUTED_{i}",
            event_category=EventCategory.SYSTEM_EVENT,
            actor=AuditActorInput(type=ActorType.SYSTEM, id="SCHEDULER"),
            source_module="M02",
            action="EXECUTE",
            correlation_id="JOB_RUN_SERIES",
        )
        await service.record_audit_event(req)

    # Verify chain
    result = await service.verify_chain_integrity("GLOBAL_CHAIN")
    assert result.verification_status == IntegrityVerificationStatus.VERIFIED
    assert result.events_checked >= 3
    assert result.mismatch_count == 0
    assert result.missing_sequence_count == 0


@pytest.mark.asyncio
async def test_event_timeline_and_correlation(async_db: AsyncSession):
    """Test cross-module event correlation timeline retrieval."""
    service = AuditTrailService(async_db)

    corr_id = "INCIDENT_FEED_DROP_001"
    # Event 1: Feed drop
    await service.record_audit_event(
        AuditEventCreateRequest(
            event_type="FEED_DISCONNECTED",
            event_category=EventCategory.SYSTEM_EVENT,
            severity=EventSeverity.CRITICAL,
            actor=AuditActorInput(type=ActorType.SERVICE, id="FEED_HANDLER_NSE"),
            source_module="M02",
            action="FAILOVER_TRIGGERED",
            correlation_id=corr_id,
        )
    )
    # Event 2: Limit Check Warning
    await service.record_audit_event(
        AuditEventCreateRequest(
            event_type="PRE_TRADE_CHECK_HALTED",
            event_category=EventCategory.CONTROL_DECISION,
            severity=EventSeverity.WARNING,
            actor=AuditActorInput(type=ActorType.SYSTEM, id="M11_ENGINE"),
            source_module="M11",
            action="REJECT",
            reason="Feed stale during pre-trade evaluation",
            correlation_id=corr_id,
        )
    )

    timeline = await service.get_timeline(corr_id)
    assert len(timeline) == 2
    assert timeline[0].event_type == "FEED_DISCONNECTED"
    assert timeline[1].event_type == "PRE_TRADE_CHECK_HALTED"


@pytest.mark.asyncio
async def test_fastapi_audit_endpoints(async_db: AsyncSession):
    """Test FastAPI router endpoints for audit event recording, search, timeline, and integrity verification."""
    app.dependency_overrides[get_db] = lambda: async_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Ingest event
        payload = {
            "event_type": "OVERRIDE_APPROVED",
            "event_category": "APPROVAL",
            "severity": "WARNING",
            "actor": {"type": "USER", "id": "head_of_risk", "role": "EXECUTIVE"},
            "source_module": "M11",
            "action": "APPROVE",
            "reason": "Emergency volatility buffer authorized",
            "correlation_id": "WF_OVERRIDE_099",
            "approval_details": {
                "approval_id": "APP_099",
                "target_type": "LIMIT_OVERRIDE",
                "target_id": "LIM_VAR_99",
                "requesting_actor_id": "trader_01",
                "approving_actor_id": "head_of_risk",
                "decision": "APPROVED",
                "reason": "Temporary buffer",
            },
        }
        res = await client.post("/api/v1/audit/events", json=payload)
        assert res.status_code == 201
        event_data = res.json()
        assert event_data["event_type"] == "OVERRIDE_APPROVED"

        # 2. Search events
        search_res = await client.get("/api/v1/audit/events?source_module=M11")
        assert search_res.status_code == 200
        assert search_res.json()["total"] >= 1

        # 3. Timeline
        tl_res = await client.get("/api/v1/audit/timeline?correlation_id=WF_OVERRIDE_099")
        assert tl_res.status_code == 200
        assert len(tl_res.json()) >= 1

        # 4. Verify integrity endpoint
        verify_res = await client.post("/api/v1/audit/integrity/verify")
        assert verify_res.status_code == 200
        assert verify_res.json()["verification_status"] == "VERIFIED"

        # 5. Checkpoints
        cp_res = await client.get("/api/v1/audit/integrity/checkpoints")
        assert cp_res.status_code == 200
        assert len(cp_res.json()) >= 1

        # 6. Retention policies
        pol_res = await client.get("/api/v1/audit/retention/policies")
        assert pol_res.status_code == 200
        assert len(pol_res.json()) >= 3
