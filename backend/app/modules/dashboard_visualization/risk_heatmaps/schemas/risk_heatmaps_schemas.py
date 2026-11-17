"""
Pydantic schemas for M13.04 — Risk Heatmaps.

Defines presentation-layer contracts for:
1. Metric Registry (governing metrics, categories, units, provenance, and direction)
2. Color Scale Engine (scale type, domain, midpoint, palette, outlier handling)
3. Sector Heatmap (cells, metrics, area vs color dimensions, aggregated metrics)
4. Security Heatmap (holdings-level cells, sector/industry grouping, long/short filtering)
5. Heatmap Cell Drill-Through (underlying positions, market values, model provenance)

Strictly adheres to Part B Section 3: NO financial calculations are duplicated here.
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# Enums and Configurations
# ---------------------------------------------------------------------------

class MetricCategory(str, Enum):
    EXPOSURE = "EXPOSURE"
    PERFORMANCE = "PERFORMANCE"
    RISK = "RISK"
    LIQUIDITY = "LIQUIDITY"
    SCENARIO = "SCENARIO"


class MetricDirection(str, Enum):
    HIGHER_IS_RISKIER = "HIGHER_IS_RISKIER"       # High = Red/Adverse (e.g. VaR, Volatility, Spread)
    LOWER_IS_RISKIER = "LOWER_IS_RISKIER"         # Low = Red/Adverse (e.g. Market Depth, Liquidity Ratio)
    POSITIVE_IS_FAVORABLE = "POSITIVE_IS_FAVORABLE" # Positive = Green, Negative = Red (e.g. P&L, Return)
    NEGATIVE_IS_ADVERSE = "NEGATIVE_IS_ADVERSE"   # Negative = Red (e.g. Drawdown)
    NEUTRAL_CENTERED = "NEUTRAL_CENTERED"         # Deviations from zero are notable (e.g. Net Exposure)
    MAGNITUDE_ONLY = "MAGNITUDE_ONLY"             # Absolute intensity (e.g. Turnover, Gross Exposure)


class ScaleType(str, Enum):
    SEQUENTIAL = "SEQUENTIAL"
    DIVERGING = "DIVERGING"
    QUANTILE = "QUANTILE"
    THRESHOLD = "THRESHOLD"


class PaletteType(str, Enum):
    RED_GREEN = "RED_GREEN"           # Financial standard (Green = Positive, Red = Negative / Risk)
    BLUES = "BLUES"                   # Sequential single-hue
    REDS = "REDS"                     # Sequential risk intensity
    COOL_WARM = "COOL_WARM"           # Blue to Red diverging
    VIRIDIS = "VIRIDIS"               # Perceptually uniform
    SPECTRAL = "SPECTRAL"             # Multi-hue diverging


class HeatmapGrouping(str, Enum):
    NONE = "NONE"
    SECTOR = "SECTOR"
    INDUSTRY = "INDUSTRY"
    SIDE = "SIDE"


class HeatmapPositionSide(str, Enum):
    ALL = "ALL"
    LONG = "LONG"
    SHORT = "SHORT"


# ---------------------------------------------------------------------------
# Metric Registry Models
# ---------------------------------------------------------------------------

class MetricDefinition(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric_id: str = Field(..., description="Unique metric identifier, e.g. 'unrealized_pnl', 'var_95', 'volatility_annualized'")
    display_name: str = Field(..., description="Institutional human-readable label")
    category: MetricCategory
    unit: str = Field(..., description="Unit of measurement: 'CURRENCY', 'PERCENTAGE', 'BPS', 'RATIO', 'DAYS'")
    semantic_direction: MetricDirection
    default_scale_type: ScaleType
    default_palette: PaletteType
    source_module: str = Field(..., description="Authoritative backend module: M05, M06, M07, M08, M09, M10")
    description: str
    is_additive: bool = Field(True, description="Whether metric can be sum-aggregated across hierarchy")
    supports_sector_view: bool = True
    supports_security_view: bool = True


class MetricRegistryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metrics: List[MetricDefinition]
    total_metrics: int
    as_of: datetime


# ---------------------------------------------------------------------------
# Color Scale & Formatting Models
# ---------------------------------------------------------------------------

class ColorScaleConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scale_type: ScaleType
    palette: PaletteType
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    midpoint: Optional[Decimal] = Field(Decimal("0"), description="Zero or center pivot for diverging scales")
    quantile_breaks: Optional[List[Decimal]] = None
    threshold_steps: Optional[List[Dict[str, Any]]] = None
    clipped_outliers_count: int = 0
    is_inverted: bool = False


# ---------------------------------------------------------------------------
# Heatmap Cell Models
# ---------------------------------------------------------------------------

class HeatmapCell(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entity_id: str = Field(..., description="Identifier: sector name or instrument symbol / ID")
    label: str = Field(..., description="Display label")
    sub_label: Optional[str] = Field(None, description="Secondary label, e.g. Sector for security or classification code")
    
    # Area Dimension (typically Market Value / Gross Exposure magnitude)
    area_metric_id: str
    area_value: Decimal = Field(..., description="Positive value representing cell area weight")
    area_weight_pct: Optional[Decimal] = Field(None, description="Percentage of total heatmap area (0 to 100)")
    
    # Color Dimension (metric being visualized)
    color_metric_id: str
    color_metric_value: Optional[Decimal] = Field(None, description="Raw financial value, None if unavailable/stale")
    formatted_value: str = Field(..., description="Human-readable formatted string with units")
    normalized_score: Optional[Decimal] = Field(None, description="Normalized score [0.0 to 1.0] for color mapping")
    color_hex: Optional[str] = Field(None, description="Hex color code determined by color scale engine")
    
    # Exposure context
    long_exposure: Decimal = Decimal("0")
    short_exposure: Decimal = Decimal("0")
    net_exposure: Decimal = Decimal("0")
    gross_exposure: Decimal = Decimal("0")
    instrument_count: int = 1
    
    # Data Quality & Provenance
    data_quality_status: str = Field("VERIFIED", description="VERIFIED, STALE, UNAVAILABLE, ESTIMATED")
    is_outlier_clipped: bool = False
    provenance_source: str = Field(..., description="Authoritative backend module name")
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Sector Heatmap Models
# ---------------------------------------------------------------------------

class SectorHeatmapResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    as_of_date: date
    generated_at: datetime
    reporting_currency: str
    
    color_metric: MetricDefinition
    area_metric_id: str
    color_scale: ColorScaleConfig
    
    cells: List[HeatmapCell]
    total_area_value: Decimal
    unclassified_cell: Optional[HeatmapCell] = None
    
    data_quality_summary: Dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Security Heatmap Models
# ---------------------------------------------------------------------------

class SecurityGroupNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    group_id: str
    group_name: str
    group_area_value: Decimal
    group_area_pct: Decimal
    cells: List[HeatmapCell]


class SecurityHeatmapResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    as_of_date: date
    generated_at: datetime
    reporting_currency: str
    
    grouping: HeatmapGrouping
    side_filter: HeatmapPositionSide
    color_metric: MetricDefinition
    area_metric_id: str
    color_scale: ColorScaleConfig
    
    # Either flat cells or grouped structures
    cells: List[HeatmapCell]
    groups: Optional[List[SecurityGroupNode]] = None
    
    total_securities: int
    total_area_value: Decimal
    data_quality_summary: Dict[str, int] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Heatmap Drill-Through Models
# ---------------------------------------------------------------------------

class DrilldownHoldingRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instrument_id: str
    symbol: str
    instrument_name: str
    sector_name: Optional[str] = None
    industry_name: Optional[str] = None
    side: str
    quantity: Decimal
    market_price: Decimal
    market_value: Decimal
    weight_pct: Decimal
    color_metric_value: Optional[Decimal] = None
    formatted_color_metric: str
    data_quality_status: str


class HeatmapDrilldownResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: str
    entity_id: str
    entity_type: str = Field(..., description="'SECTOR' or 'SECURITY'")
    entity_name: str
    as_of_date: date
    generated_at: datetime
    reporting_currency: str
    
    color_metric: MetricDefinition
    area_metric_id: str
    
    summary: Dict[str, Any]
    holdings: List[DrilldownHoldingRow]
    total_holdings: int
    provenance_details: Dict[str, Any]
