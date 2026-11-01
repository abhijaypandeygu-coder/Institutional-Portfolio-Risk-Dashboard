from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.instrument_reference_data.instrument_mapping.models import (
    NamespaceType,
    MappingTargetType,
    MappingStatus,
    VerificationStatus,
    ResolutionMatchingLevel
)


class IdentifierNamespaceCreate(BaseModel):
    namespace_code: str = Field(..., min_length=2, max_length=64)
    namespace_name: str = Field(..., min_length=2, max_length=128)
    namespace_type: NamespaceType
    provider_name: Optional[str] = None
    exchange_code: Optional[str] = None
    case_sensitive: bool = False
    strip_suffix: bool = False


class IdentifierNamespaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    namespace_code: str
    namespace_name: str
    namespace_type: NamespaceType
    provider_name: Optional[str] = None
    exchange_code: Optional[str] = None
    case_sensitive: bool
    strip_suffix: bool
    is_active: bool
    created_at: datetime


class ExternalIdentifierMappingCreate(BaseModel):
    mapping_id: str = Field(..., min_length=3, max_length=64)
    namespace_code: str = Field(..., min_length=2, max_length=64)
    external_identifier_raw: str = Field(..., min_length=1, max_length=128)
    target_type: MappingTargetType = MappingTargetType.LISTING_LEVEL
    instrument_id: str = Field(..., min_length=3, max_length=64)
    listing_id: Optional[str] = None
    exchange_code: Optional[str] = None
    effective_from: date
    effective_to: Optional[date] = None
    mapping_status: MappingStatus = MappingStatus.APPROVED_FOR_INGESTION
    source_reference: Optional[str] = None


class ExternalIdentifierMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mapping_id: str
    namespace_code: str
    external_identifier_raw: str
    external_identifier_normalized: str
    target_type: MappingTargetType
    instrument_id: str
    listing_id: Optional[str] = None
    exchange_code: Optional[str] = None
    mapping_status: MappingStatus
    verification_status: VerificationStatus
    effective_from: date
    effective_to: Optional[date] = None
    mapping_version: int
    recorded_at: datetime


class ResolveIdentifierRequest(BaseModel):
    namespace_code: str
    raw_identifier: str
    as_of_date: Optional[date] = None
    exchange_code: Optional[str] = None


class ResolvedIdentifierResponse(BaseModel):
    matching_level: ResolutionMatchingLevel
    raw_identifier: str
    normalized_identifier: str
    namespace_code: str
    instrument_id: Optional[str] = None
    listing_id: Optional[str] = None
    exchange_code: Optional[str] = None
    mapping_id: Optional[str] = None
    mapping_version: Optional[int] = None
    is_eligible_for_ingestion: bool
    candidate_instrument_ids: List[str] = []
    reason: Optional[str] = None


class BulkResolveRequest(BaseModel):
    requests: List[ResolveIdentifierRequest]


class BulkResolveResponse(BaseModel):
    total_requested: int
    resolved_count: int
    unresolved_count: int
    results: List[ResolvedIdentifierResponse]
