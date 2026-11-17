from datetime import datetime, timezone
from decimal import Decimal
from typing import Generic, TypeVar, Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")


class APIResponseMeta(BaseModel):
    """Institutional API response metadata."""
    request_id: str = Field(..., description="Unique request tracing identifier")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp of response generation")
    environment: str = Field("production-local", description="Runtime environment")
    version: str = Field("v1", description="API contract version")


class PaginationMeta(APIResponseMeta):
    """Metadata envelope for paginated collections."""
    page: int = Field(..., ge=1, description="Current page number (1-based)")
    page_size: int = Field(..., ge=1, le=500, description="Items per page")
    total_items: int = Field(..., ge=0, description="Total matching items across all pages")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class SingleResourceResponse(BaseModel, Generic[T]):
    """Standardized envelope for individual resource responses."""
    data: T
    meta: APIResponseMeta


class PaginatedCollectionResponse(BaseModel, Generic[T]):
    """Standardized envelope for paginated collection responses."""
    data: List[T]
    meta: PaginationMeta


class ValidationErrorDetail(BaseModel):
    """Field-level validation error specification."""
    field: str = Field(..., description="Field path or parameter name")
    code: str = Field(..., description="Machine-readable error classification code")
    message: str = Field(..., description="Safe human-readable validation issue description")


class APIErrorEnvelope(BaseModel):
    """Uniform institutional error response envelope."""
    error: Dict[str, Any] = Field(
        ...,
        description="Structured error object containing code, message, details, and request_id",
    )


class APIPaginationParams(BaseModel):
    """Common request parameters for pagination."""
    page: int = Field(1, ge=1, description="1-based page number")
    page_size: int = Field(25, ge=1, le=500, description="Items per page")
    sort_by: Optional[str] = Field(None, description="Field name to sort by")
    sort_order: str = Field("asc", pattern="^(asc|desc)$", description="Sort direction ('asc' or 'desc')")


class HealthStatusResponse(BaseModel):
    """Structured platform API health status."""
    status: str = Field("healthy", description="Overall API health state")
    app_name: str
    api_version: str = "v1"
    uptime_seconds: float
    modules_registered: int
    database_connected: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
