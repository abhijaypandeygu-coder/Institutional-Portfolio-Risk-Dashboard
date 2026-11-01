"""
FastAPI Router for M03.04 - Order Book Validation.
Endpoints for:
- Single & batch order book validation
- Validation rule configuration
- Incident inspection & lifecycle
- M02 Resynchronization tracking
- Feed/symbol quality summaries
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import require_role, UserRole
from backend.app.modules.market_data_quality.order_book.schemas import (
    OrderBookValidationInput,
    ValidationResultResponse,
    BookValidationRuleCreate,
    BookValidationRuleResponse,
    ResyncRequestCreate,
    ResyncRequestResponse,
    BookIntegrityIncidentResponse,
    BookQualitySummary
)
from backend.app.modules.market_data_quality.order_book.service import OrderBookValidationService
from backend.app.modules.market_data_quality.order_book.incidents.repository import BookIncidentRepository

router = APIRouter(prefix="/quality/order-book", tags=["M03.04 - Order Book Validation"])


@router.post("/validate", response_model=ValidationResultResponse)
async def validate_order_book(
    payload: OrderBookValidationInput,
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.OPERATOR))
):
    """
    Validates a single order book observation (snapshot or delta).
    Evaluates crossed books, locked books, displayed quantities, continuity, and structures.
    """
    try:
        return await OrderBookValidationService.validate_order_book(session, payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Order book validation error: {str(e)}")


@router.post("/validate/batch", response_model=List[ValidationResultResponse])
async def validate_order_book_batch(
    payloads: List[OrderBookValidationInput],
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.OPERATOR))
):
    """
    Validates a batch of sequential order book observations.
    """
    results = []
    for item in payloads:
        res = await OrderBookValidationService.validate_order_book(session, item)
        results.append(res)
    return results


@router.post("/rules", response_model=BookValidationRuleResponse)
async def create_validation_rule(
    rule_in: BookValidationRuleCreate,
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.ADMIN))
):
    """
    Configures a new order book validation rule.
    """
    existing = await BookIncidentRepository.get_rule_by_code(session, rule_in.rule_code)
    if existing:
        raise HTTPException(status_code=409, detail=f"Rule with code '{rule_in.rule_code}' already exists.")
    return await BookIncidentRepository.create_rule(session, rule_in)


@router.get("/rules", response_model=List[BookValidationRuleResponse])
async def list_validation_rules(
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.READ_ONLY))
):
    """
    Lists all configured order book validation rules.
    """
    return await BookIncidentRepository.list_rules(session)


@router.get("/incidents", response_model=List[BookIntegrityIncidentResponse])
async def list_incidents(
    feed_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.READ_ONLY))
):
    """
    Lists order book integrity incidents with optional filters.
    """
    return await BookIncidentRepository.list_incidents(session, feed_id, symbol, status)


@router.post("/resync", response_model=ResyncRequestResponse)
async def request_order_book_resynchronization(
    resync_in: ResyncRequestCreate,
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.OPERATOR))
):
    """
    Manually initiates or simulates an order book resynchronization request to M02.
    """
    return await BookIncidentRepository.create_resync_request(session, resync_in)


@router.get("/summary", response_model=BookQualitySummary)
async def get_book_quality_summary(
    feed_id: str = Query(..., description="Market data feed identifier"),
    symbol: str = Query(..., description="Ticker symbol"),
    session: AsyncSession = Depends(get_db),
    _user=Depends(require_role(UserRole.READ_ONLY))
):
    """
    Retrieves summary quality and eligibility statistics for a feed and symbol.
    """
    summary = await BookIncidentRepository.get_quality_summary(session, feed_id, symbol)
    return BookQualitySummary(**summary)
