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
      <div className="bg-surface border border-line rounded-xl overflow-hidden flex flex-col">
        <div className="p-5 border-b border-line">
          <h2 className="text-base font-semibold text-ink flex items-center gap-2">
            <Sliders className="w-4 h-4 text-brand" />
            Sensitivity Analysis (Alternative Shock Assumptions)
          </h2>
          <p className="text-xs text-muted mt-0.5">
            Portfolio outcome changes across alternative market decline levels
          </p>
        </div>

        <div className="p-5 space-y-3 flex-1">
          {sensitivities.map((s, idx) => (
            <div
              key={idx}
              className="bg-canvas border border-line/80 rounded-lg p-3.5 flex items-center justify-between"
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-secondary">
                    {s.assumption_name} ({s.assumption_value})
                  </span>
                  <span className="text-[10px] text-muted font-sans">
                    {s.sensitivity_dimension}
                  </span>
                </div>
                <div className="text-[11px] text-muted mt-1 font-sans">
                  Incremental Loss: ${Math.abs(s.incremental_loss).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </div>
              </div>

              <div className="text-right font-sans">
                <div className="text-sm font-bold text-negative">
                  -${Math.abs(s.stressed_pnl).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </div>
                <div className="text-xs text-negative font-semibold">
                  {s.impact_percentage.toFixed(2)}% NAV
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 2. Stress Limit Implications */}
      <div className="bg-surface border border-line rounded-xl overflow-hidden flex flex-col">
        <div className="p-5 border-b border-line">
          <h2 className="text-base font-semibold text-ink flex items-center gap-2">
            <AlertOctagon className="w-4 h-4 text-warning" />
            Projected Risk-Limit Implications
          </h2>
          <p className="text-xs text-muted mt-0.5">
            Hypothetical limit utilization derived from M11 Risk Limit Framework
          </p>
        </div>

        <div className="p-5 space-y-3 flex-1 overflow-y-auto max-h-[460px]">
          {limits.map((l) => {
            const isExceed = l.is_projected_exceedance;
            return (
              <div
                key={l.limit_id}
                className="bg-canvas border border-line/80 rounded-lg p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <div className="text-xs font-bold text-secondary">{l.limit_name}</div>
                    <div className="text-[10px] text-muted font-sans">
                      {l.limit_id} • Policy {l.limit_policy_version}
                    </div>
                  </div>

                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${
                      isExceed
                        ? 'bg-rose-500/10 text-negative border border-rose-500/20'
                        : l.evaluation_status === 'APPROACHING_LIMIT'
                        ? 'bg-amber-500/10 text-warning border border-amber-500/20'
                        : 'bg-brand/10 text-positive border border-emerald-500/20'
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

                <div className="grid grid-cols-3 gap-2 text-xs font-sans py-2 border-y border-line/60 my-2">
                  <div>
                    <span className="text-[10px] text-muted block font-sans">Threshold</span>
                    <span className="text-secondary">${l.configured_threshold.toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-muted block font-sans">Stressed Metric</span>
                    <span className="text-secondary">${l.stressed_metric.toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-muted block font-sans">Utilization</span>
                    <span className={isExceed ? 'text-negative font-bold' : 'text-secondary'}>
                      {l.utilization_percentage.toFixed(1)}%
                    </span>
                  </div>
                </div>

                {isExceed && (
                  <p className="text-[11px] text-warning/90 leading-relaxed mt-1">
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
