"""Centralized Dataset Registry for M14.06 Export Engine.

Registers all supported datasets, their fields, types, units, precision, sensitivity,
and supported export formats across M05, M06, M07, M08, M09, M10, M11, M12, M13, and M14.
"""

from typing import Dict, Any, List, Optional
from backend.app.modules.reporting_attribution_audit.export_engine.models.export_models import (
    ExportFormat,
    SensitivityLevel,
)

DATASET_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    # M14.01 Daily Risk Reports
    "daily_risk_positions": {
        "dataset_code": "daily_risk_positions",
        "dataset_name": "Daily Risk Report Positions",
        "source_module": "M14",
        "source_feature": "M14.01",
        "description": "Position-level risk valuations, sensitivities, and factor betas from daily reports.",
        "schema_version": "v1.0",
        "supported_formats": [ExportFormat.CSV, ExportFormat.XLSX, ExportFormat.PDF],
        "access_policy_reference": "PORTFOLIO_RISK_READ",
        "maximum_rows": 50000,
        "fields": [
            {"field_name": "instrument_id", "display_name": "Instrument ID", "data_type": "STRING", "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": False, "is_exportable": True, "field_order": 1},
            {"field_name": "symbol", "display_name": "Symbol", "data_type": "STRING", "sensitivity_level": SensitivityLevel.PUBLIC, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 2},
            {"field_name": "exchange", "display_name": "Exchange", "data_type": "STRING", "sensitivity_level": SensitivityLevel.PUBLIC, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 3},
            {"field_name": "quantity", "display_name": "Quantity", "data_type": "NUMERIC", "unit": "SHARES", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 4},
            {"field_name": "market_value", "display_name": "Market Value", "data_type": "NUMERIC", "currency_semantics": "BASE_CURRENCY", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 5},
            {"field_name": "weight_pct", "display_name": "Portfolio Weight %", "data_type": "NUMERIC", "unit": "PERCENT", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": False, "is_selectable": True, "is_exportable": True, "field_order": 6},
            {"field_name": "var_contribution", "display_name": "VaR Contribution", "data_type": "NUMERIC", "currency_semantics": "BASE_CURRENCY", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": False, "is_selectable": True, "is_exportable": True, "field_order": 7},
            {"field_name": "currency", "display_name": "Currency", "data_type": "STRING", "sensitivity_level": SensitivityLevel.PUBLIC, "is_required": True, "is_selectable": False, "is_exportable": True, "field_order": 8},
        ],
    },
    # M14.02 Performance Reports
    "portfolio_performance_series": {
        "dataset_code": "portfolio_performance_series",
        "dataset_name": "Portfolio Historical Performance Series",
        "source_module": "M14",
        "source_feature": "M14.02",
        "description": "Daily TWR and MWR return series, P&L, benchmark returns, and cash flows.",
        "schema_version": "v1.0",
        "supported_formats": [ExportFormat.CSV, ExportFormat.XLSX, ExportFormat.PDF],
        "access_policy_reference": "PORTFOLIO_PERFORMANCE_READ",
        "maximum_rows": 25000,
        "fields": [
            {"field_name": "date", "display_name": "Date", "data_type": "DATE", "sensitivity_level": SensitivityLevel.PUBLIC, "is_required": True, "is_selectable": False, "is_exportable": True, "field_order": 1},
            {"field_name": "portfolio_nav", "display_name": "Portfolio NAV", "data_type": "NUMERIC", "currency_semantics": "BASE_CURRENCY", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 2},
            {"field_name": "daily_pnl", "display_name": "Daily P&L", "data_type": "NUMERIC", "currency_semantics": "BASE_CURRENCY", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 3},
            {"field_name": "daily_return_pct", "display_name": "Daily Return %", "data_type": "NUMERIC", "unit": "PERCENT", "precision": 4, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 4},
            {"field_name": "cumulative_return_pct", "display_name": "Cumulative Return %", "data_type": "NUMERIC", "unit": "PERCENT", "precision": 4, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 5},
            {"field_name": "benchmark_return_pct", "display_name": "Benchmark Return %", "data_type": "NUMERIC", "unit": "PERCENT", "precision": 4, "sensitivity_level": SensitivityLevel.PUBLIC, "is_required": False, "is_selectable": True, "is_exportable": True, "field_order": 6},
            {"field_name": "external_cash_flow", "display_name": "External Cash Flow", "data_type": "NUMERIC", "currency_semantics": "BASE_CURRENCY", "precision": 2, "sensitivity_level": SensitivityLevel.CONFIDENTIAL, "is_required": False, "is_selectable": True, "is_exportable": True, "field_order": 7},
        ],
    },
    # M14.03 Risk Attribution
    "risk_attribution_positions": {
        "dataset_code": "risk_attribution_positions",
        "dataset_name": "Risk Attribution Positions & Factors",
        "source_module": "M14",
        "source_feature": "M14.03",
        "description": "Multi-level risk attribution showing marginal, component, and percentage contributions to total risk.",
        "schema_version": "v1.0",
        "supported_formats": [ExportFormat.CSV, ExportFormat.XLSX, ExportFormat.PDF],
        "access_policy_reference": "PORTFOLIO_RISK_READ",
        "maximum_rows": 20000,
        "fields": [
            {"field_name": "instrument_id", "display_name": "Instrument ID", "data_type": "STRING", "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": False, "is_exportable": True, "field_order": 1},
            {"field_name": "symbol", "display_name": "Symbol", "data_type": "STRING", "sensitivity_level": SensitivityLevel.PUBLIC, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 2},
            {"field_name": "sector", "display_name": "Sector", "data_type": "STRING", "sensitivity_level": SensitivityLevel.PUBLIC, "is_required": False, "is_selectable": True, "is_exportable": True, "field_order": 3},
            {"field_name": "position_market_value", "display_name": "Market Value", "data_type": "NUMERIC", "currency_semantics": "BASE_CURRENCY", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 4},
            {"field_name": "marginal_risk", "display_name": "Marginal Risk", "data_type": "NUMERIC", "precision": 4, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": False, "is_selectable": True, "is_exportable": True, "field_order": 5},
            {"field_name": "component_risk", "display_name": "Component Risk", "data_type": "NUMERIC", "currency_semantics": "BASE_CURRENCY", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 6},
            {"field_name": "percent_contribution", "display_name": "% Risk Contribution", "data_type": "NUMERIC", "unit": "PERCENT", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 7},
        ],
    },
    # M14.04 Stress Testing
    "stress_testing_results": {
        "dataset_code": "stress_testing_results",
        "dataset_name": "Stress Testing Scenario Results",
        "source_module": "M14",
        "source_feature": "M14.04",
        "description": "Historical, hypothetical, and factor shock scenario outcomes and stressed P&L impacts.",
        "schema_version": "v1.0",
        "supported_formats": [ExportFormat.CSV, ExportFormat.XLSX, ExportFormat.PDF],
        "access_policy_reference": "PORTFOLIO_RISK_READ",
        "maximum_rows": 10000,
        "fields": [
            {"field_name": "scenario_id", "display_name": "Scenario ID", "data_type": "STRING", "sensitivity_level": SensitivityLevel.PUBLIC, "is_required": True, "is_selectable": False, "is_exportable": True, "field_order": 1},
            {"field_name": "scenario_name", "display_name": "Scenario Name", "data_type": "STRING", "sensitivity_level": SensitivityLevel.PUBLIC, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 2},
            {"field_name": "scenario_category", "display_name": "Category", "data_type": "STRING", "sensitivity_level": SensitivityLevel.PUBLIC, "is_required": False, "is_selectable": True, "is_exportable": True, "field_order": 3},
            {"field_name": "baseline_nav", "display_name": "Baseline NAV", "data_type": "NUMERIC", "currency_semantics": "BASE_CURRENCY", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 4},
            {"field_name": "stressed_nav", "display_name": "Stressed NAV", "data_type": "NUMERIC", "currency_semantics": "BASE_CURRENCY", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 5},
            {"field_name": "stressed_pnl", "display_name": "Stressed P&L", "data_type": "NUMERIC", "currency_semantics": "BASE_CURRENCY", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 6},
            {"field_name": "pnl_impact_pct", "display_name": "P&L Impact %", "data_type": "NUMERIC", "unit": "PERCENT", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 7},
        ],
    },
    # M14.05 Liquidity Reports
    "liquidity_positions_and_costs": {
        "dataset_code": "liquidity_positions_and_costs",
        "dataset_name": "Liquidity Profiles & Exit Cost Estimates",
        "source_module": "M14",
        "source_feature": "M14.05",
        "description": "Instrument spread, depth, volume, directional liquidation time (days) and non-overlapping cost breakdowns.",
        "schema_version": "v1.0",
        "supported_formats": [ExportFormat.CSV, ExportFormat.XLSX, ExportFormat.PDF],
        "access_policy_reference": "PORTFOLIO_LIQUIDITY_READ",
        "maximum_rows": 20000,
        "fields": [
            {"field_name": "instrument_id", "display_name": "Instrument ID", "data_type": "STRING", "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": False, "is_exportable": True, "field_order": 1},
            {"field_name": "symbol", "display_name": "Symbol", "data_type": "STRING", "sensitivity_level": SensitivityLevel.PUBLIC, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 2},
            {"field_name": "exchange", "display_name": "Exchange", "data_type": "STRING", "sensitivity_level": SensitivityLevel.PUBLIC, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 3},
            {"field_name": "position_quantity", "display_name": "Quantity", "data_type": "NUMERIC", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 4},
            {"field_name": "market_value", "display_name": "Market Value", "data_type": "NUMERIC", "currency_semantics": "BASE_CURRENCY", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 5},
            {"field_name": "spread_bps", "display_name": "Spread (bps)", "data_type": "NUMERIC", "unit": "BPS", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 6},
            {"field_name": "liquidation_direction", "display_name": "Execution Side", "data_type": "STRING", "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 7},
            {"field_name": "estimated_duration_days", "display_name": "Duration (Days)", "data_type": "NUMERIC", "unit": "DAYS", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 8},
            {"field_name": "estimated_total_cost", "display_name": "Total Cost", "data_type": "NUMERIC", "currency_semantics": "BASE_CURRENCY", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 9},
            {"field_name": "cost_bps", "display_name": "Cost (bps)", "data_type": "NUMERIC", "unit": "BPS", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 10},
        ],
    },
    # M11 Risk Limits & Alerts
    "risk_limits_and_breaches": {
        "dataset_code": "risk_limits_and_breaches",
        "dataset_name": "Risk Limit Utilization & Breach Evaluations",
        "source_module": "M11",
        "source_feature": "M11.02",
        "description": "Active risk limits, threshold values, current utilizations, and evaluation statuses.",
        "schema_version": "v1.0",
        "supported_formats": [ExportFormat.CSV, ExportFormat.XLSX, ExportFormat.PDF],
        "access_policy_reference": "RISK_LIMITS_READ",
        "maximum_rows": 5000,
        "fields": [
            {"field_name": "limit_code", "display_name": "Limit Code", "data_type": "STRING", "sensitivity_level": SensitivityLevel.PUBLIC, "is_required": True, "is_selectable": False, "is_exportable": True, "field_order": 1},
            {"field_name": "limit_name", "display_name": "Limit Name", "data_type": "STRING", "sensitivity_level": SensitivityLevel.PUBLIC, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 2},
            {"field_name": "metric_name", "display_name": "Metric", "data_type": "STRING", "sensitivity_level": SensitivityLevel.PUBLIC, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 3},
            {"field_name": "configured_threshold", "display_name": "Threshold", "data_type": "NUMERIC", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 4},
            {"field_name": "current_value", "display_name": "Current Value", "data_type": "NUMERIC", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 5},
            {"field_name": "utilization_pct", "display_name": "Utilization %", "data_type": "NUMERIC", "unit": "PERCENT", "precision": 2, "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 6},
            {"field_name": "evaluation_status", "display_name": "Status", "data_type": "STRING", "sensitivity_level": SensitivityLevel.INTERNAL, "is_required": True, "is_selectable": True, "is_exportable": True, "field_order": 7},
        ],
    },
}
