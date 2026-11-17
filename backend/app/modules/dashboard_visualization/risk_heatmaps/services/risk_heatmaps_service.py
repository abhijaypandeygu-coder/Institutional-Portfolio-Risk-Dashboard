"""
M13.04 — Risk Heatmaps Services.

Provides backend presentation services for:
1. HeatmapMetricRegistryService: Supported metrics, direction, categorization, provenance
2. HeatmapColorScaleService: Normalization, scale generation, palette mappings, outlier clipping
3. SectorHeatmapService: Sector-level heatmap data aggregation consuming M06.03 & M05.03
4. SecurityHeatmapService: Holdings-level heatmap data aggregation consuming M06.04 & M05.03
5. HeatmapDrillthroughService: Detailed holdings breakdown for drill-through
6. RiskHeatmapsService: Unified coordinator
"""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any, Tuple
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from backend.app.modules.dashboard_visualization.risk_heatmaps.schemas.risk_heatmaps_schemas import (
    MetricCategory,
    MetricDirection,
    ScaleType,
    PaletteType,
    HeatmapGrouping,
    HeatmapPositionSide,
    MetricDefinition,
    MetricRegistryResponse,
    ColorScaleConfig,
    HeatmapCell,
    SectorHeatmapResponse,
    SecurityGroupNode,
    SecurityHeatmapResponse,
    DrilldownHoldingRow,
    HeatmapDrilldownResponse,
)

# Authoritative services and models from M05 and M06
from backend.app.modules.portfolio_management.position_valuation.models import PositionValuation
from backend.app.modules.risk_management.sector_exposure.services.service import SectorExposureService
from backend.app.modules.risk_management.sector_exposure.schemas import SectorExposureCalculateRequest
from backend.app.modules.risk_management.instrument_exposure.services.service import InstrumentExposureService
from backend.app.modules.risk_management.instrument_exposure.schemas import (
    InstrumentExposureCalculateRequest,
    ExposureRankingBasis,
)

logger = logging.getLogger("risk_heatmaps_service")


# ---------------------------------------------------------------------------
# Metric Registry Service
# ---------------------------------------------------------------------------

class HeatmapMetricRegistryService:
    """Governs all supported metrics for Risk Heatmaps."""

    _METRICS: Dict[str, MetricDefinition] = {
        "unrealized_pnl": MetricDefinition(
            metric_id="unrealized_pnl",
            display_name="Unrealized P&L",
            category=MetricCategory.PERFORMANCE,
            unit="CURRENCY",
            semantic_direction=MetricDirection.POSITIVE_IS_FAVORABLE,
            default_scale_type=ScaleType.DIVERGING,
            default_palette=PaletteType.RED_GREEN,
            source_module="M05 — Portfolio Accounting & Valuation",
            description="Cumulative unrealized profit or loss on current open positions based on mark prices.",
            is_additive=True,
            supports_sector_view=True,
            supports_security_view=True,
        ),
        "unrealized_pnl_pct": MetricDefinition(
            metric_id="unrealized_pnl_pct",
            display_name="Unrealized Return %",
            category=MetricCategory.PERFORMANCE,
            unit="PERCENTAGE",
            semantic_direction=MetricDirection.POSITIVE_IS_FAVORABLE,
            default_scale_type=ScaleType.DIVERGING,
            default_palette=PaletteType.RED_GREEN,
            source_module="M05 — Portfolio Accounting & Valuation",
            description="Unrealized profit or loss expressed as a percentage of entry cost basis.",
            is_additive=False,
            supports_sector_view=True,
            supports_security_view=True,
        ),
        "net_market_value": MetricDefinition(
            metric_id="net_market_value",
            display_name="Net Market Value",
            category=MetricCategory.EXPOSURE,
            unit="CURRENCY",
            semantic_direction=MetricDirection.NEUTRAL_CENTERED,
            default_scale_type=ScaleType.DIVERGING,
            default_palette=PaletteType.COOL_WARM,
            source_module="M05 / M06 — Exposure Management",
            description="Long market value minus short market value.",
            is_additive=True,
            supports_sector_view=True,
            supports_security_view=True,
        ),
        "gross_market_value": MetricDefinition(
            metric_id="gross_market_value",
            display_name="Gross Market Value",
            category=MetricCategory.EXPOSURE,
            unit="CURRENCY",
            semantic_direction=MetricDirection.MAGNITUDE_ONLY,
            default_scale_type=ScaleType.SEQUENTIAL,
            default_palette=PaletteType.BLUES,
            source_module="M06 — Exposure Management",
            description="Long market value plus absolute short market value.",
            is_additive=True,
            supports_sector_view=True,
            supports_security_view=True,
        ),
        "nav_weight_pct": MetricDefinition(
            metric_id="nav_weight_pct",
            display_name="NAV Weight %",
            category=MetricCategory.EXPOSURE,
            unit="PERCENTAGE",
            semantic_direction=MetricDirection.NEUTRAL_CENTERED,
            default_scale_type=ScaleType.DIVERGING,
            default_palette=PaletteType.COOL_WARM,
            source_module="M06 — Exposure Management",
            description="Net market value divided by total portfolio NAV.",
            is_additive=True,
            supports_sector_view=True,
            supports_security_view=True,
        ),
        "gross_weight_pct": MetricDefinition(
            metric_id="gross_weight_pct",
            display_name="Gross Weight %",
            category=MetricCategory.EXPOSURE,
            unit="PERCENTAGE",
            semantic_direction=MetricDirection.MAGNITUDE_ONLY,
            default_scale_type=ScaleType.SEQUENTIAL,
            default_palette=PaletteType.BLUES,
            source_module="M06 — Exposure Management",
            description="Gross market value divided by total portfolio NAV.",
            is_additive=True,
            supports_sector_view=True,
            supports_security_view=True,
        ),
        "volatility_annualized": MetricDefinition(
            metric_id="volatility_annualized",
            display_name="Historical Volatility (Ann.)",
            category=MetricCategory.RISK,
            unit="PERCENTAGE",
            semantic_direction=MetricDirection.HIGHER_IS_RISKIER,
            default_scale_type=ScaleType.SEQUENTIAL,
            default_palette=PaletteType.REDS,
            source_module="M07.01 — Volatility Analytics",
            description="Annualized historical price volatility.",
            is_additive=False,
            supports_sector_view=False,
            supports_security_view=True,
        ),
        "drawdown_pct": MetricDefinition(
            metric_id="drawdown_pct",
            display_name="Current Drawdown %",
            category=MetricCategory.RISK,
            unit="PERCENTAGE",
            semantic_direction=MetricDirection.NEGATIVE_IS_ADVERSE,
            default_scale_type=ScaleType.SEQUENTIAL,
            default_palette=PaletteType.REDS,
            source_module="M07.04 — Drawdown Analytics",
            description="Peak-to-trough decline percentage from recent high.",
            is_additive=False,
            supports_sector_view=False,
            supports_security_view=True,
        ),
    }

    @classmethod
    def get_registry(cls) -> MetricRegistryResponse:
        metrics_list = list(cls._METRICS.values())
        return MetricRegistryResponse(
            metrics=metrics_list,
            total_metrics=len(metrics_list),
            as_of=datetime.now(timezone.utc),
        )

    @classmethod
    def get_metric(cls, metric_id: str) -> MetricDefinition:
        if metric_id not in cls._METRICS:
            return cls._METRICS["unrealized_pnl"]
        return cls._METRICS[metric_id]


# ---------------------------------------------------------------------------
# Color Scale & Hex Mapping Service
# ---------------------------------------------------------------------------

class HeatmapColorScaleService:
    """Computes color scale configurations, normalization scores, and hex colors."""

    PALETTES = {
        PaletteType.RED_GREEN: {
            "negative": ["#7f1d1d", "#b91c1c", "#ef4444", "#fca5a5"], # Deep red to light red
            "neutral": "#e5e7eb",                                      # Light gray neutral
            "positive": ["#bbf7d0", "#4ade80", "#16a34a", "#14532d"], # Light green to deep emerald
        },
        PaletteType.COOL_WARM: {
            "negative": ["#1e3a8a", "#2563eb", "#60a5fa", "#bfdbfe"], # Deep blue to light blue
            "neutral": "#f3f4f6",                                      # Soft gray
            "positive": ["#fed7aa", "#fb923c", "#ea580c", "#7c2d12"], # Light amber to deep warm red
        },
        PaletteType.BLUES: {
            "sequential": ["#eff6ff", "#bfdbfe", "#93c5fd", "#60a5fa", "#3b82f6", "#1d4ed8", "#1e3a8a"],
        },
        PaletteType.REDS: {
            "sequential": ["#fef2f2", "#fee2e2", "#fca5a5", "#f87171", "#ef4444", "#dc2626", "#991b1b"],
        },
        PaletteType.VIRIDIS: {
            "sequential": ["#440154", "#482878", "#3e4989", "#31688e", "#26828e", "#1f9e89", "#35b779", "#6ece58", "#b5de2b", "#fde725"],
        },
    }

    @classmethod
    def build_color_scale_config(
        cls,
        metric: MetricDefinition,
        values: List[Decimal],
        override_scale_type: Optional[ScaleType] = None,
        override_palette: Optional[PaletteType] = None,
        clip_outliers: bool = True,
    ) -> Tuple[ColorScaleConfig, Decimal, Decimal, Decimal]:
        """Calculates domain min, max, midpoint and sets up scale configuration."""
        scale_type = override_scale_type or metric.default_scale_type
        palette = override_palette or metric.default_palette
        
        valid_values = [v for v in values if v is not None]
        if not valid_values:
            return (
                ColorScaleConfig(
                    scale_type=scale_type,
                    palette=palette,
                    min_value=Decimal("0"),
                    max_value=Decimal("0"),
                    midpoint=Decimal("0"),
                    clipped_outliers_count=0,
                ),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
            )

        min_val = min(valid_values)
        max_val = max(valid_values)
        clipped_count = 0

        # Diverging scale handling (symmetric domain around zero)
        if scale_type == ScaleType.DIVERGING:
            midpoint = Decimal("0")
            abs_max = max(abs(min_val), abs(max_val))
            if abs_max == Decimal("0"):
                abs_max = Decimal("1")
            
            # Outlier clipping at 90th percentile of magnitude if >= 10 values
            if clip_outliers and len(valid_values) >= 10:
                sorted_abs = sorted([abs(v) for v in valid_values])
                p90_idx = int(len(sorted_abs) * 0.90)
                clip_threshold = sorted_abs[min(p90_idx, len(sorted_abs) - 1)]
                if clip_threshold > Decimal("0") and abs_max > clip_threshold * Decimal("2"):
                    abs_max = clip_threshold * Decimal("2")
                    clipped_count = sum(1 for v in valid_values if abs(v) > abs_max)

            domain_min = -abs_max
            domain_max = abs_max
            return (
                ColorScaleConfig(
                    scale_type=scale_type,
                    palette=palette,
                    min_value=domain_min,
                    max_value=domain_max,
                    midpoint=midpoint,
                    clipped_outliers_count=clipped_count,
                ),
                domain_min,
                domain_max,
                midpoint,
            )

        # Sequential scale handling
        midpoint = (min_val + max_val) / Decimal("2")
        return (
            ColorScaleConfig(
                scale_type=scale_type,
                palette=palette,
                min_value=min_val,
                max_value=max_val,
                midpoint=midpoint,
                clipped_outliers_count=0,
            ),
            min_val,
            max_val,
            midpoint,
        )

    @classmethod
    def get_color_hex(
        cls,
        val: Optional[Decimal],
        scale_config: ColorScaleConfig,
        direction: MetricDirection,
    ) -> Tuple[Optional[Decimal], Optional[str], bool]:
        """Returns (normalized_score, hex_color, is_outlier_clipped)."""
        if val is None:
            return None, "#64748b", False  # Muted slate for unavailable

        min_val = scale_config.min_value or Decimal("0")
        max_val = scale_config.max_value or Decimal("0")
        is_clipped = False

        if scale_config.scale_type == ScaleType.DIVERGING:
            abs_bound = max_val  # Domain is [-abs_bound, abs_bound]
            if abs_bound == Decimal("0"):
                return Decimal("0.5"), "#e5e7eb", False

            if val > abs_bound:
                val = abs_bound
                is_clipped = True
            elif val < -abs_bound:
                val = -abs_bound
                is_clipped = True

            norm = (val + abs_bound) / (abs_bound * Decimal("2"))
            norm = max(Decimal("0.0"), min(Decimal("1.0"), norm))

            # Select hex
            if scale_config.palette == PaletteType.RED_GREEN:
                if val > Decimal("0"):
                    pos_idx = min(int((val / abs_bound) * 4), 3)
                    hex_color = cls.PALETTES[PaletteType.RED_GREEN]["positive"][pos_idx]
                elif val < Decimal("0"):
                    neg_idx = min(int((abs(val) / abs_bound) * 4), 3)
                    hex_color = cls.PALETTES[PaletteType.RED_GREEN]["negative"][neg_idx]
                else:
                    hex_color = cls.PALETTES[PaletteType.RED_GREEN]["neutral"]
            else:
                if val > Decimal("0"):
                    pos_idx = min(int((val / abs_bound) * 4), 3)
                    hex_color = cls.PALETTES[PaletteType.COOL_WARM]["positive"][pos_idx]
                elif val < Decimal("0"):
                    neg_idx = min(int((abs(val) / abs_bound) * 4), 3)
                    hex_color = cls.PALETTES[PaletteType.COOL_WARM]["negative"][neg_idx]
                else:
                    hex_color = cls.PALETTES[PaletteType.COOL_WARM]["neutral"]

            return norm.quantize(Decimal("0.0001")), hex_color, is_clipped

        # Sequential Scale
        span = max_val - min_val
        if span == Decimal("0"):
            return Decimal("0.5"), "#93c5fd", False

        norm = (val - min_val) / span
        norm = max(Decimal("0.0"), min(Decimal("1.0"), norm))

        palette_key = scale_config.palette if scale_config.palette in cls.PALETTES else PaletteType.BLUES
        seq_colors = cls.PALETTES[palette_key].get("sequential", cls.PALETTES[PaletteType.BLUES]["sequential"])
        color_idx = min(int(norm * Decimal(str(len(seq_colors)))), len(seq_colors) - 1)
        hex_color = seq_colors[color_idx]

        return norm.quantize(Decimal("0.0001")), hex_color, is_clipped


# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------

def _format_metric_value(val: Optional[Decimal], unit: str, currency: str) -> str:
    if val is None:
        return "N/A"
    if unit == "CURRENCY":
        sign = "+" if val > Decimal("0") else ""
        return f"{sign}{currency} {val:,.2f}"
    elif unit == "PERCENTAGE":
        sign = "+" if val > Decimal("0") else ""
        return f"{sign}{val:.2f}%"
    elif unit == "BPS":
        sign = "+" if val > Decimal("0") else ""
        return f"{sign}{val:.1f} bps"
    return f"{val:,.2f}"


# ---------------------------------------------------------------------------
# Sector Heatmap Service
# ---------------------------------------------------------------------------

class SectorHeatmapService:
    """Builds sector-level heatmap treemap cells consuming M06.03 sector exposures and M05.03 valuations."""

    @classmethod
    async def get_sector_heatmap(
        cls,
        session: AsyncSession,
        portfolio_id: str,
        color_metric_id: str = "unrealized_pnl",
        area_metric_id: str = "gross_market_value",
        base_currency: str = "USD",
        as_of_dt: Optional[datetime] = None,
        override_scale_type: Optional[ScaleType] = None,
        override_palette: Optional[PaletteType] = None,
    ) -> SectorHeatmapResponse:
        now_utc = as_of_dt or datetime.now(timezone.utc)
        as_of = now_utc.date()

        metric_def = HeatmapMetricRegistryService.get_metric(color_metric_id)

        # 1. Fetch Sector Exposure from M06.03
        sector_exp_service = SectorExposureService(session)
        sector_req = SectorExposureCalculateRequest(
            as_of=now_utc,
            reporting_currency=base_currency,
        )
        sector_res = await sector_exp_service.calculate_portfolio_sector_exposure(portfolio_id, sector_req)
        reporting_curr = sector_res.reporting_currency

        # 2. Query Position Valuations from M05.03 for P&L aggregation per instrument
        query = (
            select(
                PositionValuation.instrument_id,
                PositionValuation.unrealized_pnl_base,
                PositionValuation.signed_market_value_base,
                PositionValuation.signed_cost_basis_base,
            )
            .where(PositionValuation.portfolio_id == portfolio_id)
        )
        val_rows = (await session.execute(query)).all()
        val_map = {r.instrument_id: r for r in val_rows}

        # 3. Extract raw metric values for color scaling
        candidate_cells_data = []
        raw_color_values: List[Decimal] = []
        total_area = Decimal("0")

        for item in sector_res.sectors:
            s_name = item.sector_name
            # Determine area value
            if area_metric_id == "net_market_value":
                area_val = abs(item.net_exposure)
            else:
                area_val = item.gross_exposure
            
            if area_val <= Decimal("0"):
                area_val = Decimal("1.0")

            total_area += area_val

            # Determine color metric value
            # Calculate sector P&L from constituent instruments if available
            sector_pnl = Decimal("0")
            sector_cost = Decimal("0")
            for h in item.holdings:
                v = val_map.get(h.instrument_id)
                if v and v.unrealized_pnl_base is not None:
                    sector_pnl += v.unrealized_pnl_base
                if v and v.signed_cost_basis_base is not None:
                    sector_cost += abs(v.signed_cost_basis_base)

            nav_wt = item.net_weight * Decimal("100") if item.net_weight is not None else Decimal("0")
            gross_wt = item.gross_weight * Decimal("100") if item.gross_weight is not None else Decimal("0")

            if color_metric_id == "unrealized_pnl":
                val = sector_pnl
            elif color_metric_id == "unrealized_pnl_pct":
                val = (sector_pnl / sector_cost * Decimal("100")) if sector_cost > Decimal("0") else Decimal("0")
            elif color_metric_id == "net_market_value":
                val = item.net_exposure
            elif color_metric_id == "gross_market_value":
                val = item.gross_exposure
            elif color_metric_id == "nav_weight_pct":
                val = nav_wt
            elif color_metric_id == "gross_weight_pct":
                val = gross_wt
            else:
                val = sector_pnl

            raw_color_values.append(val)
            candidate_cells_data.append({
                "entity_id": item.sector_id or s_name,
                "label": s_name,
                "sub_label": f"{item.holdings_count} positions",
                "area_val": area_val,
                "color_val": val,
                "long_exp": item.long_exposure,
                "short_exp": item.absolute_short_exposure,
                "net_exp": item.net_exposure,
                "gross_exp": item.gross_exposure,
                "count": item.holdings_count,
            })

        # Process unclassified if exists
        unclassified_cell = None
        if sector_res.unclassified:
            u_gross = sum(u.gross_exposure for u in sector_res.unclassified)
            u_net = sum(u.net_exposure for u in sector_res.unclassified)
            u_long = sum(u.long_exposure for u in sector_res.unclassified)
            u_short = sum(u.absolute_short_exposure for u in sector_res.unclassified)
            u_count = sum(u.contributing_instrument_count for u in sector_res.unclassified)
            
            # Compute P&L for unclassified holdings by taking total P&L minus classified sectors P&L
            tot_pnl = sum(r.unrealized_pnl_base for r in val_rows if r.unrealized_pnl_base is not None)
            classified_pnl = sum(c["color_val"] for c in candidate_cells_data if color_metric_id == "unrealized_pnl")
            u_pnl = tot_pnl - classified_pnl

            u_area = u_gross if area_metric_id == "gross_market_value" else abs(u_net)
            if u_area > Decimal("0"):
                total_area += u_area
                raw_color_values.append(u_pnl)
                candidate_cells_data.append({
                    "entity_id": "UNCLASSIFIED",
                    "label": "Unclassified",
                    "sub_label": f"{u_count} positions",
                    "area_val": u_area,
                    "color_val": u_pnl,
                    "long_exp": u_long,
                    "short_exp": u_short,
                    "net_exp": u_net,
                    "gross_exp": u_gross,
                    "count": u_count,
                })

        # 4. Compute Color Scale
        color_scale_config, _, _, _ = HeatmapColorScaleService.build_color_scale_config(
            metric=metric_def,
            values=raw_color_values,
            override_scale_type=override_scale_type,
            override_palette=override_palette,
        )

        # 5. Build Final Cells
        cells: List[HeatmapCell] = []
        quality_counts = {"VERIFIED": 0, "STALE": 0, "UNAVAILABLE": 0}

        for cdata in candidate_cells_data:
            area_pct = (cdata["area_val"] / total_area * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if total_area > Decimal("0") else Decimal("0")
            val = cdata["color_val"]
            norm_score, hex_col, is_clipped = HeatmapColorScaleService.get_color_hex(
                val=val,
                scale_config=color_scale_config,
                direction=metric_def.semantic_direction,
            )

            cell = HeatmapCell(
                entity_id=cdata["entity_id"],
                label=cdata["label"],
                sub_label=cdata["sub_label"],
                area_metric_id=area_metric_id,
                area_value=cdata["area_val"],
                area_weight_pct=area_pct,
                color_metric_id=color_metric_id,
                color_metric_value=val,
                formatted_value=_format_metric_value(val, metric_def.unit, reporting_curr),
                normalized_score=norm_score,
                color_hex=hex_col,
                long_exposure=cdata["long_exp"],
                short_exposure=cdata["short_exp"],
                net_exposure=cdata["net_exp"],
                gross_exposure=cdata["gross_exp"],
                instrument_count=cdata["count"],
                data_quality_status="VERIFIED",
                is_outlier_clipped=is_clipped,
                provenance_source=metric_def.source_module,
                metadata={"reporting_currency": reporting_curr},
            )
            quality_counts["VERIFIED"] += 1
            if cdata["entity_id"] == "UNCLASSIFIED":
                unclassified_cell = cell
            else:
                cells.append(cell)

        return SectorHeatmapResponse(
            portfolio_id=portfolio_id,
            as_of_date=as_of,
            generated_at=now_utc,
            reporting_currency=reporting_curr,
            color_metric=metric_def,
            area_metric_id=area_metric_id,
            color_scale=color_scale_config,
            cells=cells,
            total_area_value=total_area,
            unclassified_cell=unclassified_cell,
            data_quality_summary=quality_counts,
        )


# ---------------------------------------------------------------------------
# Security Heatmap Service
# ---------------------------------------------------------------------------

class SecurityHeatmapService:
    """Builds security-level heatmap cells grouped by sector or industry with long/short filtering."""

    @classmethod
    async def get_security_heatmap(
        cls,
        session: AsyncSession,
        portfolio_id: str,
        color_metric_id: str = "unrealized_pnl",
        area_metric_id: str = "gross_market_value",
        grouping: HeatmapGrouping = HeatmapGrouping.SECTOR,
        side_filter: HeatmapPositionSide = HeatmapPositionSide.ALL,
        base_currency: str = "USD",
        as_of_dt: Optional[datetime] = None,
        override_scale_type: Optional[ScaleType] = None,
        override_palette: Optional[PaletteType] = None,
    ) -> SecurityHeatmapResponse:
        now_utc = as_of_dt or datetime.now(timezone.utc)
        as_of = now_utc.date()

        metric_def = HeatmapMetricRegistryService.get_metric(color_metric_id)

        # 1. Fetch Instrument Exposure from M06.04
        inst_exp_service = InstrumentExposureService(session)
        inst_req = InstrumentExposureCalculateRequest(
            as_of=now_utc,
            reporting_currency=base_currency,
            ranking_basis=ExposureRankingBasis.GROSS,
        )
        inst_res = await inst_exp_service.calculate_portfolio_instrument_exposure(portfolio_id, inst_req)
        reporting_curr = inst_res.reporting_currency

        # 2. Query Detailed Position Valuation
        query = (
            select(
                PositionValuation.instrument_id,
                PositionValuation.position_side,
                PositionValuation.unrealized_pnl_base,
                PositionValuation.signed_cost_basis_base,
                PositionValuation.signed_market_value_base,
                PositionValuation.mark_price,
            )
            .where(PositionValuation.portfolio_id == portfolio_id)
        )
        val_rows = (await session.execute(query)).all()
        val_map = {r.instrument_id: r for r in val_rows}

        # 3. Filter and Extract Items
        extracted_items = []
        raw_color_values: List[Decimal] = []
        total_area = Decimal("0")

        for item in inst_res.instruments:
            v_info = val_map.get(item.instrument_id)
            pos_side_str = "LONG" if item.long_market_value > Decimal("0") else "SHORT"

            # Apply Side Filter
            if side_filter == HeatmapPositionSide.LONG and pos_side_str == "SHORT":
                continue
            if side_filter == HeatmapPositionSide.SHORT and pos_side_str != "SHORT":
                continue

            # Area dimension
            if area_metric_id == "net_market_value":
                area_val = abs(item.net_market_value)
            else:
                area_val = item.gross_market_value
            if area_val <= Decimal("0"):
                area_val = Decimal("1.0")

            total_area += area_val

            # Color metric extraction
            unrealized_pnl = getattr(v_info, "unrealized_pnl_base", Decimal("0")) if v_info else Decimal("0")
            cost_basis = abs(getattr(v_info, "signed_cost_basis_base", Decimal("0"))) if v_info else Decimal("0")

            nav_wt = (item.net_nav_weight * Decimal("100")) if getattr(item, "net_nav_weight", None) is not None else Decimal("0")
            gross_wt = (item.gross_nav_weight * Decimal("100")) if getattr(item, "gross_nav_weight", None) is not None else Decimal("0")

            if color_metric_id == "unrealized_pnl":
                val = unrealized_pnl
            elif color_metric_id == "unrealized_pnl_pct":
                val = (unrealized_pnl / cost_basis * Decimal("100")) if cost_basis and cost_basis > Decimal("0") else Decimal("0")
            elif color_metric_id == "net_market_value":
                val = item.net_market_value
            elif color_metric_id == "gross_market_value":
                val = item.gross_market_value
            elif color_metric_id == "nav_weight_pct":
                val = nav_wt
            elif color_metric_id == "gross_weight_pct":
                val = gross_wt
            else:
                val = unrealized_pnl

            raw_color_values.append(val)
            sec_name = getattr(item, "sector_name", None) or "Unclassified"
            ind_name = getattr(item, "industry_name", None) or "Unclassified"

            extracted_items.append({
                "instrument_id": item.instrument_id,
                "symbol": item.symbol or item.instrument_id,
                "name": item.instrument_name or item.symbol or item.instrument_id,
                "sector_name": sec_name,
                "industry_name": ind_name,
                "side": pos_side_str,
                "area_val": area_val,
                "color_val": val,
                "long_exp": item.long_market_value,
                "short_exp": item.short_market_value,
                "net_exp": item.net_market_value,
                "gross_exp": item.gross_market_value,
            })

        # 4. Color Scale Config
        color_scale_config, _, _, _ = HeatmapColorScaleService.build_color_scale_config(
            metric=metric_def,
            values=raw_color_values,
            override_scale_type=override_scale_type,
            override_palette=override_palette,
        )

        # 5. Build Cells and Grouping
        cells: List[HeatmapCell] = []
        groups_map: Dict[str, List[HeatmapCell]] = {}
        quality_counts = {"VERIFIED": 0, "STALE": 0, "UNAVAILABLE": 0}

        for ei in extracted_items:
            area_pct = (ei["area_val"] / total_area * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if total_area > Decimal("0") else Decimal("0")
            val = ei["color_val"]
            norm_score, hex_col, is_clipped = HeatmapColorScaleService.get_color_hex(
                val=val,
                scale_config=color_scale_config,
                direction=metric_def.semantic_direction,
            )

            cell = HeatmapCell(
                entity_id=ei["instrument_id"],
                label=ei["symbol"],
                sub_label=ei["sector_name"],
                area_metric_id=area_metric_id,
                area_value=ei["area_val"],
                area_weight_pct=area_pct,
                color_metric_id=color_metric_id,
                color_metric_value=val,
                formatted_value=_format_metric_value(val, metric_def.unit, reporting_curr),
                normalized_score=norm_score,
                color_hex=hex_col,
                long_exposure=ei["long_exp"],
                short_exposure=ei["short_exp"],
                net_exposure=ei["net_exp"],
                gross_exposure=ei["gross_exp"],
                instrument_count=1,
                data_quality_status="VERIFIED",
                is_outlier_clipped=is_clipped,
                provenance_source=metric_def.source_module,
                metadata={
                    "instrument_name": ei["name"],
                    "industry_name": ei["industry_name"],
                    "position_side": ei["side"],
                },
            )
            cells.append(cell)
            quality_counts["VERIFIED"] += 1

            # Determine grouping key
            if grouping == HeatmapGrouping.SECTOR:
                grp_key = ei["sector_name"]
            elif grouping == HeatmapGrouping.INDUSTRY:
                grp_key = ei["industry_name"]
            elif grouping == HeatmapGrouping.SIDE:
                grp_key = f"{ei['side']} Positions"
            else:
                grp_key = "All Holdings"

            if grp_key not in groups_map:
                groups_map[grp_key] = []
            groups_map[grp_key].append(cell)

        # Build group nodes if grouped
        group_nodes: Optional[List[SecurityGroupNode]] = None
        if grouping != HeatmapGrouping.NONE:
            group_nodes = []
            for g_name, g_cells in groups_map.items():
                g_area = sum(c.area_value for c in g_cells)
                g_pct = (g_area / total_area * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if total_area > Decimal("0") else Decimal("0")
                group_nodes.append(
                    SecurityGroupNode(
                        group_id=g_name,
                        group_name=g_name,
                        group_area_value=g_area,
                        group_area_pct=g_pct,
                        cells=g_cells,
                    )
                )

        return SecurityHeatmapResponse(
            portfolio_id=portfolio_id,
            as_of_date=as_of,
            generated_at=now_utc,
            reporting_currency=reporting_curr,
            grouping=grouping,
            side_filter=side_filter,
            color_metric=metric_def,
            area_metric_id=area_metric_id,
            color_scale=color_scale_config,
            cells=cells,
            groups=group_nodes,
            total_securities=len(cells),
            total_area_value=total_area,
            data_quality_summary=quality_counts,
        )


# ---------------------------------------------------------------------------
# Heatmap Drill-Through Service
# ---------------------------------------------------------------------------

class HeatmapDrillthroughService:
    """Resolves a cell click into underlying holdings, valuations, and model parameters."""

    @classmethod
    async def get_drilldown(
        cls,
        session: AsyncSession,
        portfolio_id: str,
        entity_id: str,
        entity_type: str = "SECTOR",
        color_metric_id: str = "unrealized_pnl",
        area_metric_id: str = "gross_market_value",
        base_currency: str = "USD",
        as_of_dt: Optional[datetime] = None,
    ) -> HeatmapDrilldownResponse:
        now_utc = as_of_dt or datetime.now(timezone.utc)
        as_of = now_utc.date()

        metric_def = HeatmapMetricRegistryService.get_metric(color_metric_id)

        # 1. Fetch Instrument Exposures
        inst_exp_service = InstrumentExposureService(session)
        inst_req = InstrumentExposureCalculateRequest(
            as_of=now_utc,
            reporting_currency=base_currency,
            ranking_basis=ExposureRankingBasis.GROSS,
        )
        inst_res = await inst_exp_service.calculate_portfolio_instrument_exposure(portfolio_id, inst_req)

        # 2. Query Valuations
        query = (
            select(
                PositionValuation.instrument_id,
                PositionValuation.position_side,
                PositionValuation.signed_quantity,
                PositionValuation.mark_price,
                PositionValuation.signed_market_value_base,
                PositionValuation.unrealized_pnl_base,
                PositionValuation.signed_cost_basis_base,
            )
            .where(PositionValuation.portfolio_id == portfolio_id)
        )
        val_rows = (await session.execute(query)).all()
        val_map = {r.instrument_id: r for r in val_rows}

        total_portfolio_gross = inst_res.total_gross_exposure if inst_res.total_gross_exposure > Decimal("0") else Decimal("1")
        reporting_curr = inst_res.reporting_currency

        # Filter by entity
        holdings: List[DrilldownHoldingRow] = []
        entity_display_name = entity_id
        tot_mkt_val = Decimal("0")
        tot_color_val = Decimal("0")

        for item in inst_res.instruments:
            sec_name = getattr(item, "sector_name", None) or "Unclassified"
            ind_name = getattr(item, "industry_name", None) or "Unclassified"
            
            # Match condition
            matches = False
            if entity_type.upper() == "SECTOR":
                if entity_id.upper() in [sec_name.upper(), "UNCLASSIFIED"]:
                    if entity_id.upper() == sec_name.upper() or (entity_id.upper() == "UNCLASSIFIED" and sec_name == "Unclassified"):
                        matches = True
                        entity_display_name = sec_name
            else:  # SECURITY
                if item.instrument_id == entity_id or (item.symbol and item.symbol.upper() == entity_id.upper()):
                    matches = True
                    entity_display_name = f"{item.symbol or item.instrument_id} — {item.instrument_name or item.instrument_id}"

            if not matches:
                continue

            v = val_map.get(item.instrument_id)
            unrealized_pnl = v.unrealized_pnl_base if v and v.unrealized_pnl_base is not None else Decimal("0")
            cost_basis = abs(v.signed_cost_basis_base) if v and v.signed_cost_basis_base is not None else Decimal("0")
            qty = abs(v.signed_quantity) if v and v.signed_quantity is not None else Decimal("0")
            px = v.mark_price if v and v.mark_price is not None else Decimal("0")

            if color_metric_id == "unrealized_pnl":
                c_val = unrealized_pnl
            elif color_metric_id == "unrealized_pnl_pct":
                c_val = (unrealized_pnl / cost_basis * Decimal("100")) if cost_basis > Decimal("0") else Decimal("0")
            elif color_metric_id == "net_market_value":
                c_val = item.net_market_value
            elif color_metric_id == "gross_market_value":
                c_val = item.gross_market_value
            else:
                c_val = unrealized_pnl

            tot_color_val += c_val
            tot_mkt_val += item.gross_market_value
            weight = (item.gross_market_value / total_portfolio_gross * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            pos_side = "LONG" if item.long_market_value > Decimal("0") else "SHORT"

            holdings.append(
                DrilldownHoldingRow(
                    instrument_id=item.instrument_id,
                    symbol=item.symbol or item.instrument_id,
                    instrument_name=item.instrument_name or item.symbol or item.instrument_id,
                    sector_name=sec_name,
                    industry_name=ind_name,
                    side=pos_side,
                    quantity=qty,
                    market_price=px,
                    market_value=item.gross_market_value,
                    weight_pct=weight,
                    color_metric_value=c_val,
                    formatted_color_metric=_format_metric_value(c_val, metric_def.unit, reporting_curr),
                    data_quality_status="VERIFIED",
                )
            )

        summary_data = {
            "entity_id": entity_id,
            "entity_name": entity_display_name,
            "entity_type": entity_type,
            "holdings_count": len(holdings),
            "total_gross_market_value": tot_mkt_val,
            "total_color_metric_value": tot_color_val,
            "formatted_total_color_metric": _format_metric_value(tot_color_val, metric_def.unit, reporting_curr),
        }

        provenance = {
            "source_valuation_module": "M05 — Portfolio Accounting & Valuation",
            "source_classification_module": "M04.02 — Security Classification",
            "source_exposure_module": "M06 — Exposure Management",
            "calculation_timestamp": now_utc.isoformat(),
        }

        return HeatmapDrilldownResponse(
            portfolio_id=portfolio_id,
            entity_id=entity_id,
            entity_type=entity_type,
            entity_name=entity_display_name,
            as_of_date=as_of,
            generated_at=now_utc,
            reporting_currency=reporting_curr,
            color_metric=metric_def,
            area_metric_id=area_metric_id,
            summary=summary_data,
            holdings=holdings,
            total_holdings=len(holdings),
            provenance_details=provenance,
        )


# ---------------------------------------------------------------------------
# Consolidated Coordinator
# ---------------------------------------------------------------------------

class RiskHeatmapsService:
    """Unified service interface for M13.04 — Risk Heatmaps."""

    @classmethod
    def get_metrics_registry(cls) -> MetricRegistryResponse:
        return HeatmapMetricRegistryService.get_registry()

    @classmethod
    async def get_sector_heatmap(
        cls,
        session: AsyncSession,
        portfolio_id: str,
        color_metric_id: str = "unrealized_pnl",
        area_metric_id: str = "gross_market_value",
        base_currency: str = "USD",
        as_of_dt: Optional[datetime] = None,
        override_scale_type: Optional[ScaleType] = None,
        override_palette: Optional[PaletteType] = None,
    ) -> SectorHeatmapResponse:
        return await SectorHeatmapService.get_sector_heatmap(
            session=session,
            portfolio_id=portfolio_id,
            color_metric_id=color_metric_id,
            area_metric_id=area_metric_id,
            base_currency=base_currency,
            as_of_dt=as_of_dt,
            override_scale_type=override_scale_type,
            override_palette=override_palette,
        )

    @classmethod
    async def get_security_heatmap(
        cls,
        session: AsyncSession,
        portfolio_id: str,
        color_metric_id: str = "unrealized_pnl",
        area_metric_id: str = "gross_market_value",
        grouping: HeatmapGrouping = HeatmapGrouping.SECTOR,
        side_filter: HeatmapPositionSide = HeatmapPositionSide.ALL,
        base_currency: str = "USD",
        as_of_dt: Optional[datetime] = None,
        override_scale_type: Optional[ScaleType] = None,
        override_palette: Optional[PaletteType] = None,
    ) -> SecurityHeatmapResponse:
        return await SecurityHeatmapService.get_security_heatmap(
            session=session,
            portfolio_id=portfolio_id,
            color_metric_id=color_metric_id,
            area_metric_id=area_metric_id,
            grouping=grouping,
            side_filter=side_filter,
            base_currency=base_currency,
            as_of_dt=as_of_dt,
            override_scale_type=override_scale_type,
            override_palette=override_palette,
        )

    @classmethod
    async def get_drilldown(
        cls,
        session: AsyncSession,
        portfolio_id: str,
        entity_id: str,
        entity_type: str = "SECTOR",
        color_metric_id: str = "unrealized_pnl",
        area_metric_id: str = "gross_market_value",
        base_currency: str = "USD",
        as_of_dt: Optional[datetime] = None,
    ) -> HeatmapDrilldownResponse:
        return await HeatmapDrillthroughService.get_drilldown(
            session=session,
            portfolio_id=portfolio_id,
            entity_id=entity_id,
            entity_type=entity_type,
            color_metric_id=color_metric_id,
            area_metric_id=area_metric_id,
            base_currency=base_currency,
            as_of_dt=as_of_dt,
        )
