"""
M13.10 — Central Widget Registry.

Defines all registered widgets provided by M13.01–M13.09 with their:
- Unique widget ID and display name
- Owning module reference
- Supported metrics and display fields
- Allowed visualization types
- Min/Max layout dimensions (12-column grid system)
- Default configuration schema
- Required permission tags
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class WidgetDimensionBounds(BaseModel):
    min_width: int = Field(2, ge=1, le=12)
    max_width: int = Field(12, ge=1, le=12)
    default_width: int = Field(6, ge=1, le=12)
    min_height: int = Field(2, ge=1, le=12)
    max_height: int = Field(12, ge=1, le=12)
    default_height: int = Field(4, ge=1, le=12)


class WidgetDefinition(BaseModel):
    widget_id: str
    name: str
    owning_module: str
    category: str
    description: str
    supported_metrics: List[str]
    supported_visualization_types: List[str]
    default_visualization_type: str
    dimension_bounds: WidgetDimensionBounds
    default_configuration: Dict[str, Any]
    allow_multiple_instances: bool = True
    required_permissions: List[str] = Field(default_factory=list)
    version: str = "1.0.0"


# Central Institutional Widget Registry Definitions
REGISTERED_WIDGETS: Dict[str, WidgetDefinition] = {
    "m13_01_portfolio_overview": WidgetDefinition(
        widget_id="m13_01_portfolio_overview",
        name="Portfolio Overview",
        owning_module="M13.01",
        category="PORTFOLIO",
        description="Comprehensive summary of portfolio NAV, Daily/Total P&L, Cash Balances, and Gross/Net Exposure.",
        supported_metrics=["nav", "daily_pnl", "total_pnl", "gross_exposure", "net_exposure", "cash_balance"],
        supported_visualization_types=["kpi_cards", "table", "summary_strip"],
        default_visualization_type="kpi_cards",
        dimension_bounds=WidgetDimensionBounds(min_width=4, max_width=12, default_width=12, min_height=2, max_height=6, default_height=3),
        default_configuration={
            "visible_metrics": ["nav", "daily_pnl", "gross_exposure", "net_exposure"],
            "display_mode": "cards",
            "show_currency_symbol": True,
        },
    ),
    "m13_02_risk_overview": WidgetDefinition(
        widget_id="m13_02_risk_overview",
        name="Risk Overview",
        owning_module="M13.02",
        category="RISK",
        description="Core portfolio market risk measurements including VaR (95%/99%), Expected Shortfall, Realized Volatility, and Max Drawdown.",
        supported_metrics=["var_95", "var_99", "expected_shortfall", "volatility", "drawdown", "beta"],
        supported_visualization_types=["kpi_cards", "gauge", "bar", "table"],
        default_visualization_type="kpi_cards",
        dimension_bounds=WidgetDimensionBounds(min_width=3, max_width=12, default_width=6, min_height=2, max_height=8, default_height=4),
        default_configuration={
            "visible_metrics": ["var_99", "expected_shortfall", "volatility", "drawdown"],
            "show_methodology_badge": True,
            "confidence_level": 0.99,
        },
    ),
    "m13_03_exposure_dashboard": WidgetDefinition(
        widget_id="m13_03_exposure_dashboard",
        name="Exposure & Allocation",
        owning_module="M13.03",
        category="EXPOSURE",
        description="Detailed capital distribution by sector, industry, instrument, asset class, and long/short positioning.",
        supported_metrics=["gross_exposure", "net_exposure", "sector_weight", "long_exposure", "short_exposure"],
        supported_visualization_types=["bar_chart", "pie_chart", "treemap", "table"],
        default_visualization_type="bar_chart",
        dimension_bounds=WidgetDimensionBounds(min_width=4, max_width=12, default_width=6, min_height=3, max_height=8, default_height=4),
        default_configuration={
            "breakdown_dimension": "sector",
            "top_n_holdings": 10,
            "show_percentage": True,
        },
    ),
    "m13_04_risk_heatmaps": WidgetDefinition(
        widget_id="m13_04_risk_heatmaps",
        name="Risk Heatmaps",
        owning_module="M13.04",
        category="VISUALIZATION",
        description="Visual matrix of portfolio concentration, sector risk clusters, performance divergence, and drawdown distribution.",
        supported_metrics=["pnl_contribution", "var_contribution", "volatility_level", "drawdown_level"],
        supported_visualization_types=["heatmap", "treemap", "clustered_grid"],
        default_visualization_type="heatmap",
        dimension_bounds=WidgetDimensionBounds(min_width=4, max_width=12, default_width=6, min_height=3, max_height=10, default_height=5),
        default_configuration={
            "color_scale": "RED_GREEN",
            "normalization": "Z_SCORE",
            "group_by": "sector",
        },
    ),
    "m13_05_correlation_dashboard": WidgetDefinition(
        widget_id="m13_05_correlation_dashboard",
        name="Correlation Matrix",
        owning_module="M13.05",
        category="RISK",
        description="Pairwise correlation matrix and hierarchical clustering across portfolio securities and benchmark risk factors.",
        supported_metrics=["pearson_correlation", "spearman_correlation", "covariance"],
        supported_visualization_types=["correlation_matrix", "cluster_dendrogram", "scatter_plot"],
        default_visualization_type="correlation_matrix",
        dimension_bounds=WidgetDimensionBounds(min_width=4, max_width=12, default_width=6, min_height=4, max_height=10, default_height=5),
        default_configuration={
            "lookback_window": 90,
            "sampling_frequency": "DAILY",
            "show_cluster_ordering": True,
        },
    ),
    "m13_06_liquidity_dashboard": WidgetDefinition(
        widget_id="m13_06_liquidity_dashboard",
        name="Liquidity & Market Microstructure",
        owning_module="M13.06",
        category="LIQUIDITY",
        description="Real-time and historical bid-ask spreads, order-book depth, composite liquidity scores, and liquidation horizon estimates.",
        supported_metrics=["bid_ask_spread_bps", "composite_liquidity_score", "order_book_depth", "liquidation_days"],
        supported_visualization_types=["multi_metric_card", "line_chart", "table"],
        default_visualization_type="multi_metric_card",
        dimension_bounds=WidgetDimensionBounds(min_width=4, max_width=12, default_width=6, min_height=3, max_height=8, default_height=4),
        default_configuration={
            "urgency_mode": "MODERATE",
            "participation_rate": 0.10,
            "show_cost_breakdown": True,
        },
    ),
    "m13_07_stress_dashboard": WidgetDefinition(
        widget_id="m13_07_stress_dashboard",
        name="Stress Testing & Scenario Analysis",
        owning_module="M13.07",
        category="STRESS_TESTING",
        description="Scenario definition loss impacts, historical stress shocks (e.g. 2008 GFC, COVID), and Monte Carlo tail distributions.",
        supported_metrics=["stressed_loss_pnl", "stressed_loss_pct", "scenario_var", "tail_loss"],
        supported_visualization_types=["waterfall", "bar_chart", "distribution_curve", "table"],
        default_visualization_type="waterfall",
        dimension_bounds=WidgetDimensionBounds(min_width=4, max_width=12, default_width=6, min_height=3, max_height=8, default_height=4),
        default_configuration={
            "selected_scenario_id": "HIST_2008_GFC",
            "show_sector_attribution": True,
        },
    ),
    "m13_08_alerts_dashboard": WidgetDefinition(
        widget_id="m13_08_alerts_dashboard",
        name="Alerts & Limit Breaches",
        owning_module="M13.08",
        category="ALERTS",
        description="Real-time operational view of active risk-limit breaches, threshold alerts, acknowledgement workflows, and escalation history.",
        supported_metrics=["active_breaches_count", "critical_alerts_count", "unacknowledged_count"],
        supported_visualization_types=["alert_stream", "table", "summary_strip"],
        default_visualization_type="alert_stream",
        dimension_bounds=WidgetDimensionBounds(min_width=4, max_width=12, default_width=6, min_height=3, max_height=8, default_height=5),
        default_configuration={
            "min_severity": "WARNING",
            "auto_refresh_sec": 30,
            "enable_sound": False,
        },
    ),
    "m13_09_historical_analytics": WidgetDefinition(
        widget_id="m13_09_historical_analytics",
        name="Historical Analytics & Audit Replay",
        owning_module="M13.09",
        category="HISTORICAL",
        description="Bitemporal point-in-time valuation history, multi-event overlays (breaches, alerts, trades), and provenance manifests.",
        supported_metrics=["nav_history", "pnl_cumulative", "var_trend", "exposure_trend"],
        supported_visualization_types=["time_series_line", "event_timeline", "point_in_time_inspector"],
        default_visualization_type="time_series_line",
        dimension_bounds=WidgetDimensionBounds(min_width=6, max_width=12, default_width=12, min_height=3, max_height=10, default_height=5),
        default_configuration={
            "historical_mode": "AS_KNOWN_AT_TIME",
            "show_event_overlays": True,
            "lookback_days": 90,
            "frequency": "DAILY",
        },
    ),
}


class WidgetRegistryService:
    """Service providing access to the authoritative widget registry."""

    @staticmethod
    def get_all_widgets() -> List[WidgetDefinition]:
        return list(REGISTERED_WIDGETS.values())

    @staticmethod
    def get_widget(widget_id: str) -> Optional[WidgetDefinition]:
        return REGISTERED_WIDGETS.get(widget_id)

    @staticmethod
    def is_valid_widget(widget_id: str) -> bool:
        return widget_id in REGISTERED_WIDGETS

    @staticmethod
    def get_default_config(widget_id: str) -> Dict[str, Any]:
        widget = REGISTERED_WIDGETS.get(widget_id)
        return widget.default_configuration.copy() if widget else {}
