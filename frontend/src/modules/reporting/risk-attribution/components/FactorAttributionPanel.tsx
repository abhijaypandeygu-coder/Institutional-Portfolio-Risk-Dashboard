import React from 'react';
import { Cpu, Sliders, CheckCircle2, AlertTriangle, Layers } from 'lucide-react';
import { FactorContribution } from '../../../../types/riskAttribution';

interface FactorAttributionPanelProps {
  factors: FactorContribution[];
  modelVersion?: string;
}

export const FactorAttributionPanel: React.FC<FactorAttributionPanelProps> = ({
  factors,
  modelVersion,
}) => {
  return (
    <div className="bg-surface border border-line rounded-xl overflow-hidden">
      {/* Header */}
      <div className="p-5 border-b border-line flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-ink flex items-center gap-2">
            <Cpu className="w-4 h-4 text-info" />
            Systematic Factor Risk Contribution
          </h2>
          <p className="text-xs text-muted mt-0.5">
            M08 Multi-Factor Covariance Decomposition (sigma_sys^2 = beta^T Sigma_F beta)
          </p>
        </div>

        {modelVersion && (
          <span className="px-2.5 py-1 rounded bg-purple-500/10 border border-purple-500/20 text-info text-xs font-sans">
            {modelVersion}
          </span>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-canvas/60 border-b border-line text-muted font-semibold uppercase ">
              <th className="py-3 px-4">Rank</th>
              <th className="py-3 px-4">Factor Name</th>
              <th className="py-3 px-4">Category</th>
              <th className="py-3 px-4 text-right">Portfolio Exposure (beta)</th>
              <th className="py-3 px-4 text-right">Marginal RC</th>
              <th className="py-3 px-4 text-right">Component RC</th>
              <th className="py-3 px-4 text-right">Contribution %</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-sans">
            {factors.map((f) => (
              <tr key={f.factor_id} className="hover:bg-subtle/40 transition-colors">
                <td className="py-3 px-4 font-sans text-muted">{f.factor_rank}</td>
                <td className="py-3 px-4 font-sans font-semibold text-secondary">
                  {f.factor_name}
                </td>
                <td className="py-3 px-4 font-sans">
                  <span className="px-2 py-0.5 rounded bg-subtle text-secondary text-[10px]">
                    {f.factor_category}
                  </span>
                </td>
                <td className="py-3 px-4 text-right text-secondary">
                  {f.factor_exposure.toFixed(2)}
                </td>
                <td className="py-3 px-4 text-right text-secondary">
                  {(f.marginal_risk_contribution * 100).toFixed(2)}%
                </td>
                <td className="py-3 px-4 text-right font-semibold text-ink">
                  {(f.component_risk_contribution * 100).toFixed(3)}%
                </td>
                <td className="py-3 px-4 text-right font-semibold text-info">
                  {f.contribution_percentage.toFixed(2)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
