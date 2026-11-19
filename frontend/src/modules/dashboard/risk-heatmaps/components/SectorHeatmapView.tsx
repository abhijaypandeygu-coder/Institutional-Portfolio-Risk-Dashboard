import React from 'react';
import { SectorHeatmapResponse, HeatmapCell } from '../../../../types/dashboard';

interface SectorHeatmapViewProps {
  data: SectorHeatmapResponse;
  onCellClick: (cell: HeatmapCell) => void;
  selectedEntityId?: string | null;
}

export const SectorHeatmapView: React.FC<SectorHeatmapViewProps> = ({
  data,
  onCellClick,
  selectedEntityId,
}) => {
  const allCells = [...data.cells];
  if (data.unclassified_cell) {
    allCells.push(data.unclassified_cell);
  }

  // Sort by area value descending
  const sortedCells = [...allCells].sort((a, b) => b.area_value - a.area_value);

  return (
    <div className="space-y-4">
      {/* Treemap Container */}
      <div className="bg-surface border border-line rounded-lg p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-ink uppercase ">
              Sector Risk & Exposure Treemap
            </h3>
            <p className="text-xs text-muted mt-0.5">
              Area encodes <span className="text-secondary font-medium">{data.area_metric_id.replace(/_/g, ' ')}</span>,
              Color encodes <span className="text-secondary font-medium">{data.color_metric.display_name}</span>. Click cell to inspect constituents.
            </p>
          </div>
          <div className="text-xs text-muted">
            Total Exposure: <strong className="text-ink">{data.reporting_currency} {data.total_area_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
          </div>
        </div>

        {/* Heatmap Grid / Treemap representation */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {sortedCells.map((cell) => {
            const isSelected = selectedEntityId === cell.entity_id;
            const bgHex = cell.color_hex || '#334155';
            const isUnclassified = cell.entity_id === 'UNCLASSIFIED';

            return (
              <div
                key={cell.entity_id}
                onClick={() => onCellClick(cell)}
                style={{
                  backgroundColor: bgHex,
                  minHeight: `${Math.max(100, Math.min(200, (cell.area_weight_pct || 10) * 8))}px`,
                }}
                className={`p-3.5 rounded-lg cursor-pointer transition-opacity duration-150 transform hover:scale-[1.02] flex flex-col justify-between shadow-md relative overflow-hidden border ${
                  isSelected ? 'ring-2 ring-blue-400 border-white' : 'border-line/40 hover:border-line-strong'
                }`}
              >
                {/* Header: Label & Area Weight */}
                <div>
                  <div className="flex items-start justify-between gap-1 text-ink font-bold">
                    <span className="text-sm truncate" title={cell.label}>
                      {cell.label}
                    </span>
                    <span className="text-xs px-1.5 py-0.5 rounded bg-black/20 text-ink ">
                      {cell.area_weight_pct?.toFixed(1) ?? '0.0'}%
                    </span>
                  </div>
                  <div className="text-[11px] text-black/80 font-medium mt-0.5">
                    {cell.sub_label || `${cell.instrument_count} positions`}
                  </div>
                </div>

                {/* Primary Metric Value */}
                <div className="mt-4 pt-2 border-t border-black/10">
                  <div className="text-base font-extrabold text-ink  drop-shadow-sm">
                    {cell.formatted_value}
                  </div>
                  <div className="text-[10px] text-ink/80 font-medium mt-0.5 flex justify-between">
                    <span>Gross: {data.reporting_currency} {(cell.gross_exposure / 1000).toFixed(0)}k</span>
                    <span>Net: {data.reporting_currency} {(cell.net_exposure / 1000).toFixed(0)}k</span>
                  </div>
                </div>

                {isUnclassified && (
                  <div className="absolute top-1 right-1 text-[9px] bg-amber-500 text-black px-1 rounded font-semibold uppercase">
                    Review Needed
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
