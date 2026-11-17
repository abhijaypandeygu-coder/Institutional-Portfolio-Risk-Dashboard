import React from 'react';
import { PortfolioAllocationSummary } from '../../../../types/dashboard';
import { formatCurrency, formatPercentage } from '../../../../utils/financialFormatting';

interface PortfolioAllocationCardProps {
  summary: PortfolioAllocationSummary;
}

export const PortfolioAllocationCard: React.FC<PortfolioAllocationCardProps> = ({ summary }) => {
  const {
    total_nav,
    total_long_position_value,
    total_short_position_value,
    net_position_value,
    gross_position_exposure,
    total_cash_value,
    invested_nav_weight_pct,
    cash_nav_weight_pct,
    gross_exposure_to_nav_ratio,
    reconciliation_status,
    reporting_currency,
  } = summary;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">M13.03.03 — Capital & Cash Composition</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Breakdown of Net Asset Value (NAV) between invested equity positions and cash balances.
          </p>
        </div>
        <span
          className={`text-xs px-2.5 py-0.5 rounded font-medium border ${
            reconciliation_status === 'RECONCILED'
              ? 'bg-emerald-950/60 border-emerald-800 text-emerald-300'
              : 'bg-amber-950/60 border-amber-800 text-amber-300'
          }`}
        >
          {reconciliation_status}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div className="p-3.5 bg-slate-950 rounded border border-slate-800">
          <span className="text-[11px] text-slate-400 block mb-1">Total Portfolio NAV</span>
          <div className="text-xl font-bold text-white">{formatCurrency(total_nav, reporting_currency)}</div>
          <span className="text-[10px] text-slate-500">100.0% Base Allocation</span>
        </div>

        <div className="p-3.5 bg-slate-950 rounded border border-slate-800">
          <span className="text-[11px] text-slate-400 block mb-1">Invested Position Value</span>
          <div className="text-xl font-bold text-blue-400">{formatCurrency(net_position_value, reporting_currency)}</div>
          <span className="text-[10px] text-slate-400">{formatPercentage(invested_nav_weight_pct)} of NAV</span>
        </div>

        <div className="p-3.5 bg-slate-950 rounded border border-slate-800">
          <span className="text-[11px] text-slate-400 block mb-1">Total Cash Reserves</span>
          <div className="text-xl font-bold text-emerald-400">{formatCurrency(total_cash_value, reporting_currency)}</div>
          <span className="text-[10px] text-slate-400">{formatPercentage(cash_nav_weight_pct)} of NAV</span>
        </div>

        <div className="p-3.5 bg-slate-950 rounded border border-slate-800">
          <span className="text-[11px] text-slate-400 block mb-1">Gross Exposure / NAV</span>
          <div className="text-xl font-bold text-purple-400">{gross_exposure_to_nav_ratio.toFixed(2)}x</div>
          <span className="text-[10px] text-slate-400">{formatCurrency(gross_position_exposure, reporting_currency)} Gross</span>
        </div>
      </div>

      {/* Long vs Short breakdown bar */}
      <div className="p-3.5 bg-slate-950 rounded border border-slate-800 flex items-center justify-between text-xs text-slate-300">
        <div>
          <span className="text-slate-500 mr-2">Long Value:</span>
          <span className="font-semibold text-emerald-400">{formatCurrency(total_long_position_value, reporting_currency)}</span>
        </div>
        <div>
          <span className="text-slate-500 mr-2">Short Value:</span>
          <span className="font-semibold text-rose-400">{formatCurrency(total_short_position_value, reporting_currency)}</span>
        </div>
        <div>
          <span className="text-slate-500 mr-2">Net Directional Value:</span>
          <span className={`font-semibold ${net_position_value < 0 ? 'text-rose-400' : 'text-slate-200'}`}>
            {formatCurrency(net_position_value, reporting_currency)}
          </span>
        </div>
      </div>
    </div>
  );
};
