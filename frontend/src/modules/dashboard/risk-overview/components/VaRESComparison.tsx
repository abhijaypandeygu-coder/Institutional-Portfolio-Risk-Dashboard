import React from 'react';
import { VaRESComparisonItem } from '../../../../types/dashboard';
import { formatCurrency, formatPercentage } from '../../../../utils/financialFormatting';

interface VaRESComparisonProps {
  comparison?: VaRESComparisonItem | null;
}

export const VaRESComparison: React.FC<VaRESComparisonProps> = ({ comparison }) => {
  if (!comparison) {
    return null;
  }

  const {
    var_monetary_amount,
    var_percentage_of_nav,
    es_monetary_amount,
    es_percentage_of_nav,
    tail_excess_amount,
    tail_excess_pct,
    es_to_var_ratio,
    confidence_level,
    horizon_days,
    reporting_currency,
    is_compatible,
    compatibility_note,
  } = comparison;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">Value at Risk vs. Expected Shortfall Tail Analysis</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Compares quantile loss threshold (VaR) against average modeled loss in the tail (ES) at {(confidence_level * 100).toFixed(1)}% confidence ({horizon_days}d horizon).
          </p>
        </div>
        {!is_compatible && (
          <span className="text-xs px-2.5 py-1 rounded bg-amber-950/60 border border-amber-800 text-amber-300 font-medium">
            Incompatible Configurations
          </span>
        )}
      </div>

      {!is_compatible && compatibility_note && (
        <div className="p-3 mb-4 rounded bg-amber-950/30 border border-amber-800/60 text-xs text-amber-200">
          ⚠️ {compatibility_note}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 bg-slate-950 rounded border border-slate-800/80">
          <span className="text-xs text-slate-400 block mb-1">VaR Loss Quantile (Threshold)</span>
          <div className="text-xl font-bold text-white">
            {formatCurrency(var_monetary_amount, reporting_currency)}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            {formatPercentage(var_percentage_of_nav)} of Portfolio NAV
          </div>
        </div>

        <div className="p-4 bg-slate-950 rounded border border-slate-800/80">
          <span className="text-xs text-slate-400 block mb-1">Expected Shortfall (Average Tail Loss)</span>
          <div className="text-xl font-bold text-amber-400">
            {formatCurrency(es_monetary_amount, reporting_currency)}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            {formatPercentage(es_percentage_of_nav)} of Portfolio NAV
          </div>
        </div>

        <div className="p-4 bg-slate-950 rounded border border-slate-800/80">
          <span className="text-xs text-slate-400 block mb-1">Tail Excess Beyond VaR</span>
          <div className="text-xl font-bold text-rose-400">
            {formatCurrency(tail_excess_amount, reporting_currency)}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            {es_to_var_ratio ? `${es_to_var_ratio.toFixed(2)}x VaR Ratio` : 'N/A'} (Tail Severity)
          </div>
        </div>
      </div>
    </div>
  );
};
