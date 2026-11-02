"""
M07.07 Portfolio Beta Pydantic Schemas.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.modules.market_risk.beta.models import (
    BetaModelType,
    BetaCalculationMethod,
    StandardErrorMethod,
    BetaRegressionStatus,
)


class BenchmarkReferenceCreate(BaseModel):
    benchmark_code: str = Field(..., max_length=64)
    benchmark_name: str = Field(..., max_length=128)
    instrument_id: Optional[str] = None
    provider: str = "NSE_INDICES"
    market: str = "INDIA"
    currency: str = "INR"
    return_basis: str = "TOTAL_RETURN"


class BenchmarkReferenceResponse(BenchmarkReferenceCreate):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BetaConfigCreate(BaseModel):
    config_name: str = Field(..., max_length=100)
    default_benchmark_id: Optional[str] = None
    model_type: BetaModelType = BetaModelType.OLS_WITH_INTERCEPT
    standard_error_method: StandardErrorMethod = StandardErrorMethod.OLS_CONVENTIONAL
    default_lookback_days: int = Field(60, ge=5, le=2520)
    min_observations: int = Field(20, ge=3, le=500)
    confidence_level: Decimal = Field(Decimal("0.9500"), ge=0.5, le=0.9999)
    description: Optional[str] = None


class BetaConfigResponse(BetaConfigCreate):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SecurityBetaRequest(BaseModel):
    instrument_id: str
    benchmark_id: Optional[str] = None
    benchmark_code: Optional[str] = None
    lookback_days: int = Field(60, ge=5, le=2520)
    as_of: Optional[date] = None
    model_type: BetaModelType = BetaModelType.OLS_WITH_INTERCEPT
    portfolio_id: Optional[str] = None


class SecurityBetaResponse(BaseModel):
    instrument_id: str
    instrument_symbol: str
    benchmark_id: str
    benchmark_code: str
    benchmark_name: str
    as_of_date: datetime
    lookback_days: int
    beta_value: Decimal
    alpha_value: Decimal
    r_squared: Decimal
    adjusted_r_squared: Optional[Decimal] = None
    beta_standard_error: Decimal
    beta_t_statistic: Decimal
    p_value: Optional[Decimal] = None
    ci_lower_95: Optional[Decimal] = None
    ci_upper_95: Optional[Decimal] = None
    residual_std_error: Optional[Decimal] = None
    sample_size: int
    regression_status: BetaRegressionStatus


class AssetBetaContribution(BaseModel):
    asset_id: str
    symbol: str
    weight: Decimal
    individual_beta: Decimal
    beta_contribution: Decimal
    contribution_percentage: Optional[Decimal] = None


class PortfolioBetaRequest(BaseModel):
    portfolio_id: str
    benchmark_id: Optional[str] = None
    benchmark_code: Optional[str] = None
    method: BetaCalculationMethod = BetaCalculationMethod.CURRENT_WEIGHT_IMPLIED
    lookback_days: int = Field(60, ge=5, le=2520)
    as_of: Optional[date] = None
    user_weights: Optional[Dict[str, Decimal]] = None


class PortfolioBetaResponse(BaseModel):
    calculation_code: str
    portfolio_id: str
    benchmark_id: str
    benchmark_code: str
    benchmark_name: str
    as_of_date: datetime
    lookback_days: int
    method: BetaCalculationMethod
    portfolio_beta: Decimal
    portfolio_alpha: Optional[Decimal] = None
    r_squared: Optional[Decimal] = None
    beta_standard_error: Optional[Decimal] = None
    beta_t_statistic: Optional[Decimal] = None
    sample_size: int
    weight_basis: str
    contributions: Optional[List[AssetBetaContribution]] = None
    reconciliation_sum: Optional[Decimal] = None
    reconciliation_discrepancy: Optional[Decimal] = None
    regression_status: BetaRegressionStatus


class DirectVsWeightedBetaReconciliation(BaseModel):
    portfolio_id: str
    benchmark_code: str
    as_of_date: datetime
    direct_beta: Optional[Decimal] = None
    weighted_beta: Decimal
    beta_discrepancy: Optional[Decimal] = None
    direct_r_squared: Optional[Decimal] = None
    explanation: str
