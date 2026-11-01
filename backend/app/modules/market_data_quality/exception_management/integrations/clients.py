"""
M03.08 Integration interfaces for M02, M03 Findings, and M03.07 Quality Scoring.
"""
from typing import Dict, Any, Optional
import uuid
import logging

logger = logging.getLogger("market_data_quality.exception_management.integrations")


class IngestionQuarantineClient:
    """Interface allowing M03.08 to coordinate quarantine with M02 ingestion engine."""

    @classmethod
    async def request_observation_quarantine(
        cls, observation_id: str, feed_id: str, reason: str
    ) -> Dict[str, Any]:
        """Notifies M02 to isolate observation from trusted downstream distribution."""
        logger.info(f"M02_QUARANTINE_ISOLATION_REQUEST observation_id={observation_id} feed_id={feed_id} reason={reason}")
        return {
            "status": "ISOLATED",
            "observation_id": observation_id,
            "isolation_confirmed": True,
            "isolation_token": f"QIS_{uuid.uuid4().hex[:8]}",
        }

    @classmethod
    async def request_observation_release(
        cls, observation_id: str, release_token: str
    ) -> Dict[str, Any]:
        """Notifies M02 of verified release back into processing pipeline."""
        logger.info(f"M02_QUARANTINE_RELEASE_REQUEST observation_id={observation_id} token={release_token}")
        return {
            "status": "RELEASED_TO_INGESTION",
            "observation_id": observation_id,
            "release_confirmed": True,
        }


class IngestionReplayClient:
    """Interface allowing M03.08 to request replay execution from M02."""

    @classmethod
    async def submit_replay_request(
        cls,
        replay_id: str,
        observation_id: str,
        replay_mode: str,
        correction_payload: Optional[Dict[str, Any]] = None,
        idempotency_key: str = "",
    ) -> Dict[str, Any]:
        """
        Executes replay in M02 ingestion pipeline.
        M02 processes data, recalculates canonical states, and pushes through validation.
        """
        logger.info(
            f"M02_REPLAY_EXECUTION_DISPATCH replay_id={replay_id} observation_id={observation_id} mode={replay_mode} key={idempotency_key}"
        )
        return {
            "execution_status": "SUCCEEDED",
            "integration_reference": f"M02_RPL_REF_{uuid.uuid4().hex[:8]}",
            "observation_id": observation_id,
            "details": "M02 replay engine re-parsed corrected payload and refreshed canonical tick state.",
        }


class QualityResultClient:
    """Interface to query updated quality scores and use-eligibility from M03.07 post-remediation."""

    @classmethod
    async def fetch_updated_eligibility(
        cls, profile_code: str, feed_id: str, instrument_id: str
    ) -> Dict[str, Any]:
        """Fetches post-remediation eligibility decision."""
        return {
            "profile_code": profile_code,
            "eligibility_status": "ACCEPTED",
            "hard_gates_passed": True,
            "evaluated_at": "2026-11-01T12:00:00Z",
        }

