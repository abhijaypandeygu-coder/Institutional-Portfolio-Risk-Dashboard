"""
M10.05 Correlation Shock Schemas Package.
"""
from backend.app.modules.scenario_analysis.correlation_shock.schemas.correlation_schemas import (
    PairRuleCreate,
    PairRuleResponse,
    ScopeMemberCreate,
    ScopeMemberResponse,
    CorrelationShockScenarioCreate,
    CorrelationShockScenarioResponse,
    MatrixValidateRequest,
    MatrixValidateResponse,
    ExecuteScenarioRequest,
    RiskContributionItem,
    RiskResultSummary,
    ExecutionResponse,
)

__all__ = [
    "PairRuleCreate",
    "PairRuleResponse",
    "ScopeMemberCreate",
    "ScopeMemberResponse",
    "CorrelationShockScenarioCreate",
    "CorrelationShockScenarioResponse",
    "MatrixValidateRequest",
    "MatrixValidateResponse",
    "ExecuteScenarioRequest",
    "RiskContributionItem",
    "RiskResultSummary",
    "ExecutionResponse",
]
