"""
FastAPI Router for M04.01 Instrument Master.
Mounts endpoints under /api/v1/instruments.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user, require_role, UserRole, AuthenticatedUser
from backend.app.modules.instrument_reference_data.instrument_master.schemas import (
    InstrumentCreateRequest,
    InstrumentUpdateRequest,
    InstrumentResponse,
    ListingCreateRequest,
    ListingStatusUpdateRequest,
    ListingResponse,
    InstrumentResolutionResponse,
    ImportBatchCreateRequest,
    ImportBatchResponse,
)
from backend.app.modules.instrument_reference_data.instrument_master.services.service import (
    InstrumentMasterService,
)
from backend.app.modules.instrument_reference_data.instrument_master.repositories.repository import (
    InstrumentRepository,
)

router = APIRouter(prefix="/instruments", tags=["M04.01 - Instrument Master"])


# 1. Instrument Endpoints
@router.post("/", response_model=InstrumentResponse, status_code=status.HTTP_201_CREATED)
async def create_instrument(
    req: InstrumentCreateRequest,
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Creates a canonical instrument with a stable internal UUID."""
    return await InstrumentMasterService.create_instrument(session, req, actor_id=user.username)


@router.get("/", response_model=List[InstrumentResponse])
async def list_instruments(
    query: Optional[str] = Query(None, description="Search by name, symbol, or ISIN"),
    instrument_type: Optional[str] = Query(None),
    lifecycle_status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Lists and searches canonical instruments."""
    instruments = await InstrumentRepository.list_instruments(
        session, query, instrument_type, lifecycle_status, limit, offset
    )
    result = []
    for inst in instruments:
        listings = await InstrumentRepository.get_listings_for_instrument(session, inst.instrument_id)
        inst_dict = {c.name: getattr(inst, c.name) for c in inst.__table__.columns}
        inst_dict["listings"] = listings
        result.append(InstrumentResponse.model_validate(inst_dict))
    return result


@router.get("/resolve", response_model=InstrumentResolutionResponse)
async def resolve_identifier(
    symbol: Optional[str] = Query(None),
    exchange: Optional[str] = Query(None),
    isin: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Resolves an external symbol, exchange code, or ISIN to canonical instrument and listing IDs."""
    return await InstrumentMasterService.resolve_identifier(
        session, symbol=symbol, exchange=exchange, isin=isin
    )


@router.get("/{instrument_id}", response_model=InstrumentResponse)
async def get_instrument(
    instrument_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Retrieves full details of a canonical instrument."""
    inst = await InstrumentRepository.get_by_instrument_id(session, instrument_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Instrument not found.")
    listings = await InstrumentRepository.get_listings_for_instrument(session, inst.instrument_id)
    inst_dict = {c.name: getattr(inst, c.name) for c in inst.__table__.columns}
    inst_dict["listings"] = listings
    return InstrumentResponse.model_validate(inst_dict)


@router.patch("/{instrument_id}", response_model=InstrumentResponse)
async def update_instrument(
    req: InstrumentUpdateRequest,
    instrument_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Updates permitted attributes with effective-dated history."""
    return await InstrumentMasterService.update_instrument(session, instrument_id, req, actor_id=user.username)


@router.get("/{instrument_id}/history")
async def get_instrument_history(
    instrument_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Retrieves attribute change history for an instrument."""
    return await InstrumentRepository.get_history(session, instrument_id)


# 2. Listing Endpoints
@router.post("/{instrument_id}/listings", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
async def create_listing(
    req: ListingCreateRequest,
    instrument_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Creates an exchange-facing listing for a canonical instrument."""
    return await InstrumentMasterService.create_listing(session, instrument_id, req, actor_id=user.username)


@router.get("/{instrument_id}/listings", response_model=List[ListingResponse])
async def get_instrument_listings(
    instrument_id: str = Path(...),
    active_only: bool = Query(True),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.READ_ONLY)),
):
    """Lists all venue listings for an instrument."""
    return await InstrumentRepository.get_listings_for_instrument(session, instrument_id, active_only)


@router.post("/listings/{listing_id}/status", response_model=ListingResponse)
async def update_listing_status(
    req: ListingStatusUpdateRequest,
    listing_id: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Updates listing status (SUSPENDED, DELISTED, etc.)."""
    return await InstrumentMasterService.update_listing_status(session, listing_id, req, actor_id=user.username)


# 3. Import Endpoints
@router.post("/imports", response_model=ImportBatchResponse, status_code=status.HTTP_201_CREATED)
async def create_import_batch(
    req: ImportBatchCreateRequest,
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.OPERATOR)),
):
    """Stages a reference data import batch for validation and preview."""
    return await InstrumentMasterService.create_import_batch(session, req, actor_id=user.username)


@router.post("/imports/{batch_reference}/process", response_model=ImportBatchResponse)
async def process_import_batch(
    batch_reference: str = Path(...),
    session: AsyncSession = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role(UserRole.ADMIN)),
):
    """Processes an approved import batch into canonical instruments & listings."""
    return await InstrumentMasterService.process_import_batch(session, batch_reference, actor_id=user.username)

