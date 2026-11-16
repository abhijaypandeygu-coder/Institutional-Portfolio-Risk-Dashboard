"""
Pydantic schemas for M11.09 Pre-trade Risk Checks.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ProposedOrderInput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str = Field(..., description="Target portfolio identifier")
    instrument_id: str = Field(..., description="Instrument identifier (e.g., AAPL, RELIANCE)")
    listing_id: str = Field(..., description="Exchange listing identifier")
    exchange: str = Field(..., description="Exchange (e.g., NASDAQ, NYSE, NSE, BSE)")
    side: str = Field(..., description="BUY or SELL")
    quantity: Decimal = Field(..., gt=0, description="Positive proposed quantity")
    order_type: str = Field("LIMIT", description="MARKET, LIMIT, STOP, STOP_LIMIT")
    limit_price: Optional[Decimal] = Field(None, gt=0, description="Limit price for LIMIT orders")
    stop_price: Optional[Decimal] = Field(None, gt=0, description="Stop price for STOP orders")
    time_in_force: str = Field("DAY", description="DAY, IOC, FOK, GTC")
    currency: str = Field("USD", description="Currency of order")
    strategy_id: Optional[str] = Field(None, description="Optional trading strategy identifier")
    submitting_user_id: str = Field(..., description="User or algo account submitting order")
    originating_system: str = Field("ALGO_STRATEGY", description="Submitting system identifier")
    idempotency_key: Optional[str] = Field(None, description="Client idempotency key")


class OrderValidationResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class CheckResultOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    check_name: str
    check_category: str
    check_status: str  # PASS, WARNING, HARD_FAIL, REVIEW_REQUIRED, UNAVAILABLE, STALE
    current_value: Decimal
    projected_value: Decimal
    effective_limit: Optional[Decimal] = None
    utilization_percentage: Decimal
    unit: str
    source_module: str
    reason_code: Optional[str] = None


class SimulationResultOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_nav: Decimal
    projected_nav: Decimal
    current_position_qty: Decimal
    projected_position_qty: Decimal
    position_transition_type: str
    projected_gross_exposure: Decimal
    projected_net_exposure: Decimal
    projected_var: Decimal
    incremental_var: Decimal
    simulation_status: str


class PretradeDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision_id: str
    order_id: str
    order_version: int
    portfolio_id: str
    instrument_id: str
    side: str
    quantity: Decimal
    decision: str  # PASS, REJECT, REVIEW_REQUIRED
    primary_reason_code: str
    reason_summary: str
    evaluated_at: datetime
    expires_at: datetime
    authorization_id: Optional[str] = None
    check_results: List[CheckResultOutput] = Field(default_factory=list)
    simulation: Optional[SimulationResultOutput] = None


class AuthorizationValidationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    is_valid: bool
    authorization_id: str
    status: str
    permitted_instrument_id: str
    permitted_side: str
    permitted_quantity: Decimal
    expires_at: datetime
    message: str


class PretradeDashboardSummary(BaseModel):
    total_orders_evaluated: int
    pass_count: int
    reject_count: int
    review_required_count: int
    pass_percentage: Decimal
    reject_percentage: Decimal
    active_reservations_count: int
    active_authorizations_count: int
    rejection_reasons_breakdown: Dict[str, int]

