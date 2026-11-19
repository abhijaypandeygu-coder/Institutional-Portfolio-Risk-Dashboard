import React from 'react';
import { SectorAllocationSummary } from '../../../../types/dashboard';
import { formatCurrency, formatPercentage } from '../../../../utils/financialFormatting';

interface SectorAllocationTableProps {
  summary: SectorAllocationSummary;
  onSelectSector?: (sectorId: string) => void;
}

export const SectorAllocationTable: React.FC<SectorAllocationTableProps> = ({ summary, onSelectSector }) => {
  const { sectors, reporting_currency } = summary;

  return (
    <div className="bg-surface border border-line rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-secondary">M13.03.01 — Sector Capital Allocation</h3>
          <p className="text-xs text-muted mt-0.5">
            Distribution of capital across {sectors.length} sectors using GICS authoritative classifications.
          </p>
        </div>
        <div className="text-xs text-muted">
          Source: <span className="font-sans text-brand font-medium">M06.03 + M04.02</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-secondary">
          <thead className="text-[11px] uppercase  text-muted border-b border-line bg-canvas/60">
            <tr>
              <th className="py-2.5 px-3">Sector</th>
              <th className="py-2.5 px-3 text-right">Net Value</th>
              <th className="py-2.5 px-3 text-right">NAV Weight</th>
              <th className="py-2.5 px-3 text-right">Long Value</th>
              <th className="py-2.5 px-3 text-right">Short Value</th>
              <th className="py-2.5 px-3 text-right">Gross Value</th>
              <th className="py-2.5 px-3 text-center">Instruments</th>
              <th className="py-2.5 px-3 text-center">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {sectors.map((sec) => (
              <tr key={sec.sector_id} className="hover:bg-subtle/30 transition">
                <td className="py-2 px-3">
                  <div className="font-medium text-ink flex items-center space-x-1.5">
                    <span>{sec.sector_name}</span>
                    {sec.is_unclassified && (
                      <span className="px-1.5 py-0.2 rounded text-[10px] bg-warning-soft text-warning border border-warning/20">
                        Unclassified
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] text-muted font-sans">{sec.classification_scheme}</span>
                </td>
                <td className={`py-2 px-3 text-right font-medium ${sec.net_market_value < 0 ? 'text-negative' : 'text-secondary'}`}>
                  {formatCurrency(sec.net_market_value, reporting_currency)}
                </td>
                <td className="py-2 px-3 text-right font-bold text-ink">
                  {formatPercentage(sec.nav_weight_pct)}
                </td>
                <td className="py-2 px-3 text-right text-positive">
                  {formatCurrency(sec.long_market_value, reporting_currency)}
                </td>
                <td className="py-2 px-3 text-right text-negative">
                  {formatCurrency(sec.short_market_value, reporting_currency)}
                </td>
                <td className="py-2 px-3 text-right font-sans text-secondary">
                  {formatCurrency(sec.gross_market_value, reporting_currency)}
                </td>
                <td className="py-2 px-3 text-center font-sans text-muted">
                  {sec.instrument_count}
                </td>
                <td className="py-2 px-3 text-center">
                  <button
                    onClick={() => onSelectSector && onSelectSector(sec.sector_id)}
                    className="px-2 py-1 rounded bg-subtle hover:bg-hover text-brand text-[11px] transition"
                  >
                    Drill Down
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
