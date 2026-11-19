import React from 'react';
import { 
  HeatmapMetricDefinition, 
  HeatmapScaleType, 
  HeatmapPaletteType, 
  ColorScaleConfig,
  HeatmapPositionSide,
  HeatmapGrouping
} from '../../../../types/dashboard';

interface ColorScaleControlsProps {
  metrics: HeatmapMetricDefinition[];
  selectedColorMetric: string;
  onSelectColorMetric: (metricId: string) => void;
  selectedAreaMetric: string;
  onSelectAreaMetric: (metricId: string) => void;
  scaleConfig?: ColorScaleConfig | null;
  selectedScaleType?: HeatmapScaleType;
  onSelectScaleType?: (st: HeatmapScaleType) => void;
  selectedPalette?: HeatmapPaletteType;
  onSelectPalette?: (pal: HeatmapPaletteType) => void;
  viewMode: 'SECTOR' | 'SECURITY';
  onViewModeChange: (mode: 'SECTOR' | 'SECURITY') => void;
  sideFilter?: HeatmapPositionSide;
  onSideFilterChange?: (side: HeatmapPositionSide) => void;
  grouping?: HeatmapGrouping;
  onGroupingChange?: (grp: HeatmapGrouping) => void;
}

export const ColorScaleControls: React.FC<ColorScaleControlsProps> = ({
  metrics,
  selectedColorMetric,
  onSelectColorMetric,
  selectedAreaMetric,
  onSelectAreaMetric,
  scaleConfig,
  selectedScaleType,
  onSelectScaleType,
  selectedPalette,
  onSelectPalette,
  viewMode,
  onViewModeChange,
  sideFilter,
  onSideFilterChange,
  grouping,
  onGroupingChange,
}) => {
  const currentMetric = metrics.find(m => m.metric_id === selectedColorMetric);

  return (
    <div className="bg-surface border border-line rounded-lg p-4 mb-6 shadow-sm">
      {/* Top Bar: View Mode, Metric Pickers, Side Filter */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-line">
        <div className="flex items-center gap-3">
          <span className="text-xs uppercase  text-muted font-semibold">View Dimension:</span>
          <div className="inline-flex rounded-md shadow-sm" role="group">
            <button
              type="button"
              onClick={() => onViewModeChange('SECTOR')}
              className={`px-3 py-1.5 text-xs font-medium rounded-l-lg border transition-colors ${
                viewMode === 'SECTOR'
                  ? 'bg-brand text-white border-brand/20'
                  : 'bg-subtle text-secondary border-line-strong hover:bg-hover'
              }`}
            >
              Sector Heatmap
            </button>
            <button
              type="button"
              onClick={() => onViewModeChange('SECURITY')}
              className={`px-3 py-1.5 text-xs font-medium rounded-r-lg border transition-colors ${
                viewMode === 'SECURITY'
                  ? 'bg-brand text-white border-brand/20'
                  : 'bg-subtle text-secondary border-line-strong hover:bg-hover'
              }`}
            >
              Holdings Heatmap
            </button>
          </div>

          {viewMode === 'SECURITY' && onSideFilterChange && (
            <div className="flex items-center gap-2 ml-4">
              <span className="text-xs text-muted">Position Side:</span>
              <select
                value={sideFilter || 'ALL'}
                onChange={(e) => onSideFilterChange(e.target.value as HeatmapPositionSide)}
                className="bg-subtle border border-line-strong text-xs rounded px-2.5 py-1 text-secondary focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="ALL">All Positions</option>
                <option value="LONG">Longs Only</option>
                <option value="SHORT">Shorts Only</option>
              </select>
            </div>
          )}

          {viewMode === 'SECURITY' && onGroupingChange && (
            <div className="flex items-center gap-2 ml-2">
              <span className="text-xs text-muted">Group By:</span>
              <select
                value={grouping || 'SECTOR'}
                onChange={(e) => onGroupingChange(e.target.value as HeatmapGrouping)}
                className="bg-subtle border border-line-strong text-xs rounded px-2.5 py-1 text-secondary focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="SECTOR">Sector</option>
                <option value="INDUSTRY">Industry</option>
                <option value="SIDE">Side (Long / Short)</option>
                <option value="NONE">Ungrouped</option>
              </select>
            </div>
          )}
        </div>

        {/* Metric Selectors */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted">Cell Color (Metric):</label>
            <select
              value={selectedColorMetric}
              onChange={(e) => onSelectColorMetric(e.target.value)}
              className="bg-subtle border border-line-strong text-xs rounded px-2.5 py-1.5 text-ink font-medium focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {metrics.map(m => (
                <option key={m.metric_id} value={m.metric_id}>
                  {m.display_name} ({m.category})
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-muted">Cell Area (Weight):</label>
            <select
              value={selectedAreaMetric}
              onChange={(e) => onSelectAreaMetric(e.target.value)}
              className="bg-subtle border border-line-strong text-xs rounded px-2.5 py-1.5 text-secondary focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="gross_market_value">Gross Market Value</option>
              <option value="net_market_value">Absolute Net Market Value</option>
            </select>
          </div>
        </div>
      </div>

      {/* Bottom Bar: Scale Details, Legend Bar, and Semantic Badges */}
      <div className="flex flex-wrap items-center justify-between gap-4 pt-3 text-xs">
        <div className="flex items-center gap-3">
          {currentMetric && (
            <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-subtle text-brand border border-line-strong">
              {currentMetric.semantic_direction.replace(/_/g, ' ')}
            </span>
          )}
          {scaleConfig && (
            <span className="text-muted">
              Domain: <strong className="text-secondary">{scaleConfig.min_value?.toLocaleString() ?? 0}</strong> to{' '}
              <strong className="text-secondary">{scaleConfig.max_value?.toLocaleString() ?? 0}</strong>
              {scaleConfig.scale_type === 'DIVERGING' && ' (Symmetric Zero Midpoint)'}
            </span>
          )}
          {scaleConfig && scaleConfig.clipped_outliers_count > 0 && (
            <span className="text-warning bg-warning-soft/40 border border-warning/20 px-2 py-0.5 rounded">
              {scaleConfig.clipped_outliers_count} Outlier(s) Clipped
            </span>
          )}
        </div>

        {/* Visual Gradient Legend Bar */}
        <div className="flex items-center gap-2">
          <span className="text-muted text-[11px]">Adverse</span>
          <div className="h-3.5 w-36 rounded overflow-hidden flex shadow-inner">
            <div className="h-full flex-1 bg-red-700" title="Negative Extreme" />
            <div className="h-full flex-1 bg-red-500" />
            <div className="h-full flex-1 bg-red-300" />
            <div className="h-full w-2 bg-line-strong" title="Zero / Neutral" />
            <div className="h-full flex-1 bg-emerald-300" />
            <div className="h-full flex-1 bg-brand" />
            <div className="h-full flex-1 bg-positive-soft" title="Positive Extreme" />
          </div>
          <span className="text-muted text-[11px]">Favorable</span>
        </div>
      </div>
    </div>
  );
};
