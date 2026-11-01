"""
FastAPI Router for M03.07 - Quality Scoring.
Endpoints for:
- Feed operational reliability scores
- Dataset & field-level completeness scores
- Freshness scores
- Composite quality score snapshots
- Calculation-specific use eligibility decisions
- Quality scoring policies & summary metrics
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import require_role, UserRole, AuthenticatedUser
from backend.app.modules.market_data_quality.quality_scoring.schemas import (
    FeedReliabilityInput,
    FeedReliabilityResponse,
    CompletenessEvaluationInput,
    CompletenessScoreResponse,
    FreshnessEvaluationInput,
    FreshnessScoreResponse,
    CompositeQualityRequest,
    CompositeQualitySnapshotResponse,
    EligibilityEvaluationRequest,
    UseEligibilityDecisionResponse,
    QualityScoringPolicyCreate,
    QualityScoringPolicyResponse,
)
from backend.app.modules.market_data_quality.quality_scoring.service import QualityScoringService
from backend.app.modules.market_data_quality.quality_scoring.repository.repository import (
    QualityScoringRepository,
)

router = APIRouter(prefix="/quality/scoring", tags=["M03.07 - Quality Scoring"])


@router.post("/feed-reliability", response_model=FeedReliabilityResponse)
async def evaluate_feed_reliability(
    payload: FeedReliabilityInput,
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """
    Evaluates feed availability, delivery timeliness, and operational error rates.
    """
    return await QualityScoringService.evaluate_reliability(session, payload)


@router.post("/completeness", response_model=CompletenessScoreResponse)
async def evaluate_completeness(
    payload: CompletenessEvaluationInput,
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """
    Evaluates dataset and field-level completeness against expected observation baselines.
    """
    return await QualityScoringService.evaluate_completeness(session, payload)


@router.post("/freshness", response_model=FreshnessScoreResponse)
async def evaluate_freshness(
    payload: FreshnessEvaluationInput,
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """
    Evaluates observation ages against update cadence SLAs using piecewise decay.
    """
    return await QualityScoringService.evaluate_freshness(session, payload)


@router.post("/calculate", response_model=CompositeQualitySnapshotResponse)
async def calculate_composite_snapshot(
    payload: CompositeQualityRequest,
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """
    Synthesizes reliability, completeness, and freshness into a composite quality snapshot.
    """
    return await QualityScoringService.calculate_composite_snapshot(session, payload)


@router.post("/eligibility/evaluate", response_model=UseEligibilityDecisionResponse)
async def evaluate_use_eligibility(
    payload: EligibilityEvaluationRequest,
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """
    Determines data fitness for specific financial calculations with mandatory hard-gate overrides.
    """
    return await QualityScoringService.evaluate_eligibility(session, payload)


@router.get("/eligibility", response_model=List[UseEligibilityDecisionResponse])
async def list_eligibility_decisions(
    feed_id: Optional[str] = Query(None),
    profile_code: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """
    Lists recorded downstream calculation eligibility decisions.
    """
    return await QualityScoringRepository.list_eligibility_decisions(session, feed_id, profile_code, limit)


@router.post("/policies", response_model=QualityScoringPolicyResponse)
async def create_scoring_policy(
    policy_in: QualityScoringPolicyCreate,
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.ADMIN)),
):
    """
    Configures a versioned quality scoring policy.
    """
    existing = await QualityScoringRepository.get_policy_by_code(session, policy_in.policy_code)
    if existing:
        raise HTTPException(status_code=409, detail=f"Policy '{policy_in.policy_code}' already exists.")
    return await QualityScoringRepository.create_policy(session, policy_in)


@router.get("/policies", response_model=List[QualityScoringPolicyResponse])
async def list_scoring_policies(
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """
    Lists configured quality scoring policies.
    """
    return await QualityScoringRepository.list_policies(session)


@router.get("/summary")
async def get_scoring_summary(
    feed_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """
    Retrieves summary statistics for quality scores across feeds.
    """
    return await QualityScoringRepository.get_summary_scores(session, feed_id)
