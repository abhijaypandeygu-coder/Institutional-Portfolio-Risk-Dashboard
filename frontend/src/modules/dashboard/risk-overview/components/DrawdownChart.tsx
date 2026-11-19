import React from 'react';
import { UnderwaterChartPoint } from '../../../../types/dashboard';
import { formatPercentage, formatCurrency } from '../../../../utils/financialFormatting';

interface DrawdownChartProps {
  points?: UnderwaterChartPoint[] | null;
  baseCurrency?: string;
}

export const DrawdownChart: React.FC<DrawdownChartProps> = ({ points, baseCurrency = 'USD' }) => {
  if (!points || points.length === 0) {
    return (
      <div className="bg-surface border border-line rounded-lg p-5 text-center">
        <h3 className="text-sm font-semibold text-secondary mb-2">Historical Drawdown Underwater Series</h3>
        <p className="text-xs text-muted">No authoritative drawdown series points available for this period.</p>
      </div>
    );
  }

  // Calculate stats
  const minDrawdown = Math.min(...points.map((p) => p.drawdown_pct));
  const latest = points[points.length - 1];

  return (
    <div className="bg-surface border border-line rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-secondary">Underwater Drawdown Profile</h3>
          <p className="text-xs text-muted mt-0.5">
            Depth of portfolio decline below previous high-water mark across {points.length} observation sessions.
          </p>
        </div>
        <div className="text-right">
          <span className="text-xs text-muted block">Worst Observed in Period</span>
          <span className="text-sm font-bold text-negative">{formatPercentage(minDrawdown)}</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-secondary">
          <thead className="text-[11px] uppercase  text-muted border-b border-line bg-canvas/60">
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
              <tr key={idx} className="hover:bg-subtle/30 transition">
                <td className="py-2 px-3 font-sans text-secondary">{pt.observation_date}</td>
                <td className="py-2 px-3">{formatCurrency(pt.portfolio_nav, baseCurrency)}</td>
                <td className="py-2 px-3">{formatCurrency(pt.high_water_mark, baseCurrency)}</td>
                <td className={`py-2 px-3 text-right font-medium ${pt.drawdown_pct < 0 ? 'text-negative' : 'text-secondary'}`}>
                  {formatPercentage(pt.drawdown_pct)}
                </td>
                <td className="py-2 px-3 text-right font-sans text-muted">
                  {formatCurrency(pt.drawdown_amount, baseCurrency)}
                </td>
                <td className="py-2 px-3 text-center">
                  {pt.is_trough && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-negative-soft text-negative border border-negative/20">
                      Trough
                    </span>
                  )}
                  {pt.is_peak && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-positive-soft text-positive border border-positive/20">
                      New Peak
                    </span>
                  )}
                  {pt.is_recovered && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] bg-brand-soft text-brand border border-brand/20">
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
