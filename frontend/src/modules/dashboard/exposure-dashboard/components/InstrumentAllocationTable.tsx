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
    <div className="bg-surface border border-line rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-secondary">M13.03.02 — Ranked Instrument Holdings</h3>
          <p className="text-xs text-muted mt-0.5">
            Ranked by absolute market value exposure across long and short equity holdings.
          </p>
        </div>
        <div className="text-xs text-muted">
          Source: <span className="font-sans text-brand font-medium">M06.04 + M05.03</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-secondary">
          <thead className="text-[11px] uppercase  text-muted border-b border-line bg-canvas/60">
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
              <tr key={`${h.instrument_id}-${h.position_side}`} className="hover:bg-subtle/30 transition">
                <td className="py-2 px-3 font-sans text-muted">{h.rank}</td>
                <td className="py-2 px-3">
                  <div className="font-semibold text-ink flex items-center space-x-1.5">
                    <span>{h.symbol}</span>
                    <span className="text-[10px] text-muted font-sans">({h.exchange_code})</span>
                  </div>
                  <div className="text-[11px] text-muted truncate max-w-xs">{h.instrument_name}</div>
                </td>
                <td className="py-2 px-3 text-center">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      h.position_side === 'LONG'
                        ? 'bg-positive-soft text-positive border border-positive/20'
                        : 'bg-negative-soft text-negative border border-negative/20'
                    }`}
                  >
                    {h.position_side}
                  </span>
                </td>
                <td className="py-2 px-3 text-right font-sans text-secondary">
                  {h.quantity.toLocaleString()}
                </td>
                <td className="py-2 px-3 text-right font-sans text-secondary">
                  {formatCurrency(h.mark_price, h.price_currency)}
                </td>
                <td
                  className={`py-2 px-3 text-right font-semibold font-sans ${
                    h.market_value < 0 ? 'text-negative' : 'text-ink'
                  }`}
                >
                  {formatCurrency(h.market_value, reportingCurrency)}
                </td>
                <td className="py-2 px-3 text-right font-medium text-secondary">
                  {formatPercentage(h.nav_weight_pct)}
                </td>
                <td className="py-2 px-3 text-right font-sans text-muted">
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
