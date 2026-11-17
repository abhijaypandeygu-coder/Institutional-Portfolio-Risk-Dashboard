from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend.app.core.security import require_role, UserRole
from .service import ExternalDataService, ProviderError, provider_status

router = APIRouter(prefix='/api/v1/external-data', tags=['External data providers'])


class DataQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    parameters: dict[str, Any] = Field(default_factory=dict, max_length=10)


@router.get('/providers', dependencies=[Depends(require_role(UserRole.READ_ONLY))])
async def providers():
    return provider_status()


# Operator-only: requests consume external quotas and can access broker account data.
@router.post('/{provider}/{operation}', dependencies=[Depends(require_role(UserRole.OPERATOR))])
async def query(provider: str, operation: str, request: DataQuery):
    try:
        return await ExternalDataService().fetch(provider, operation, request.parameters)
    except ProviderError as exc:
        raise HTTPException(exc.status, detail={'code': exc.code}) from None
