"""
M05.08 Multi-Portfolio Management Schemas.
Pydantic contracts for groups, membership, hierarchy, shared settings/overrides,
consolidation requests, consolidated holdings, exposures, cash, and snapshots.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from backend.app.modules.portfolio_management.multi_portfolio_management.models import (
    GroupType,
    GroupStatus,
    MembershipRole,
    MembershipStatus,
    ConsolidationStatus,
)


# ==========================================
# Group Schemas
# ==========================================

class PortfolioGroupCreateRequest(BaseModel):
    group_code: str
    group_name: str
    description: Optional[str] = None
    group_type: GroupType = GroupType.CUSTOM
    parent_group_id: Optional[str] = None
    owner_reference: str
    organization_reference: Optional[str] = None
    reporting_currency: str = "USD"
    primary_benchmark_reference: Optional[str] = None
    shared_risk_convention: Optional[str] = None


class PortfolioGroupUpdateRequest(BaseModel):
    group_name: Optional[str] = None
    description: Optional[str] = None
    group_type: Optional[GroupType] = None
    parent_group_id: Optional[str] = None
    owner_reference: Optional[str] = None
    organization_reference: Optional[str] = None
    reporting_currency: Optional[str] = None
    primary_benchmark_reference: Optional[str] = None
    shared_risk_convention: Optional[str] = None
    status: Optional[GroupStatus] = None


class PortfolioGroupResponse(BaseModel):
    id: str
    group_code: str
    group_name: str
    description: Optional[str] = None
    group_type: str
    parent_group_id: Optional[str] = None
    owner_reference: str
    organization_reference: Optional[str] = None
    reporting_currency: str
    primary_benchmark_reference: Optional[str] = None
    shared_risk_convention: Optional[str] = None
    status: str
    current_version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ==========================================
# Membership Schemas
# ==========================================

class PortfolioGroupMembershipAddRequest(BaseModel):
    portfolio_id: str
    membership_role: MembershipRole = MembershipRole.MEMBER
    include_in_positions: bool = True
    include_in_valuation: bool = True
    include_in_cash: bool = True
    include_in_contribution: bool = True
    include_in_risk_inputs: bool = True
    reporting_weight: Optional[Decimal] = None
    effective_from: Optional[datetime] = None
    approval_reference: Optional[str] = None


class PortfolioGroupMembershipUpdateRequest(BaseModel):
    membership_role: Optional[MembershipRole] = None
    membership_status: Optional[MembershipStatus] = None
    include_in_positions: Optional[bool] = None
    include_in_valuation: Optional[bool] = None
    include_in_cash: Optional[bool] = None
    include_in_contribution: Optional[bool] = None
    include_in_risk_inputs: Optional[bool] = None
    reporting_weight: Optional[Decimal] = None
    effective_to: Optional[datetime] = None


class PortfolioGroupMembershipResponse(BaseModel):
    id: str
    group_id: str
    portfolio_id: str
    membership_role: str
    membership_status: str
    include_in_positions: bool
    include_in_valuation: bool
    include_in_cash: bool
    include_in_contribution: bool
    include_in_risk_inputs: bool
    reporting_weight: Optional[Decimal] = None
    effective_from: datetime
    effective_to: Optional[datetime] = None
    recorded_from: datetime
    recorded_to: Optional[datetime] = None
    membership_version: int
    approval_reference: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PortfolioGroupMembershipEventResponse(BaseModel):
    id: str
    group_id: str
    portfolio_id: str
    membership_id: str
    event_type: str
    previous_status: Optional[str] = None
    new_status: str
    effective_at: datetime
    recorded_at: datetime
    actor_id: str
    reason: Optional[str] = None
    membership_version: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ==========================================
# Shared Policies & Overrides
# ==========================================

class PortfolioGroupPolicyCreateRequest(BaseModel):
    policy_name: str
    reporting_currency: str = "USD"
    benchmark_reference: Optional[str] = None
    risk_convention_reference: Optional[str] = None
    valuation_policy_reference: Optional[str] = None
    calendar_reference: Optional[str] = None
    return_convention_reference: Optional[str] = None
    exposure_aggregation_policy: str = "CANONICAL_INSTRUMENT"
    configuration_payload: Optional[Dict[str, Any]] = None
    effective_from: Optional[datetime] = None


class PortfolioGroupPolicyResponse(BaseModel):
    id: str
    group_id: str
    policy_name: str
    reporting_currency: str
    benchmark_reference: Optional[str] = None
    risk_convention_reference: Optional[str] = None
    valuation_policy_reference: Optional[str] = None
    calendar_reference: Optional[str] = None
    return_convention_reference: Optional[str] = None
    exposure_aggregation_policy: str
    configuration_payload: Optional[Dict[str, Any]] = None
    effective_from: datetime
    effective_to: Optional[datetime] = None
    policy_version: int
    approval_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PortfolioGroupOverrideCreateRequest(BaseModel):
    portfolio_id: str
    setting_type: str
    override_reference: str
    override_value: Optional[str] = None
    effective_from: Optional[datetime] = None


class PortfolioGroupOverrideResponse(BaseModel):
    id: str
    group_id: str
    portfolio_id: str
    setting_type: str
    override_reference: str
    override_value: Optional[str] = None
    effective_from: datetime
    effective_to: Optional[datetime] = None
    override_version: int
    approval_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ResolvedGroupSettingResponse(BaseModel):
    group_id: str
    portfolio_id: Optional[str] = None
    setting_key: str
    effective_value: str
    source_level: str  # PORTFOLIO_OVERRIDE, GROUP_POLICY, or SYSTEM_DEFAULT
    policy_version: int
    is_override: bool
    explanation: str


# ==========================================
# Lineage & Consolidated Holdings
# ==========================================

class HoldingContributorResponse(BaseModel):
    id: str
    portfolio_id: str
    account_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    position_side: str
    signed_quantity: Decimal
    market_value_native: Decimal
    market_value_reporting_currency: Decimal
    currency: str
    fx_rate_applied: Decimal
    source_snapshot_id: Optional[str] = None

    model_config = {"from_attributes": True}


class ConsolidatedHoldingResponse(BaseModel):
    id: str
    group_id: str
    instrument_id: str
    listing_id: Optional[str] = None
    native_currency: str
    gross_long_quantity: Decimal
    gross_short_quantity: Decimal
    net_signed_quantity: Decimal
    gross_long_market_value: Decimal
    gross_short_market_value: Decimal
    net_market_value: Decimal
    reporting_currency_value: Decimal
    contributing_portfolio_count: int
    contributing_account_count: int
    valuation_status: str
    contributors: List[HoldingContributorResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ConsolidatedCashSummaryResponse(BaseModel):
    id: str
    group_id: str
    currency: str
    settled_cash: Decimal
    unsettled_receivables: Decimal
    unsettled_payables: Decimal
    reserved_cash: Decimal
    restricted_cash: Decimal
    available_cash: Decimal
    reporting_currency_equivalent: Decimal
    contributing_account_count: int
    completeness_status: str

    model_config = {"from_attributes": True}


# ==========================================
# Consolidation Run & Exposure Views
# ==========================================

class ConsolidationRunExecuteRequest(BaseModel):
    effective_as_of: Optional[datetime] = None
    knowledge_as_of: Optional[datetime] = None
    reporting_currency: Optional[str] = None
    consolidation_policy_version: str = "CONS-POL-V1"
    fx_rates_to_reporting: Dict[str, Decimal] = Field(default_factory=dict)  # Currency -> FX Rate to Reporting


class ConsolidationRunResponse(BaseModel):
    id: str
    group_id: str
    group_version: int
    membership_version: int
    consolidation_type: str
    effective_as_of: datetime
    knowledge_as_of: datetime
    reporting_currency: str
    consolidation_policy_version: str
    included_portfolio_count: int
    excluded_portfolio_count: int
    distinct_instrument_count: int
    total_gross_long_market_value: Decimal
    total_gross_short_market_value: Decimal
    total_gross_exposure: Decimal
    total_net_exposure: Decimal
    run_status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    input_manifest_hash: str
    created_at: datetime
    holdings: List[ConsolidatedHoldingResponse] = Field(default_factory=list)
    cash_summaries: List[ConsolidatedCashSummaryResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class GroupExposureSummaryResponse(BaseModel):
    group_id: str
    reporting_currency: str
    effective_as_of: datetime
    total_gross_long_market_value: Decimal
    total_gross_short_market_value: Decimal
    total_gross_exposure: Decimal
    total_net_exposure: Decimal
    total_net_quantity_by_instrument: Dict[str, Decimal]
    portfolio_contributions: Dict[str, Decimal]  # portfolio_id -> net market value in reporting currency
    analytical_netting_disclaimer: str = (
        "ANALYTICAL NETTING ONLY: Net positions and exposure figures represent cross-portfolio analytical aggregations "
        "and do NOT constitute legal, contractual, or settlement netting instructions."
    )


class PortfolioGroupSnapshotResponse(BaseModel):
    id: str
    group_id: str
    consolidation_run_id: str
    group_version: int
    membership_version: int
    effective_as_of: datetime
    knowledge_as_of: datetime
    reporting_currency: str
    source_snapshot_references: Dict[str, Any]
    policy_version_manifest: Dict[str, Any]
    snapshot_status: str
    snapshot_hash: str
    supersedes_snapshot_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class GroupComparisonResponse(BaseModel):
    target_group_id_1: str
    target_group_id_2: str
    reporting_currency: str
    comparison_timestamp: datetime
    group_1_net_exposure: Decimal
    group_2_net_exposure: Decimal
    net_exposure_difference: Decimal
    overlapping_portfolios: List[str]
    distinct_portfolios_group_1: List[str]
    distinct_portfolios_group_2: List[str]
