"""
Pydantic 2.x schemas for M04.01 Instrument Master.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
from backend.app.modules.instrument_reference_data.instrument_master.policies.identity_rules import (
    validate_isin_checksum,
    InstrumentType,
    LifecycleStatus,
    ListingStatus,
    VerificationStatus,
)


class InstrumentCreateRequest(BaseModel):
    canonical_name: str
    short_name: str
    instrument_type: str = "COMMON_STOCK"
    asset_class: str = "EQUITY"
    security_type: Optional[str] = None
    issuer_name: Optional[str] = None
    isin: Optional[str] = None
    country_of_issue: Optional[str] = None
    issue_currency: Optional[str] = None
    primary_market_id: Optional[str] = None
    source_name: str = "MANUAL_ENTRY"

    @field_validator("isin")
    @classmethod
    def validate_isin(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            cleaned = v.strip().upper()
            if not validate_isin_checksum(cleaned):
                raise ValueError(f"Invalid ISIN format or checksum: '{cleaned}'")
            return cleaned
        return None


class InstrumentUpdateRequest(BaseModel):
    canonical_name: Optional[str] = None
    short_name: Optional[str] = None
    issuer_name: Optional[str] = None
    lifecycle_status: Optional[str] = None
    change_reason: str


class ListingCreateRequest(BaseModel):
    market_id: str
    exchange_id: str
    exchange_symbol: str
    exchange_security_code: Optional[str] = None
    trading_currency: str = "INR"
    listing_type: str = "PRIMARY_LISTING"
    is_primary_listing: bool = False
    source_reference: Optional[str] = None


class ListingStatusUpdateRequest(BaseModel):
    listing_status: str
    change_reason: str


class IdentifierCreateRequest(BaseModel):
    identifier_type: str
    identifier_value: str
    source_id: str


class ImportBatchCreateRequest(BaseModel):
    source_name: str
    source_type: str = "CSV"
    records: List[Dict[str, Any]]


class IdentityReviewResolveRequest(BaseModel):
    review_decision: str  # LINK_EXISTING, CREATE_NEW, REJECT
    target_instrument_id: Optional[str] = None
    reason: str


# Responses
class ListingResponse(BaseModel):
    id: int
    listing_id: str
    instrument_id: str
    market_id: str
    exchange_id: str
    exchange_symbol: str
    exchange_security_code: Optional[str]
    trading_currency: str
    listing_type: str
    listing_status: str
    is_primary_listing: bool
    verification_status: str
    effective_from: datetime
    effective_to: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InstrumentResponse(BaseModel):
    id: int
    instrument_id: str
    canonical_name: str
    short_name: str
    instrument_type: str
    asset_class: str
    security_type: Optional[str]
    issuer_name: Optional[str]
    isin: Optional[str]
    country_of_issue: Optional[str]
    issue_currency: Optional[str]
    primary_market_id: Optional[str]
    lifecycle_status: str
    verification_status: str
    current_version: int
    effective_from: datetime
    effective_to: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    listings: Optional[List[ListingResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class InstrumentResolutionResponse(BaseModel):
    match_status: str
    instrument_id: Optional[str] = None
    canonical_name: Optional[str] = None
    listing_id: Optional[str] = None
    exchange_id: Optional[str] = None
    exchange_symbol: Optional[str] = None
    isin: Optional[str] = None
    lifecycle_status: Optional[str] = None
    listing_status: Optional[str] = None
    verification_status: Optional[str] = None
    confidence_score: float = 1.0
    candidates: Optional[List[Dict[str, Any]]] = None


class ImportBatchResponse(BaseModel):
    id: int
    batch_reference: str
    source_name: str
    source_type: str
    import_status: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_candidates: int
    created_count: int
    updated_count: int
    failed_count: int
    started_at: datetime
    completed_at: Optional[datetime]
    created_by: str

    model_config = ConfigDict(from_attributes=True)


class IdentityReviewResponse(BaseModel):
    id: int
    review_id: str
    candidate_instrument_id: Optional[str]
    candidate_listing_id: Optional[str]
    match_classification: str
    evidence: Dict[str, Any]
    review_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

