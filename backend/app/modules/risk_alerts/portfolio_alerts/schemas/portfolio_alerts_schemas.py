"""
Pydantic schemas for M12.04 Portfolio Alerts.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class PortfolioAlertRuleCreate(BaseModel):
    rule_code: str = Field(..., max_length=64)
    portfolio_id: Optional[str] = None
    portfolio_group_id: Optional[str] = None
    rule_name: str = Field(..., max_length=255)
    description: Optional[str] = None
    category: str = Field(..., description="PORTFOLIO_LOSS, CONCENTRATION, POSITION_MOVEMENT, CASH_MOVEMENT, RECONCILIATION_BREAK")
    event_type: str = Field(..., description="INTRADAY_LOSS, PERIOD_LOSS, INSTRUMENT_CONCENTRATION, SECTOR_CONCENTRATION, UNUSUAL_POSITION_CHANGE, CASH_WITHDRAWAL, RECONCILIATION_BREAK")
    metric_name: str
    operator: str = Field(default="GTE")
    threshold_value: Decimal
    threshold_currency: str = Field(default="INR")
    threshold_unit: str = Field(default="PERCENT_NAV")
    baseline_type: str = Field(default="PREVIOUS_CLOSE")
    evaluation_interval: str = Field(default="5m")
    persistence_count: int = Field(default=1)
    cooldown_seconds: int = Field(default=300)
    severity_preference: str = Field(default="HIGH")
    created_by: str = Field(default="SYSTEM")


class PortfolioAlertRuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    description: Optional[str] = None
    threshold_value: Optional[Decimal] = None
    threshold_unit: Optional[str] = None
    cooldown_seconds: Optional[int] = None
    enabled: Optional[bool] = None
    change_reason: str = Field(default="Rule update")
    changed_by: str = Field(default="SYSTEM")


class PortfolioAlertRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rule_code: str
    portfolio_id: Optional[str]
    rule_name: str
    description: Optional[str]
    category: str
    event_type: str
    metric_name: str
    operator: str
    threshold_value: Decimal
    threshold_currency: str
    threshold_unit: str
    baseline_type: str
    rule_version: int
    enabled: bool
    created_at: datetime
    created_by: str


class PortfolioLossEvaluationRequest(BaseModel):
    rule_code: str
    portfolio_id: str
    current_valuation: Decimal
    reference_valuation: Decimal
    reference_nav: Optional[Decimal] = None
    currency: str = "INR"
    instrument_pnls: Dict[str, Decimal] = Field(default_factory=dict)
    event_timestamp: datetime
    quality_status: str = "VALID"
    source_snapshot_id: Optional[str] = None


class ConcentrationEvaluationRequest(BaseModel):
    rule_code: str
    portfolio_id: str
    entity_key: str  # e.g., instrument_id or sector_name
    current_weight: Decimal  # e.g. 0.28 for 28%
    baseline_weight: Decimal  # e.g. 0.15 for 15%
    hhi_weights: Optional[List[Decimal]] = None
    event_timestamp: datetime
    quality_status: str = "VALID"


class PositionMovementEvaluationRequest(BaseModel):
    rule_code: str
    portfolio_id: str
    instrument_id: str
    current_quantity: Decimal
    prior_quantity: Decimal
    current_notional: Optional[Decimal] = None
    reference_nav: Optional[Decimal] = None
    event_timestamp: datetime
    quality_status: str = "VALID"
    source_transaction_id: Optional[str] = None


class CashMovementEvaluationRequest(BaseModel):
    rule_code: str
    portfolio_id: str
    current_cash: Decimal
    prior_cash: Decimal
    movement_type: str = "WITHDRAWAL"  # WITHDRAWAL, DEPOSIT, FEE, TRANSFER
    reference_nav: Optional[Decimal] = None
    currency: str = "INR"
    event_timestamp: datetime
    quality_status: str = "VALID"


class ReconciliationBreakEvaluationRequest(BaseModel):
    rule_code: str
    portfolio_id: str
    reconciliation_break_id: str  # From M05.06
    break_category: str = "POSITION_QUANTITY"  # POSITION_QUANTITY, CASH_BALANCE, VALUATION
    internal_value: Decimal
    external_value: Decimal
    reference_value: Optional[Decimal] = None
    currency: str = "INR"
    event_timestamp: datetime
    quality_status: str = "VALID"


class PortfolioEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    evidence_type: str
    metric_name: str
    observed_value: Decimal
    baseline_value: Optional[Decimal]
    threshold_value: Optional[Decimal]
    unit: str
    currency: str
    source_reference: Optional[str]
    methodology_version: str
    evidence_payload: Dict[str, Any]
    created_at: datetime


class PortfolioAlertEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_code: str
    portfolio_id: str
    category: str
    event_type: str
    observed_value: Decimal
    baseline_value: Optional[Decimal]
    threshold_value: Decimal
    delta_value: Optional[Decimal]
    currency: str
    source_module: str
    source_record_id: Optional[str]
    event_timestamp: datetime
    detected_at: datetime
    last_updated_at: datetime
    event_state: str
    event_fingerprint: str
    evidence_summary: str
    evidence_items: List[PortfolioEvidenceResponse] = Field(default_factory=list)


class PortfolioAlertOverviewResponse(BaseModel):
    portfolio_id: Optional[str]
    total_portfolio_alerts: int
    active_alerts: int
    loss_alerts_count: int
    concentration_alerts_count: int
    position_alerts_count: int
    cash_alerts_count: int
    reconciliation_alerts_count: int
    timestamp: datetime

