"""
FastAPI Router for M03.06 - Data Consistency.
Endpoints for:
- Cross-feed comparisons (single & batch)
- Intra-observation field consistency checks (OHLC & Quote)
- Conflict inspection and manual resolution
- Source precedence policies
- Data consistency summary metrics
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import require_role, UserRole, AuthenticatedUser
from backend.app.modules.market_data_quality.consistency.schemas import (
    CrossFeedCompareRequest,
    ComparisonResultResponse,
    OHLCFieldValidationInput,
    QuoteFieldValidationInput,
    FieldConsistencyResponse,
    ConflictResponse,
    ConflictResolutionActionRequest,
    SourcePrecedenceRuleCreate,
    SourcePrecedenceRuleResponse,
    ConsistencySummary,
)
from backend.app.modules.market_data_quality.consistency.service import DataConsistencyService
from backend.app.modules.market_data_quality.consistency.conflicts.repository import ConsistencyRepository

router = APIRouter(prefix="/quality/consistency", tags=["M03.06 - Data Consistency"])


@router.post("/compare", response_model=ComparisonResultResponse)
async def compare_cross_feed(
    payload: CrossFeedCompareRequest,
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """
    Evaluates cross-feed agreement between two market data observations.
    Calculates absolute and percentage divergence and triggers automated resolution if configured.
    """
    try:
        return await DataConsistencyService.compare_cross_feed(session, payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Comparison error: {str(e)}")


@router.post("/compare/batch", response_model=List[ComparisonResultResponse])
async def compare_cross_feed_batch(
    payloads: List[CrossFeedCompareRequest],
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """
    Evaluates a batch of pairwise cross-feed observations.
    """
    results = []
    for p in payloads:
        res = await DataConsistencyService.compare_cross_feed(session, p)
        results.append(res)
    return results


@router.post("/validate-fields/ohlc", response_model=FieldConsistencyResponse)
async def validate_ohlc_fields(
    payload: OHLCFieldValidationInput,
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """
    Validates logical boundaries for OHLC bars (High >= Low, High >= Open/Close, Low <= Open/Close).
    """
    return await DataConsistencyService.validate_ohlc_fields(session, payload)


@router.post("/validate-fields/quote", response_model=FieldConsistencyResponse)
async def validate_quote_fields(
    payload: QuoteFieldValidationInput,
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """
    Validates Quote displayed quantities and relationships.
    """
    return await DataConsistencyService.validate_quote_fields(session, payload)


@router.get("/conflicts", response_model=List[ConflictResponse])
async def list_conflicts(
    status: Optional[str] = Query(None),
    instrument_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """
    Lists recorded cross-feed discrepancies and conflicts.
    """
    return await ConsistencyRepository.list_conflicts(session, status, instrument_id)


@router.post("/conflicts/{conflict_key}/resolve", response_model=ConflictResponse)
async def resolve_conflict_manually(
    conflict_key: str,
    action_in: ConflictResolutionActionRequest,
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """
    Manually resolves a cross-feed conflict with auditable operator justification.
    """
    conflict = await ConsistencyRepository.get_conflict_by_key(session, conflict_key)
    if not conflict:
        raise HTTPException(status_code=404, detail=f"Conflict '{conflict_key}' not found.")
    return await ConsistencyRepository.apply_manual_resolution(
        session=session, conflict=conflict, resolution=action_in, actor_id=user.username
    )


@router.post("/source-precedence", response_model=SourcePrecedenceRuleResponse)
async def create_source_precedence_rule(
    rule_in: SourcePrecedenceRuleCreate,
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.ADMIN)),
):
    """
    Configures a source ranking precedence policy for automated conflict resolution.
    """
    return await ConsistencyRepository.create_precedence_rule(session, rule_in)


@router.get("/source-precedence", response_model=List[SourcePrecedenceRuleResponse])
async def list_source_precedence_rules(
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """
    Lists configured source precedence rules.
    """
    return await ConsistencyRepository.list_precedence_rules(session)


@router.get("/summary", response_model=ConsistencySummary)
async def get_consistency_summary(
    instrument_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
    _user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """
    Retrieves summary consistency statistics and open conflict counts.
    """
    data = await ConsistencyRepository.get_summary_metrics(session, instrument_id)
    return ConsistencySummary(**data)
