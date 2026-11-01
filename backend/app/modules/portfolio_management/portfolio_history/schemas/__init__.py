"""
M05.07 - Portfolio History Schemas.
Pydantic contracts for historical state queries, snapshot capture, timeline, and risk input manifests.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from backend.app.modules.portfolio_management.portfolio_history.models import SnapshotType, ChangeEventCategory, ReconstructionMode


class HistoricalPositionItemSchema(BaseModel):
    account_id: str
    instrument_id: str
    net_signed_quantity: Decimal
    gross_long_quantity: Decimal = Decimal("0")
    gross_short_quantity: Decimal = Decimal("0")
    settled_quantity: Decimal = Decimal("0")
    unsettled_buy_quantity: Decimal = Decimal("0")
    unsettled_sell_quantity: Decimal = Decimal("0")
    available_quantity: Decimal = Decimal("0")
    currency: str
    cost_basis_amount: Decimal = Decimal("0")
    cost_basis_base: Decimal = Decimal("0")
    market_price: Optional[Decimal] = None
    market_value_base: Decimal = Decimal("0")
    unrealized_pnl_base: Decimal = Decimal("0")
    effective_as_of: datetime
    knowledge_as_of: datetime


class HistoricalCashItemSchema(BaseModel):
    account_id: str
    currency: str
    settled_cash: Decimal
    unsettled_receivables: Decimal = Decimal("0")
    unsettled_payables: Decimal = Decimal("0")
    reserved_cash: Decimal = Decimal("0")
    restricted_cash: Decimal = Decimal("0")
    available_cash: Decimal
    fx_rate_to_base: Decimal = Decimal("1")
    available_cash_base: Decimal
    effective_as_of: datetime
    knowledge_as_of: datetime


class HistoricalValuationItemSchema(BaseModel):
    instrument_id: str
    price_source: str
    price_timestamp: datetime
    market_price: Decimal
    price_currency: str
    fx_rate_to_base: Decimal = Decimal("1")
    market_value_local: Decimal
    market_value_base: Decimal
    cost_basis_base: Decimal
    unrealized_pnl_base: Decimal


class SnapshotSourceManifestSchema(BaseModel):
    source_module: str
    event_watermark_id: Optional[str] = None
    event_watermark_timestamp: Optional[datetime] = None
    records_count: int = 0
    metadata_json: Optional[Dict[str, Any]] = None


class PortfolioBookSnapshotCreateRequest(BaseModel):
    portfolio_id: str
    snapshot_type: SnapshotType = SnapshotType.EOD
    effective_as_of: datetime
    knowledge_as_of: Optional[datetime] = None
    base_currency: str = "USD"
    positions: List[HistoricalPositionItemSchema] = Field(default_factory=list)
    cash_balances: List[HistoricalCashItemSchema] = Field(default_factory=list)
    valuations: List[HistoricalValuationItemSchema] = Field(default_factory=list)
    source_manifests: List[SnapshotSourceManifestSchema] = Field(default_factory=list)
    restatement_reason: Optional[str] = None
    superseded_snapshot_id: Optional[str] = None


class PortfolioBookSnapshotResponse(BaseModel):
    snapshot_id: str
    portfolio_id: str
    snapshot_type: str
    effective_as_of: datetime
    knowledge_as_of: datetime
    created_at: datetime
    snapshot_version: int
    is_restated: bool
    superseded_snapshot_id: Optional[str] = None
    restatement_reason: Optional[str] = None
    base_currency: str
    total_positions_count: int
    total_market_value_base: Decimal
    total_cash_value_base: Decimal
    total_nav_base: Decimal
    snapshot_hash: str
    positions: List[HistoricalPositionItemSchema] = Field(default_factory=list)
    cash_balances: List[HistoricalCashItemSchema] = Field(default_factory=list)
    valuations: List[HistoricalValuationItemSchema] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PortfolioChangeRecordCreateRequest(BaseModel):
    portfolio_id: str
    event_category: ChangeEventCategory
    source_module: str
    source_event_id: str
    effective_at: datetime
    recorded_at: Optional[datetime] = None
    instrument_id: Optional[str] = None
    account_id: Optional[str] = None
    quantity_delta: Optional[Decimal] = None
    cash_delta: Optional[Decimal] = None
    currency: Optional[str] = None
    change_description: str
    change_details: Optional[Dict[str, Any]] = None


class PortfolioChangeRecordResponse(BaseModel):
    change_record_id: str
    portfolio_id: str
    sequence_number: int
    event_category: str
    source_module: str
    source_event_id: str
    effective_at: datetime
    recorded_at: datetime
    instrument_id: Optional[str] = None
    account_id: Optional[str] = None
    quantity_delta: Optional[Decimal] = None
    cash_delta: Optional[Decimal] = None
    currency: Optional[str] = None
    change_description: str
    change_details: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class BitemporalStateQueryRequest(BaseModel):
    portfolio_id: str
    effective_as_of: datetime
    knowledge_as_of: Optional[datetime] = None  # None implies current knowledge (Query A), set implies Query B
    reconstruction_mode: ReconstructionMode = ReconstructionMode.EXACT_SNAPSHOT


class BitemporalStateResponse(BaseModel):
    portfolio_id: str
    query_type: str  # "QUERY_A_LATEST_KNOWLEDGE" or "QUERY_B_POINT_IN_TIME_KNOWLEDGE"
    effective_as_of: datetime
    knowledge_as_of: datetime
    matched_snapshot_id: Optional[str] = None
    is_restated: bool = False
    base_currency: str
    total_market_value_base: Decimal
    total_cash_value_base: Decimal
    total_nav_base: Decimal
    positions: List[HistoricalPositionItemSchema]
    cash_balances: List[HistoricalCashItemSchema]
    explanation: str


class RiskRunInputManifestCreateRequest(BaseModel):
    portfolio_id: str
    risk_run_id: str
    snapshot_id: str
    market_data_partition_id: str
    pricing_policy_version: str = "POL-EOD-DEFAULT-V1"
    fx_rate_table_version: str = "FX-OFFICIAL-EOD-V1"
    corporate_action_version: str = "CA-VER-V1"


class RiskRunInputManifestResponse(BaseModel):
    manifest_id: str
    portfolio_id: str
    risk_run_id: str
    created_at: datetime
    snapshot_id: str
    effective_as_of: datetime
    knowledge_as_of: datetime
    market_data_partition_id: str
    pricing_policy_version: str
    fx_rate_table_version: str
    corporate_action_version: str
    positions_count: int
    total_nav_base: Decimal
    manifest_hash: str
    manifest_payload: Dict[str, Any]

    model_config = {"from_attributes": True}
