import React from 'react';
import { UnderwaterChartPoint } from '../../../types/dashboard';
import { formatPercentage, formatCurrency } from '../../../utils/financialFormatting';

interface DrawdownChartProps {
  points?: UnderwaterChartPoint[] | null;
  baseCurrency?: string;
}

export const DrawdownChart: React.FC<DrawdownChartProps> = ({ points, baseCurrency = 'USD' }) => {
  if (!points || points.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 text-center">
        <h3 className="text-sm font-semibold text-slate-300 mb-2">Historical Drawdown Underwater Series</h3>
        <p className="text-xs text-slate-500">No authoritative drawdown series points available for this period.</p>
      </div>
    );
  }

  // Calculate stats
  const minDrawdown = Math.min(...points.map((p) => p.drawdown_pct));
  const latest = points[points.length - 1];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">Underwater Drawdown Profile</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Depth of portfolio decline below previous high-water mark across {points.length} observation sessions.
          </p>
        </div>
        <div className="text-right">
          <span className="text-xs text-slate-400 block">Worst Observed in Period</span>
          <span className="text-sm font-bold text-rose-400">{formatPercentage(minDrawdown)}</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-950/60">
            <tr>
              <th className="py-2.5 px-3">Date</th>
              <th className="py-2.5 px-3">Portfolio NAV</th>
              <th className="py-2.5 px-3">High-Water Mark</th>
              <th className="py-2.5 px-3 text-right">Drawdown %</th>
              <th className="py-2.5 px-3 text-right">Monetary Drawdown</th>
              <th className="py-2.5 px-3 text-center">Event Marker</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {points.slice(-10).reverse().map((pt, idx) => (
              <tr key={idx} className="hover:bg-slate-800/30 transition">
                <td className="py-2 px-3 font-mono text-slate-300">{pt.observation_date}</td>
                <td className="py-2 px-3">{formatCurrency(pt.portfolio_nav, baseCurrency)}</td>
                <td className="py-2 px-3">{formatCurrency(pt.high_water_mark, baseCurrency)}</td>
                <td className={`py-2 px-3 text-right font-medium ${pt.drawdown_pct < 0 ? 'text-rose-400' : 'text-slate-300'}`}>
                  {formatPercentage(pt.drawdown_pct)}
                </td>
                <td className="py-2 px-3 text-right font-mono text-slate-400">
                  {formatCurrency(pt.drawdown_amount, baseCurrency)}
                </td>
                <td className="py-2 px-3 text-center">
                  {pt.is_trough && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-rose-950 text-rose-300 border border-rose-800">
                      Trough
                    </span>
                  )}
                  {pt.is_peak && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800">
                      New Peak
                    </span>
                  )}
                  {pt.is_recovered && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-blue-950 text-blue-300 border border-blue-800">
                      Recovered
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
