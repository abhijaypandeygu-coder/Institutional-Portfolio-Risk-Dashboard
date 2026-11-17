"""
M13.04 — Risk Heatmaps Router.

Endpoints for:
1. Metric Registry: Supported metrics, definitions, semantic direction, default palettes
2. Sector Heatmap: Sector-level treemap representation (area vs color encoding)
3. Security Heatmap: Holdings-level heatmap with grouping and long/short filtering
4. Heatmap Drill-Through: Underlying positions breakdown and valuation provenance
"""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.modules.dashboard_visualization.risk_heatmaps.schemas.risk_heatmaps_schemas import (
    MetricRegistryResponse,
    SectorHeatmapResponse,
    SecurityHeatmapResponse,
    HeatmapDrilldownResponse,
    ScaleType,
    PaletteType,
    HeatmapGrouping,
    HeatmapPositionSide,
)
from backend.app.modules.dashboard_visualization.risk_heatmaps.services.risk_heatmaps_service import RiskHeatmapsService

router = APIRouter()


@router.get(
    "/risk-heatmaps/metrics",
    response_model=MetricRegistryResponse,
    summary="Get Risk Heatmap Metric Registry",
    description="Returns list of all supported metrics, unit types, categories, and default scales.",
)
async def get_metrics_registry() -> MetricRegistryResponse:
    return RiskHeatmapsService.get_metrics_registry()


@router.get(
    "/{portfolio_id}/risk-heatmaps/sectors",
    response_model=SectorHeatmapResponse,
    summary="Get Sector Heatmap",
    description="Returns aggregated sector heatmap cells with area weight and color metric values.",
)
async def get_sector_heatmap(
    portfolio_id: str = Path(..., description="Unique portfolio ID"),
    color_metric: str = Query("unrealized_pnl", description="Metric ID for color dimension"),
    area_metric: str = Query("gross_market_value", description="Metric ID for cell size/area"),
    base_currency: str = Query("USD", description="Base reporting currency"),
    scale_type: Optional[ScaleType] = Query(None, description="Override color scale type"),
    palette: Optional[PaletteType] = Query(None, description="Override color palette"),
    session: AsyncSession = Depends(get_db),
) -> SectorHeatmapResponse:
    return await RiskHeatmapsService.get_sector_heatmap(
        session=session,
        portfolio_id=portfolio_id,
        color_metric_id=color_metric,
        area_metric_id=area_metric,
        base_currency=base_currency,
        override_scale_type=scale_type,
        override_palette=palette,
    )


@router.get(
    "/{portfolio_id}/risk-heatmaps/securities",
    response_model=SecurityHeatmapResponse,
    summary="Get Security Heatmap",
    description="Returns holdings-level heatmap cells grouped by sector or industry with position side filtering.",
)
async def get_security_heatmap(
    portfolio_id: str = Path(..., description="Unique portfolio ID"),
    color_metric: str = Query("unrealized_pnl", description="Metric ID for color dimension"),
    area_metric: str = Query("gross_market_value", description="Metric ID for cell size/area"),
    grouping: HeatmapGrouping = Query(HeatmapGrouping.SECTOR, description="Grouping hierarchy (SECTOR, INDUSTRY, SIDE, NONE)"),
    side_filter: HeatmapPositionSide = Query(HeatmapPositionSide.ALL, description="Filter positions (ALL, LONG, SHORT)"),
    base_currency: str = Query("USD", description="Base reporting currency"),
    scale_type: Optional[ScaleType] = Query(None, description="Override color scale type"),
    palette: Optional[PaletteType] = Query(None, description="Override color palette"),
    session: AsyncSession = Depends(get_db),
) -> SecurityHeatmapResponse:
    return await RiskHeatmapsService.get_security_heatmap(
        session=session,
        portfolio_id=portfolio_id,
        color_metric_id=color_metric,
        area_metric_id=area_metric,
        grouping=grouping,
        side_filter=side_filter,
        base_currency=base_currency,
        override_scale_type=scale_type,
        override_palette=palette,
    )


@router.get(
    "/{portfolio_id}/risk-heatmaps/drilldown",
    response_model=HeatmapDrilldownResponse,
    summary="Get Heatmap Cell Drill-Through",
    description="Resolves clicked sector or security cell into underlying holdings, weights, and model provenance.",
)
async def get_heatmap_drilldown(
    portfolio_id: str = Path(..., description="Unique portfolio ID"),
    entity_id: str = Query(..., description="Sector name or Instrument ID"),
    entity_type: str = Query("SECTOR", description="'SECTOR' or 'SECURITY'"),
    color_metric: str = Query("unrealized_pnl", description="Metric ID for color dimension"),
    area_metric: str = Query("gross_market_value", description="Metric ID for cell size/area"),
    base_currency: str = Query("USD", description="Base reporting currency"),
    session: AsyncSession = Depends(get_db),
) -> HeatmapDrilldownResponse:
    return await RiskHeatmapsService.get_drilldown(
        session=session,
        portfolio_id=portfolio_id,
        entity_id=entity_id,
        entity_type=entity_type,
        color_metric_id=color_metric,
        area_metric_id=area_metric,
        base_currency=base_currency,
    )
