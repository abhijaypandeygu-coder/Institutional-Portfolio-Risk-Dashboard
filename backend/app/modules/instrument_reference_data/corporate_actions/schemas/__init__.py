from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from backend.app.modules.instrument_reference_data.corporate_actions.models import (
    CorporateActionType,
    LifecycleStatus,
    InstrumentRole,
    ConsiderationType,
    GrossNetBasis
)


class DividendDetailCreate(BaseModel):
    gross_amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    gross_net_basis: GrossNetBasis = GrossNetBasis.GROSS
    withholding_tax_rate: Optional[Decimal] = Field(default=Decimal("0.0"), ge=0, le=1)
    reinvestment_price: Optional[Decimal] = None


class RatioDetailCreate(BaseModel):
    numerator: int = Field(..., gt=0)
    denominator: int = Field(..., gt=0)
    additional_shares: Optional[int] = Field(default=None, gt=0)
    existing_shares: Optional[int] = Field(default=None, gt=0)


class MergerDetailCreate(BaseModel):
    consideration_type: ConsiderationType
    successor_instrument_id: Optional[str] = None
    stock_conversion_numerator: Optional[int] = Field(default=None, gt=0)
    stock_conversion_denominator: Optional[int] = Field(default=None, gt=0)
    cash_per_share: Optional[Decimal] = Field(default=None, ge=0)
    cash_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)


class CorporateActionCreate(BaseModel):
    event_id: str = Field(..., min_length=3, max_length=64)
    corporate_action_type: CorporateActionType
    lifecycle_status: LifecycleStatus = LifecycleStatus.ANNOUNCED
    primary_instrument_id: str = Field(..., min_length=3, max_length=64)
    
    declaration_date: Optional[date] = None
    ex_date: date
    record_date: Optional[date] = None
    payment_date: Optional[date] = None
    effective_date: date
    
    source_name: str = "MANUAL"
    source_reference_id: Optional[str] = None
    description: Optional[str] = None
    
    dividend_detail: Optional[DividendDetailCreate] = None
    ratio_detail: Optional[RatioDetailCreate] = None
    merger_detail: Optional[MergerDetailCreate] = None


class CorporateActionUpdate(BaseModel):
    lifecycle_status: Optional[LifecycleStatus] = None
    declaration_date: Optional[date] = None
    ex_date: Optional[date] = None
    record_date: Optional[date] = None
    payment_date: Optional[date] = None
    effective_date: Optional[date] = None
    description: Optional[str] = None
    reason: Optional[str] = None
    
    dividend_detail: Optional[DividendDetailCreate] = None
    ratio_detail: Optional[RatioDetailCreate] = None
    merger_detail: Optional[MergerDetailCreate] = None


class CorporateActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    corporate_action_type: CorporateActionType
    lifecycle_status: LifecycleStatus
    primary_instrument_id: str
    ex_date: date
    effective_date: date
    current_version: int
    source_name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CalculateAdjustmentRequest(BaseModel):
    instrument_id: str
    unadjusted_price: Decimal = Field(..., gt=0)
    unadjusted_quantity: Decimal = Field(..., gt=0)
    as_of_date: date
    policy_version: str = "v1.0"


class AdjustmentLineageStep(BaseModel):
    event_id: str
    event_version: int
    event_type: str
    observation_date: date
    unadjusted_price: Decimal
    step_price_factor: Decimal
    adjusted_price: Decimal
    unadjusted_quantity: Decimal
    step_quantity_factor: Decimal
    adjusted_quantity: Decimal
    formula_description: str


class AdjustmentResultResponse(BaseModel):
    run_id: str
    instrument_id: str
    as_of_date: date
    policy_version: str
    cumulative_price_factor: Decimal
    cumulative_quantity_factor: Decimal
    final_adjusted_price: Decimal
    final_adjusted_quantity: Decimal
    total_events_applied: int
    input_checksum: str
    output_checksum: str
    lineage: List[AdjustmentLineageStep]
