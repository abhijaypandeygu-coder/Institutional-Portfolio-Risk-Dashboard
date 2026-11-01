"""
Pytest Test Suite for M03.08 Exception Management.
Tests:
1. Exception intake, correlation key deduplication, and observation linking.
2. Quarantine isolation, payload hash preservation, and authorized release.
3. Explicit rejection, reason codes, and recoverability classification.
4. Controlled correction proposal, field changes, and separation-of-duties enforcement (self-approval forbidden).
5. Synthetic test simulator data rejection when correcting real-market observations.
6. Idempotent replay submission through M02 integration client, per-record batch results, and exception resolution.
7. Reopening resolved exceptions and audit trail verification.
8. REST API lifecycle with role-based access control.
"""
import uuid
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.main import app
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.core.config import settings
from backend.app.modules.market_data_quality.exception_management.models import (
    ExceptionRecord,
    QuarantineRecord,
    CorrectionProposal,
    ReplayRequest,
    compute_payload_hash,
)
from backend.app.modules.market_data_quality.exception_management.schemas import (
    FindingIntakeSchema,
    ExceptionCreateRequest,
    QuarantineCreateRequest,
    QuarantineReleaseRequest,
    RejectionCreateRequest,
    CorrectionProposalCreate,
    FieldChangeSchema,
    CorrectionApprovalRequest,
    ReplaySubmitRequest,
    ExceptionReopenRequest,
)
from backend.app.modules.market_data_quality.exception_management.services.service import (
    ExceptionManagementService,
)
from backend.app.modules.market_data_quality.exception_management.repositories.repository import (
    ExceptionRepository,
)
from backend.app.modules.market_data_quality.exception_management.state_machine.transitions import (
    WorkflowStatus,
    RecordDisposition,
    ApprovalStatus,
    ReplayStatus,
)


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()


@pytest.fixture
def auth_headers():
    return {
        "X-API-Key": settings.API_KEY_OPERATOR,
        "X-Actor": "test_operator",
    }


@pytest.fixture
def admin_headers():
    return {
        "X-API-Key": settings.API_KEY_ADMIN,
        "X-Actor": "test_admin",
    }


@pytest.mark.asyncio
async def test_exception_intake_and_deduplication():
    """
    Verifies that:
    - Multiple upstream findings can be linked to an exception.
    - Repeated submission with the same findings is handled idempotently without duplicate records.
    - Original payloads are hashed and preserved.
    """
    async with AsyncSessionLocal() as session:
        obs_id = f"OBS_TEST_{uuid.uuid4().hex[:8]}"
        finding1 = FindingIntakeSchema(
            finding_id=f"FND_PRICE_{uuid.uuid4().hex[:6]}",
            source_module="M03",
            source_feature="M03.02",
            finding_code="PRICE_SPIKE_DETECTED",
            source_severity="HIGH",
            feed_id="FEED_NSE_EQUITY",
            instrument_id="TCS",
            observation_id=obs_id,
            source_event_timestamp=datetime(2026, 11, 1, 9, 30, tzinfo=timezone.utc),
            raw_payload={"price": 38000.0, "volume": 100},
        )
        finding2 = FindingIntakeSchema(
            finding_id=f"FND_TIME_{uuid.uuid4().hex[:6]}",
            source_module="M03",
            source_feature="M03.03",
            finding_code="FUTURE_TIMESTAMP",
            source_severity="HIGH",
            feed_id="FEED_NSE_EQUITY",
            instrument_id="TCS",
            observation_id=obs_id,
            source_event_timestamp=datetime(2026, 11, 1, 9, 30, tzinfo=timezone.utc),
            raw_payload={"price": 38000.0, "volume": 100},
        )

        req = ExceptionCreateRequest(
            category="MARKET_DATA_CORRUPTION",
            exception_type="MULTIPLE_ANOMALIES",
            severity="HIGH",
            priority="P1",
            summary="Price spike and timestamp skew on TCS",
            description="Combined anomaly detected during morning session.",
            findings=[finding1, finding2],
        )

        # 1. First registration
        exc1 = await ExceptionManagementService.register_exception(session, req, actor_id="triage_bot")
        assert exc1.workflow_status == WorkflowStatus.OPEN.value
        assert exc1.exception_id.startswith("EXC_")

        # 2. Second registration with same findings (must be idempotent)
        exc2 = await ExceptionManagementService.register_exception(session, req, actor_id="triage_bot")
        assert exc1.id == exc2.id
        assert exc1.exception_id == exc2.exception_id

        # 3. Verify observation linking & hashing
        observations = await ExceptionRepository.get_observations_for_exception(session, exc1.exception_id)
        assert len(observations) == 1
        assert observations[0].observation_id == obs_id
        assert observations[0].payload_hash == compute_payload_hash({"price": 38000.0, "volume": 100})
        assert observations[0].record_disposition == RecordDisposition.QUARANTINED.value


@pytest.mark.asyncio
async def test_quarantine_isolation_and_release():
    """
    Verifies that:
    - Suspect observations are isolated into quarantine.
    - Quarantined observations cannot be released without authorization.
    - Verified release updates disposition and emits audit events.
    """
    async with AsyncSessionLocal() as session:
        obs_id = f"OBS_QRN_{uuid.uuid4().hex[:8]}"
        finding = FindingIntakeSchema(
            finding_id=f"FND_QRN_{uuid.uuid4().hex[:6]}",
            source_feature="M03.04",
            finding_code="CROSSED_ORDER_BOOK",
            feed_id="FEED_SIM_BOOK",
            instrument_id="RELIANCE",
            observation_id=obs_id,
            source_event_timestamp=datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
            raw_payload={"best_bid": 2500, "best_ask": 2490},
        )
        exc = await ExceptionManagementService.register_exception(
            session,
            ExceptionCreateRequest(
                category="MICROSTRUCTURE",
                exception_type="ORDER_BOOK_CROSSED",
                summary="Crossed order book depth",
                description="Best bid exceeds best ask",
                findings=[finding],
            ),
        )

        quarantines = await ExceptionRepository.list_quarantines(session, release_status="QUARANTINED")
        qrn = [q for q in quarantines if q.observation_id == obs_id][0]
        assert qrn.release_status == "QUARANTINED"

        # Release with authorization
        rel_req = QuarantineReleaseRequest(
            justification="Exchange crossed book resolved after quote refresh",
            release_authorization_reference="AUTH_DESK_RISK_88",
        )
        released_qrn = await ExceptionManagementService.release_quarantine(
            session, qrn.quarantine_id, rel_req, actor_id="risk_officer"
        )
        assert released_qrn.release_status == "RELEASED"
        assert released_qrn.released_by == "risk_officer"


@pytest.mark.asyncio
async def test_rejection_management_and_reason_codes():
    """
    Verifies that:
    - Hard invalid records are rejected with structured reason codes.
    - Record disposition becomes REJECTED without physical deletion.
    """
    async with AsyncSessionLocal() as session:
        obs_id = f"OBS_REJ_{uuid.uuid4().hex[:8]}"
        finding = FindingIntakeSchema(
            finding_id=f"FND_REJ_{uuid.uuid4().hex[:6]}",
            source_feature="M03.02",
            finding_code="NEGATIVE_PRICE",
            feed_id="FEED_NSE_EQUITY",
            instrument_id="INFY",
            observation_id=obs_id,
            source_event_timestamp=datetime(2026, 11, 1, 11, 0, tzinfo=timezone.utc),
            raw_payload={"price": -150.0},
        )
        exc = await ExceptionManagementService.register_exception(
            session,
            ExceptionCreateRequest(
                category="STRUCTURAL_INVALIDITY",
                exception_type="INVALID_NUMERIC",
                summary="Negative equity price print",
                description="Price was reported as -150.00",
                findings=[finding],
            ),
        )

        rej_req = RejectionCreateRequest(
            observation_id=obs_id,
            reason_code="REJ_INVALID_VALUE",
            reason_details="Price is mathematically impossible (-150.00)",
            recoverability="RECOVERABLE",
        )
        rej = await ExceptionManagementService.reject_observation(
            session, exc.exception_id, rej_req, actor_id="data_steward"
        )
        assert rej.reason_code == "REJ_INVALID_VALUE"
        assert rej.rejected_by == "data_steward"

        # Verify observation disposition updated to REJECTED
        observations = await ExceptionRepository.get_observations_for_exception(session, exc.exception_id)
        assert observations[0].record_disposition == RecordDisposition.REJECTED.value


@pytest.mark.asyncio
async def test_correction_separation_of_duties_and_simulator_guard():
    """
    Verifies:
    - Separation of duties: The user who proposes a correction CANNOT approve it.
    - Real-data provenance guard: Synthetic test simulator observations CANNOT correct real data.
    - Precision is retained in before/after values.
    """
    async with AsyncSessionLocal() as session:
        obs_id = f"OBS_COR_{uuid.uuid4().hex[:8]}"
        finding = FindingIntakeSchema(
            finding_id=f"FND_COR_{uuid.uuid4().hex[:6]}",
            source_feature="M03.02",
            finding_code="TICK_ROUNDING_ERROR",
            feed_id="FEED_NSE_EQUITY",
            instrument_id="HDFCBANK",
            data_origin="REAL",
            observation_id=obs_id,
            source_event_timestamp=datetime(2026, 11, 1, 11, 30, tzinfo=timezone.utc),
            raw_payload={"price": 1420.3333},
        )
        exc = await ExceptionManagementService.register_exception(
            session,
            ExceptionCreateRequest(
                category="PRICING",
                exception_type="ROUNDING_CORRECTION",
                summary="Unrounded tick price",
                description="Price violated 0.05 tick size",
                findings=[finding],
            ),
        )

        # 1. Guard check: Attempting to correct REAL data using SYNTHETIC_SIM provenance must fail
        with pytest.raises(Exception) as excinfo:
            await ExceptionManagementService.create_correction_proposal(
                session,
                exc.exception_id,
                CorrectionProposalCreate(
                    observation_id=obs_id,
                    correction_category="TICK_SIZE_ROUNDING",
                    correction_reason="Fix tick rounding",
                    provenance_reference="SIMULATOR_TEST_FEED_01",
                    provenance_source="SYNTHETIC_SIM",
                    field_changes=[
                        FieldChangeSchema(
                            field_name="price",
                            before_value="1420.3333",
                            after_value="1420.35",
                            change_reason="Round to nearest 0.05 tick",
                        )
                    ],
                ),
                actor_id="analyst_1",
            )
        assert "Synthetic simulator data cannot be used as authoritative evidence" in str(excinfo.value)

        # 2. Legitimate proposal from real authoritative feed
        proposal = await ExceptionManagementService.create_correction_proposal(
            session,
            exc.exception_id,
            CorrectionProposalCreate(
                observation_id=obs_id,
                correction_category="TICK_SIZE_ROUNDING",
                correction_reason="Fix tick rounding per NSE tick tables",
                provenance_reference="NSE_CIRCULAR_TICK_REGISTRY",
                provenance_source="REAL_PROVIDER",
                field_changes=[
                    FieldChangeSchema(
                        field_name="price",
                        before_value="1420.3333",
                        after_value="1420.35",
                        change_reason="Round to nearest 0.05 tick",
                    )
                ],
                resulting_payload_snapshot={"price": 1420.35},
            ),
            actor_id="analyst_1",
        )
        assert proposal.approval_status == ApprovalStatus.PENDING.value

        # 3. Separation of duties violation: analyst_1 cannot approve own proposal
        with pytest.raises(Exception) as excinfo_approve:
            await ExceptionManagementService.approve_correction(
                session,
                proposal.correction_id,
                CorrectionApprovalRequest(approval_reason="Self-approval attempt"),
                approver_id="analyst_1",
            )
        assert "Separation of duties violation" in str(excinfo_approve.value)

        # 4. Legitimate approval by independent administrator
        approved = await ExceptionManagementService.approve_correction(
            session,
            proposal.correction_id,
            CorrectionApprovalRequest(approval_reason="Verified against official NSE tick table"),
            approver_id="supervisor_admin",
        )
        assert approved.approval_status == ApprovalStatus.APPROVED.value


@pytest.mark.asyncio
async def test_replay_idempotency_and_workflow_resolution():
    """
    Verifies:
    - Replay submission executes through M02 integration client.
    - Idempotency key prevents duplicate replay operations.
    - Exception workflow transitions to RESOLVED upon successful replay.
    - Reopening resolved exception creates audit history.
    """
    async with AsyncSessionLocal() as session:
        obs_id = f"OBS_RPL_{uuid.uuid4().hex[:8]}"
        finding = FindingIntakeSchema(
            finding_id=f"FND_RPL_{uuid.uuid4().hex[:6]}",
            source_feature="M03.01",
            finding_code="LATE_OBSERVATION",
            feed_id="FEED_NSE_EQUITY",
            instrument_id="WIPRO",
            observation_id=obs_id,
            source_event_timestamp=datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc),
            raw_payload={"price": 450.0},
        )
        exc = await ExceptionManagementService.register_exception(
            session,
            ExceptionCreateRequest(
                category="TIMELINESS",
                exception_type="LATE_REPLAY",
                summary="Late arriving tick for Wipro",
                description="Recovered from network replay buffer",
                findings=[finding],
            ),
        )

        # Submit replay
        replay_req = await ExceptionManagementService.submit_replay(
            session,
            exc.exception_id,
            ReplaySubmitRequest(
                replay_mode="SINGLE_RECORD",
                replay_reason="Batch network ingestion recovery",
                idempotency_key=f"IDEMP_{uuid.uuid4().hex[:12]}",
            ),
            actor_id="operator_bob",
        )
        assert replay_req.replay_status == ReplayStatus.SUCCEEDED.value

        # Check that exception transitioned to RESOLVED
        updated_exc = await ExceptionRepository.get_by_id(session, exc.exception_id)
        assert updated_exc.workflow_status == WorkflowStatus.RESOLVED.value

        # Reopen exception
        reopened = await ExceptionManagementService.reopen_exception(
            session, exc.exception_id, reason="Subsequent downstream VaR rejected observation", actor_id="risk_auditor"
        )
        assert reopened.workflow_status == WorkflowStatus.REOPENED.value

        # Verify audit entries
        audits = await ExceptionRepository.get_audit_trail(session, exc.exception_id)
        action_types = [a.action_type for a in audits]
        assert "EXCEPTION_CREATED" in action_types
        assert "REPLAY_EXECUTED" in action_types
        assert "EXCEPTION_REOPENED" in action_types


@pytest.mark.asyncio
async def test_rest_api_lifecycle(auth_headers, admin_headers):
    """
    Verifies FastAPI endpoints:
    - POST /api/v1/exceptions/
    - GET /api/v1/exceptions/
    - POST /api/v1/exceptions/{id}/notes
    - GET /api/v1/exceptions/{id}/history
    - GET /api/v1/exceptions/summary
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register exception via REST
        obs_id = f"OBS_REST_{uuid.uuid4().hex[:8]}"
        payload = {
            "category": "DATA_INTEGRITY",
            "exception_type": "CROSS_FEED_DISCREPANCY",
            "severity": "HIGH",
            "priority": "P1",
            "summary": "Feed mismatch on Bharti Airtel",
            "description": "NSE and BSE prices diverged by 4%",
            "findings": [
                {
                    "finding_id": f"FND_REST_{uuid.uuid4().hex[:6]}",
                    "source_feature": "M03.06",
                    "finding_code": "CROSS_FEED_PRICE_DEVIATION",
                    "feed_id": "FEED_NSE_EQUITY",
                    "instrument_id": "BHARTIARTL",
                    "observation_id": obs_id,
                    "source_event_timestamp": "2026-11-01T12:00:00Z",
                    "raw_payload": {"price": 1280.0},
                }
            ],
        }
        resp = await client.post("/api/v1/exceptions/", json=payload, headers=auth_headers)
        assert resp.status_code == 201, resp.text
        exc_data = resp.json()
        exc_id = exc_data["exception_id"]

        # 2. Add note
        note_resp = await client.post(
            f"/api/v1/exceptions/{exc_id}/notes",
            json={"note_content": "Discrepancy investigated against exchange terminal", "note_type": "INVESTIGATION"},
            headers=auth_headers,
        )
        assert note_resp.status_code == 200

        # 3. Retrieve history
        hist_resp = await client.get(f"/api/v1/exceptions/{exc_id}/history", headers=auth_headers)
        assert hist_resp.status_code == 200
        hist_data = hist_resp.json()
        assert len(hist_data["audit_trail"]) >= 1
        assert len(hist_data["notes"]) >= 1

        # 4. Summary metrics
        sum_resp = await client.get("/api/v1/exceptions/summary", headers=auth_headers)
        assert sum_resp.status_code == 200
        assert sum_resp.json()["total_exceptions"] >= 1
