"""
Pydantic 2.x Schemas for M04.02 Security Classification.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ClassificationSchemeCreate(BaseModel):
    scheme_code: str
    scheme_name: str
    description: str
    provider: str
    scheme_type: str = "INTERNAL_PROPRIETARY"
    applicable_market_scope: str = "GLOBAL"
    is_primary_default: bool = False


class ClassificationSchemeVersionCreate(BaseModel):
    version_code: str
    version_description: str
    effective_from: Optional[datetime] = None


class ClassificationNodeCreate(BaseModel):
    node_code: str
    node_name: str
    node_description: str
    node_type: str  # SECTOR, INDUSTRY
    parent_node_id: Optional[str] = None
    hierarchy_level: int = 1


class AssetCategoryCreate(BaseModel):
    category_code: str
    category_name: str
    description: str
    applicable_asset_class: str = "EQUITY"


class ClassificationAssignRequest(BaseModel):
    scheme_code: str
    version_code: Optional[str] = None
    sector_code: str
    industry_code: Optional[str] = None
    valid_from: Optional[datetime] = None
    assignment_source: str = "INTERNAL_RESEARCH"
    assignment_reason: str


class AssetCategoryAssignRequest(BaseModel):
    category_code: str
    assignment_source: str = "MANUAL_ENTRY"
    assignment_reason: str


class BulkClassificationLookupRequest(BaseModel):
    instrument_ids: List[str]
    scheme_code: Optional[str] = None
    as_of_valid_time: Optional[datetime] = None
    as_of_transaction_time: Optional[datetime] = None


# Response Schemas
class ClassificationSchemeResponse(BaseModel):
    id: int
    scheme_code: str
    scheme_name: str
    description: str
    provider: str
    scheme_type: str
    is_active: bool
    is_primary_default: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClassificationNodeResponse(BaseModel):
    id: int
    node_id: str
    scheme_id: int
    node_code: str
    node_name: str
    node_description: str
    node_type: str
    parent_node_id: Optional[str]
    hierarchy_level: int
    node_status: str

    model_config = ConfigDict(from_attributes=True)


class InstrumentClassificationDetail(BaseModel):
    instrument_id: str
    scheme_code: str
    scheme_name: str
    version_code: str
    sector_code: str
    sector_name: str
    industry_code: Optional[str] = None
    industry_name: Optional[str] = None
    asset_category_code: Optional[str] = None
    asset_category_name: Optional[str] = None
    assignment_status: str
    verification_status: str
    assignment_source: str
    valid_from: datetime
    valid_to: Optional[datetime]
    recorded_at: datetime
    assignment_version: int


class BulkClassificationLookupResponse(BaseModel):
    results: Dict[str, Optional[InstrumentClassificationDetail]]
    as_of_valid_time: Optional[datetime]
    as_of_transaction_time: Optional[datetime]
    total_requested: int
    total_classified: int


class ClassificationCoverageMetrics(BaseModel):
    total_active_instruments: int
    classified_instruments: int
    sector_coverage_percentage: float
    industry_coverage_percentage: float
    asset_category_coverage_percentage: float
    conflicted_assignments_count: int

