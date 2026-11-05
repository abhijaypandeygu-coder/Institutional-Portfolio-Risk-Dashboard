"""
Hypothetical Scenarios FastAPI Router (M10.02).
Endpoints for managing reusable scenario templates, previewing shock transformations,
executing multi-channel hypothetical scenarios, and retrieving granular position, risk, and liquidity outputs.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from .services.hypothetical_service import HypotheticalScenariosService
from .schemas.hypothetical_schemas import (
    ScenarioTemplateCreate,
    ScenarioTemplateResponse,
    ScenarioExecutionRequest,
    ScenarioRunSummaryResponse
)

router = APIRouter(
    prefix="/api/v1/scenarios/hypothetical",
    tags=["M10.02 Hypothetical Scenarios"]
)


@router.post("/templates", response_model=ScenarioTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    req: ScenarioTemplateCreate,
    db: AsyncSession = Depends(get_db)
):
    service = HypotheticalScenariosService(db)
    return await service.create_template(req)


@router.get("/templates", response_model=List[ScenarioTemplateResponse])
async def list_templates(
    category: Optional[str] = Query(None),
    author_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    service = HypotheticalScenariosService(db)
    templates = await service.repo.list_templates(category=category, author_id=author_id, limit=limit)
    return [ScenarioTemplateResponse.model_validate(t) for t in templates]


@router.get("/templates/{template_id}", response_model=ScenarioTemplateResponse)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db)
):
    service = HypotheticalScenariosService(db)
    tmpl = await service.repo.get_template_by_id(template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    return ScenarioTemplateResponse.model_validate(tmpl)


@router.post("/runs", response_model=ScenarioRunSummaryResponse, status_code=status.HTTP_200_OK)
async def execute_scenario(
    req: ScenarioExecutionRequest,
    db: AsyncSession = Depends(get_db)
):
    service = HypotheticalScenariosService(db)
    try:
        return await service.execute_scenario(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

