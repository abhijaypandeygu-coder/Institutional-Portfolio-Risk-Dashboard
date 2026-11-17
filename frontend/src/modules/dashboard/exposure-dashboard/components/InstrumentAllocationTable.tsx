import React from 'react';
import { RankedHoldingItem } from '../../../../types/dashboard';
import { formatCurrency, formatPercentage } from '../../../../utils/financialFormatting';

interface InstrumentAllocationTableProps {
  holdings: RankedHoldingItem[];
  reportingCurrency: string;
}

export const InstrumentAllocationTable: React.FC<InstrumentAllocationTableProps> = ({
  holdings,
  reportingCurrency,
}) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">M13.03.02 — Ranked Instrument Holdings</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Ranked by absolute market value exposure across long and short equity holdings.
          </p>
        </div>
        <div className="text-xs text-slate-400">
          Source: <span className="font-mono text-blue-400 font-medium">M06.04 + M05.03</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="text-[11px] uppercase tracking-wider text-slate-400 border-b border-slate-800 bg-slate-950/60">
            <tr>
              <th className="py-2.5 px-3">#</th>
              <th className="py-2.5 px-3">Symbol / Instrument</th>
              <th className="py-2.5 px-3 text-center">Side</th>
              <th className="py-2.5 px-3 text-right">Quantity</th>
              <th className="py-2.5 px-3 text-right">Mark Price</th>
              <th className="py-2.5 px-3 text-right">Market Value</th>
              <th className="py-2.5 px-3 text-right">NAV Weight</th>
              <th className="py-2.5 px-3 text-right">Gross Weight</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {holdings.map((h) => (
              <tr key={`${h.instrument_id}-${h.position_side}`} className="hover:bg-slate-800/30 transition">
                <td className="py-2 px-3 font-mono text-slate-500">{h.rank}</td>
                <td className="py-2 px-3">
                  <div className="font-semibold text-white flex items-center space-x-1.5">
                    <span>{h.symbol}</span>
                    <span className="text-[10px] text-slate-500 font-mono">({h.exchange_code})</span>
                  </div>
                  <div className="text-[11px] text-slate-400 truncate max-w-xs">{h.instrument_name}</div>
                </td>
                <td className="py-2 px-3 text-center">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      h.position_side === 'LONG'
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                        : 'bg-rose-950 text-rose-300 border border-rose-800'
                    }`}
                  >
                    {h.position_side}
                  </span>
                </td>
                <td className="py-2 px-3 text-right font-mono text-slate-300">
                  {h.quantity.toLocaleString()}
                </td>
                <td className="py-2 px-3 text-right font-mono text-slate-300">
                  {formatCurrency(h.mark_price, h.price_currency)}
                </td>
                <td
                  className={`py-2 px-3 text-right font-semibold font-mono ${
                    h.market_value < 0 ? 'text-rose-400' : 'text-slate-100'
                  }`}
                >
                  {formatCurrency(h.market_value, reportingCurrency)}
                </td>
                <td className="py-2 px-3 text-right font-medium text-slate-200">
                  {formatPercentage(h.nav_weight_pct)}
                </td>
                <td className="py-2 px-3 text-right font-mono text-slate-400">
                  {formatPercentage(h.gross_weight_pct)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
