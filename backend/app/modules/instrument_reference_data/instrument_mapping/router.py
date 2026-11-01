from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.instrument_reference_data.instrument_mapping.schemas import (
    IdentifierNamespaceCreate,
    IdentifierNamespaceResponse,
    ExternalIdentifierMappingCreate,
    ExternalIdentifierMappingResponse,
    ResolveIdentifierRequest,
    ResolvedIdentifierResponse,
    BulkResolveRequest,
    BulkResolveResponse
)
from backend.app.modules.instrument_reference_data.instrument_mapping.services.service import InstrumentMappingService

router = APIRouter(prefix="/instrument-mappings", tags=["Instrument Mapping"])


@router.post("/namespaces", response_model=IdentifierNamespaceResponse, status_code=status.HTTP_201_CREATED)
async def create_namespace(
    payload: IdentifierNamespaceCreate,
    db: AsyncSession = Depends(get_db)
):
    service = InstrumentMappingService(db)
    try:
        return await service.create_namespace(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/namespaces", response_model=List[IdentifierNamespaceResponse])
async def list_namespaces(db: AsyncSession = Depends(get_db)):
    service = InstrumentMappingService(db)
    return await service.repo.list_namespaces()


@router.post("", response_model=ExternalIdentifierMappingResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ExternalIdentifierMappingResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_mapping(
    payload: ExternalIdentifierMappingCreate,
    db: AsyncSession = Depends(get_db)
):
    service = InstrumentMappingService(db)
    try:
        return await service.create_mapping(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{mapping_id}", response_model=ExternalIdentifierMappingResponse)
async def get_mapping(
    mapping_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = InstrumentMappingService(db)
    m = await service.repo.get_mapping_by_id(mapping_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Mapping '{mapping_id}' not found.")
    return m


@router.post("/resolve", response_model=ResolvedIdentifierResponse)
async def resolve_identifier(
    req: ResolveIdentifierRequest,
    db: AsyncSession = Depends(get_db)
):
    service = InstrumentMappingService(db)
    return await service.resolve_identifier(req)


@router.post("/resolve/bulk", response_model=BulkResolveResponse)
async def bulk_resolve(
    req: BulkResolveRequest,
    db: AsyncSession = Depends(get_db)
):
    service = InstrumentMappingService(db)
    return await service.bulk_resolve(req)
