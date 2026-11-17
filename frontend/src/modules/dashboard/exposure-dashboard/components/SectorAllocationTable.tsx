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
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">M13.03.01 — Sector Capital Allocation</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Distribution of capital across {sectors.length} sectors using GICS authoritative classifications.
          </p>
        </div>
        <div className="text-xs text-slate-400">
          Source: <span className="font-mono text-blue-400 font-medium">M06.03 + M04.02</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-950/60">
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
              <tr key={sec.sector_id} className="hover:bg-slate-800/30 transition">
                <td className="py-2 px-3">
                  <div className="font-medium text-white flex items-center space-x-1.5">
                    <span>{sec.sector_name}</span>
                    {sec.is_unclassified && (
                      <span className="px-1.5 py-0.2 rounded text-[10px] bg-amber-950 text-amber-300 border border-amber-800">
                        Unclassified
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] text-slate-500 font-mono">{sec.classification_scheme}</span>
                </td>
                <td className={`py-2 px-3 text-right font-medium ${sec.net_market_value < 0 ? 'text-rose-400' : 'text-slate-200'}`}>
                  {formatCurrency(sec.net_market_value, reporting_currency)}
                </td>
                <td className="py-2 px-3 text-right font-bold text-slate-100">
                  {formatPercentage(sec.nav_weight_pct)}
                </td>
                <td className="py-2 px-3 text-right text-emerald-400">
                  {formatCurrency(sec.long_market_value, reporting_currency)}
                </td>
                <td className="py-2 px-3 text-right text-rose-400">
                  {formatCurrency(sec.short_market_value, reporting_currency)}
                </td>
                <td className="py-2 px-3 text-right font-mono text-slate-300">
                  {formatCurrency(sec.gross_market_value, reporting_currency)}
                </td>
                <td className="py-2 px-3 text-center font-mono text-slate-400">
                  {sec.instrument_count}
                </td>
                <td className="py-2 px-3 text-center">
                  <button
                    onClick={() => onSelectSector && onSelectSector(sec.sector_id)}
                    className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-blue-400 text-[11px] transition"
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
