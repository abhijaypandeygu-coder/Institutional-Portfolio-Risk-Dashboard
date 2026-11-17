import React from 'react';
import {
  Sliders,
  AlertOctagon,
  Scale,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import {
  SensitivityItem,
  LimitImplication,
} from '../../../../types/stressReport';

interface SensitivityAndLimitsProps {
  sensitivities: SensitivityItem[];
  limits: LimitImplication[];
}

export const SensitivityAndLimits: React.FC<SensitivityAndLimitsProps> = ({
  sensitivities,
  limits,
}) => {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* 1. Sensitivity Analysis Summary */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden flex flex-col">
        <div className="p-5 border-b border-slate-800">
          <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <Sliders className="w-4 h-4 text-cyan-400" />
            Sensitivity Analysis (Alternative Shock Assumptions)
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Portfolio outcome changes across alternative market decline levels
          </p>
        </div>

        <div className="p-5 space-y-3 flex-1">
          {sensitivities.map((s, idx) => (
            <div
              key={idx}
              className="bg-slate-950 border border-slate-800/80 rounded-lg p-3.5 flex items-center justify-between"
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-200">
                    {s.assumption_name} ({s.assumption_value})
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {s.sensitivity_dimension}
                  </span>
                </div>
                <div className="text-[11px] text-slate-400 mt-1 font-mono">
                  Incremental Loss: ${Math.abs(s.incremental_loss).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </div>
              </div>

              <div className="text-right font-mono">
                <div className="text-sm font-bold text-rose-400">
                  -${Math.abs(s.stressed_pnl).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </div>
                <div className="text-xs text-rose-300 font-semibold">
                  {s.impact_percentage.toFixed(2)}% NAV
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 2. Stress Limit Implications */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden flex flex-col">
        <div className="p-5 border-b border-slate-800">
          <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <AlertOctagon className="w-4 h-4 text-amber-400" />
            Projected Risk-Limit Implications
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Hypothetical limit utilization derived from M11 Risk Limit Framework
          </p>
        </div>

        <div className="p-5 space-y-3 flex-1 overflow-y-auto max-h-[460px]">
          {limits.map((l) => {
            const isExceed = l.is_projected_exceedance;
            return (
              <div
                key={l.limit_id}
                className="bg-slate-950 border border-slate-800/80 rounded-lg p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <div className="text-xs font-bold text-slate-200">{l.limit_name}</div>
                    <div className="text-[10px] text-slate-500 font-mono">
                      {l.limit_id} • Policy {l.limit_policy_version}
                    </div>
                  </div>

                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${
                      isExceed
                        ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                        : l.evaluation_status === 'APPROACHING_LIMIT'
                        ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                        : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    }`}
                  >
                    {isExceed ? (
                      <AlertTriangle className="w-3 h-3" />
                    ) : (
                      <CheckCircle2 className="w-3 h-3" />
                    )}
                    {l.evaluation_status}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-xs font-mono py-2 border-y border-slate-800/60 my-2">
                  <div>
                    <span className="text-[10px] text-slate-500 block font-sans">Threshold</span>
                    <span className="text-slate-300">${l.configured_threshold.toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 block font-sans">Stressed Metric</span>
                    <span className="text-slate-300">${l.stressed_metric.toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 block font-sans">Utilization</span>
                    <span className={isExceed ? 'text-rose-400 font-bold' : 'text-slate-300'}>
                      {l.utilization_percentage.toFixed(1)}%
                    </span>
                  </div>
                </div>

                {isExceed && (
                  <p className="text-[11px] text-amber-400/90 leading-relaxed mt-1">
                    Projected exceedance of ${Math.abs(l.difference_from_threshold).toLocaleString()}. Represents hypothetical stress outcome, not an active breach.
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
