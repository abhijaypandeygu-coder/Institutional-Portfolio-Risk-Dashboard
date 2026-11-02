"""
M08.01 Factor Definition Pydantic Schemas.
Request and response models for factor definitions, versions, characteristics,
factor models, memberships, and governance approvals.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.factor_risk.factor_definition.models import (
    FactorFamily,
    FactorType,
    ConstructionType,
    FactorLifecycleStatus,
    CharacteristicDirection,
    StandardizationMethod,
    WeightingMethodology,
    RebalancingFrequency,
    MarketScope,
)


class CharacteristicItemSchema(BaseModel):
    characteristic_code: str
    characteristic_name: str
    source_field_reference: str
    formula_specification: str
    unit: str = "RATIO"
    characteristic_direction: CharacteristicDirection
    standardization_method: StandardizationMethod = StandardizationMethod.CROSS_SECTIONAL_Z_SCORE
    winsorization_pct: Decimal = Decimal("0.0100")
    component_weight: Decimal = Decimal("1.0000")
    missing_data_policy: str = "EXCLUDE_OR_AVERAGE_REMAINING"
    model_config = ConfigDict(from_attributes=True)


class FactorDefinitionVersionResponse(BaseModel):
    version_id: str
    factor_id: str
    version_number: int
    market_scope: MarketScope
    currency: str
    frequency: str
    return_type: str
    return_direction: str
    construction_specification: Dict[str, Any]
    source_metadata: Optional[Dict[str, Any]] = None
    definition_hash: str
    approval_status: FactorLifecycleStatus
    effective_from: date
    effective_to: Optional[date] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    change_rationale: Optional[str] = None
    created_at: datetime
    characteristics: List[CharacteristicItemSchema] = []
    model_config = ConfigDict(from_attributes=True)


class FactorDefinitionResponse(BaseModel):
    factor_id: str
    factor_code: str
    factor_name: str
    factor_family: FactorFamily
    factor_type: FactorType
    description: str
    economic_interpretation: str
    construction_type: ConstructionType
    current_version_number: int
    lifecycle_status: FactorLifecycleStatus
    latest_version: Optional[FactorDefinitionVersionResponse] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CreateFactorDefinitionRequest(BaseModel):
    factor_code: str = Field(..., max_length=32, description="Unique uppercase factor code (e.g. MKT, SMB, HML, MOM, QMJ)")
    factor_name: str = Field(..., max_length=128)
    factor_family: FactorFamily
    factor_type: FactorType
    description: str
    economic_interpretation: str
    construction_type: ConstructionType
    market_scope: MarketScope = MarketScope.INDIA
    currency: str = "INR"
    frequency: str = "DAILY"
    return_type: str = "LOGARITHMIC"
    construction_specification: Dict[str, Any]
    source_metadata: Optional[Dict[str, Any]] = None
    characteristics: Optional[List[CharacteristicItemSchema]] = None
    change_rationale: Optional[str] = "Initial factor registration"
    model_config = ConfigDict(from_attributes=True)


class CreateFactorVersionRequest(BaseModel):
    market_scope: MarketScope = MarketScope.INDIA
    currency: str = "INR"
    frequency: str = "DAILY"
    return_type: str = "LOGARITHMIC"
    construction_specification: Dict[str, Any]
    source_metadata: Optional[Dict[str, Any]] = None
    characteristics: Optional[List[CharacteristicItemSchema]] = None
    change_rationale: str = Field(..., description="Mandatory rationale for methodology modification")
    model_config = ConfigDict(from_attributes=True)


class GovernanceActionRequest(BaseModel):
    action: str = Field(..., description="SUBMIT, APPROVE, REJECT, ACTIVATE, DEPRECATE")
    actor: str = Field("RISK_OFFICER", description="User identity performing action")
    rationale: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# Factor Model Schemas
class FactorModelMemberSchema(BaseModel):
    factor_position: int
    factor_id: str
    version_id: str
    factor_code: str
    model_config = ConfigDict(from_attributes=True)


class FactorModelVersionResponse(BaseModel):
    model_version_id: str
    model_id: str
    version_number: int
    model_definition_hash: str
    approval_status: FactorLifecycleStatus
    effective_from: date
    effective_to: Optional[date] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    memberships: List[FactorModelMemberSchema] = []
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FactorModelResponse(BaseModel):
    model_id: str
    model_code: str
    model_name: str
    description: str
    market_scope: MarketScope
    currency_basis: str
    return_frequency: str
    lifecycle_status: FactorLifecycleStatus
    current_version_number: int
    latest_version: Optional[FactorModelVersionResponse] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CreateFactorModelRequest(BaseModel):
    model_code: str = Field(..., max_length=64, description="Unique model code (e.g. FF3_INDIA, FF5_US)")
    model_name: str = Field(..., max_length=128)
    description: str
    market_scope: MarketScope = MarketScope.INDIA
    currency_basis: str = "INR"
    return_frequency: str = "DAILY"
    factor_version_ids: List[str] = Field(
        ..., min_length=1, description="Ordered list of pinned factor definition version IDs"
    )
    change_rationale: Optional[str] = "Initial model specification"
    model_config = ConfigDict(from_attributes=True)

