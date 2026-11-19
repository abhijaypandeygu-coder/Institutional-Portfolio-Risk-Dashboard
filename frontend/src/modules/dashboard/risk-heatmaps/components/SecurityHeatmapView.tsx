import React from 'react';
import { SecurityHeatmapResponse, HeatmapCell } from '../../../../types/dashboard';

interface SecurityHeatmapViewProps {
  data: SecurityHeatmapResponse;
  onCellClick: (cell: HeatmapCell) => void;
  selectedEntityId?: string | null;
}

export const SecurityHeatmapView: React.FC<SecurityHeatmapViewProps> = ({
  data,
  onCellClick,
  selectedEntityId,
}) => {
  // If grouping is enabled and groups are returned
  if (data.groups && data.groups.length > 0) {
    return (
      <div className="space-y-6">
        {data.groups.map((group) => (
          <div key={group.group_id} className="bg-surface border border-line rounded-lg p-4 shadow-sm">
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-line">
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-semibold text-ink">{group.group_name}</h4>
                <span className="text-xs text-muted">({group.cells.length} holdings)</span>
              </div>
              <div className="text-xs text-muted">
                Weight: <strong className="text-secondary">{group.group_area_pct.toFixed(1)}%</strong> | Gross:{' '}
                <strong className="text-secondary">{data.reporting_currency} {group.group_area_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</strong>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2.5">
              {group.cells.map((cell) => renderSecurityCell(cell, data.reporting_currency, onCellClick, selectedEntityId))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Flat list fallback
  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-ink uppercase ">
            Holdings Risk Heatmap ({data.total_securities} Positions)
          </h3>
          <p className="text-xs text-muted mt-0.5">
            Color encodes <strong className="text-secondary">{data.color_metric.display_name}</strong>.
          </p>
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2.5">
        {data.cells.map((cell) => renderSecurityCell(cell, data.reporting_currency, onCellClick, selectedEntityId))}
      </div>
    </div>
  );
};

function renderSecurityCell(
  cell: HeatmapCell,
  currency: string,
  onCellClick: (cell: HeatmapCell) => void,
  selectedEntityId?: string | null
) {
  const isSelected = selectedEntityId === cell.entity_id;
  const bgHex = cell.color_hex || '#334155';
  const side = cell.metadata?.position_side as string || (cell.short_exposure > 0 ? 'SHORT' : 'LONG');

  return (
    <div
      key={cell.entity_id}
      onClick={() => onCellClick(cell)}
      style={{ backgroundColor: bgHex }}
      className={`p-2.5 rounded-lg cursor-pointer transition-opacity duration-150 transform hover:scale-[1.03] flex flex-col justify-between shadow-sm border ${
        isSelected ? 'ring-2 ring-blue-400 border-white' : 'border-line/40 hover:border-line'
      }`}
    >
      <div>
        <div className="flex items-center justify-between text-ink font-bold text-xs">
          <span className="truncate" title={cell.label}>{cell.label}</span>
          <span className={`text-[10px] px-1 rounded uppercase ${side === 'SHORT' ? 'bg-warning-soft/30 text-warning' : 'bg-black/20 text-ink'}`}>
            {side}
          </span>
        </div>
        <div className="text-[10px] text-ink/80 truncate mt-0.5" title={cell.metadata?.instrument_name as string}>
          {cell.metadata?.instrument_name as string || cell.sub_label || ''}
        </div>
      </div>

      <div className="mt-3 pt-1 border-t border-black/10">
        <div className="text-xs font-extrabold text-ink ">
          {cell.formatted_value}
        </div>
        <div className="text-[10px] text-ink/70 mt-0.5 flex justify-between">
          <span>{currency} {(cell.area_value / 1000).toFixed(0)}k</span>
          <span>{cell.area_weight_pct?.toFixed(1) ?? '0.0'}%</span>
        </div>
      </div>
    </div>
  );
}
