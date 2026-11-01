"""Pydantic 2.x Schemas for M05.06 - Portfolio Reconciliation."""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.portfolio_management.portfolio_reconciliation.models import (
    ProviderType,
    StatementType,
    ImportStatus,
    ReconciliationType,
    ReconciliationRunStatus,
    BreakCategory,
    BreakSeverity,
    BreakStatus,
    ResolutionType,
)


# ---------------------------------------------------------------------------
# PROVIDERS
# ---------------------------------------------------------------------------

class ProviderCreate(BaseModel):
    provider_name: str = Field(..., max_length=128)
    provider_type: ProviderType = ProviderType.BROKER
    provider_code: str = Field(..., max_length=32)


class ProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider_id: str
    provider_name: str
    provider_type: ProviderType
    provider_code: str
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# STATEMENT IMPORTS
# ---------------------------------------------------------------------------

class ExternalPositionItem(BaseModel):
    external_symbol: str
    quantity: Decimal
    position_side: str = "LONG"
    price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    currency: str = "USD"


class ExternalTransactionItem(BaseModel):
    external_trade_id: str
    external_symbol: str
    trade_side: str  # BUY, SELL
    quantity: Decimal
    price: Decimal
    gross_amount: Decimal
    fees: Decimal = Decimal("0.000000")
    currency: str = "USD"
    trade_date: date
    settlement_date: Optional[date] = None


class ExternalCashItem(BaseModel):
    currency: str
    closing_balance: Decimal


class StatementImportCreate(BaseModel):
    provider_code: str
    statement_type: StatementType
    portfolio_id: str
    account_id: str
    as_of_date: date
    file_name: str
    positions: Optional[List[ExternalPositionItem]] = None
    transactions: Optional[List[ExternalTransactionItem]] = None
    cash_records: Optional[List[ExternalCashItem]] = None


class StatementImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    statement_id: str
    provider_code: str
    statement_type: StatementType
    portfolio_id: str
    account_id: str
    as_of_date: date
    file_name: str
    file_hash: str
    import_status: ImportStatus
    total_records: int
    valid_records: int
    invalid_records: int
    created_at: datetime
    completed_at: Optional[datetime]


# ---------------------------------------------------------------------------
# RECONCILIATION RUNS
# ---------------------------------------------------------------------------

class ReconciliationRunCreate(BaseModel):
    portfolio_id: str
    account_id: str
    provider_code: str
    reconciliation_type: ReconciliationType = ReconciliationType.FULL_PORTFOLIO
    as_of_date: date
    statement_id: Optional[str] = None


class ReconciliationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    portfolio_id: str
    account_id: str
    provider_code: str
    reconciliation_type: ReconciliationType
    as_of_date: date
    statement_id: Optional[str]
    status: ReconciliationRunStatus
    total_external_records: int
    total_internal_records: int
    matched_records: int
    unmatched_records: int
    break_count: int
    critical_break_count: int
    started_at: datetime
    completed_at: Optional[datetime]
    created_at: datetime


# ---------------------------------------------------------------------------
# RECONCILIATION BREAKS & WORKFLOW
# ---------------------------------------------------------------------------

class BreakNoteCreate(BaseModel):
    author_id: str = "ANALYST"
    note_content: str = Field(..., min_length=3)


class BreakNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    note_id: str
    break_id: str
    author_id: str
    note_content: str
    created_at: datetime


class BreakAssignRequest(BaseModel):
    assigned_to: str


class BreakResolveRequest(BaseModel):
    resolution_type: ResolutionType
    resolution_explanation: str
    root_cause: Optional[str] = None


class ReconciliationBreakResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    break_id: str
    run_id: str
    portfolio_id: str
    account_id: str
    instrument_id: Optional[str]
    break_category: BreakCategory
    severity: BreakSeverity
    break_status: BreakStatus
    internal_value: str
    external_value: str
    difference_value: Decimal
    difference_unit: str
    assigned_to: Optional[str]
    root_cause: Optional[str]
    resolution_type: Optional[ResolutionType]
    resolution_explanation: Optional[str]
    detected_at: datetime
    resolved_at: Optional[datetime]
    closed_at: Optional[datetime]
    created_at: datetime
    notes: List[BreakNoteResponse] = []

