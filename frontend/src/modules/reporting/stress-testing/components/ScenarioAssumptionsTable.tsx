import React from 'react';
import {
  FileText,
  AlertTriangle,
  Clock,
  Layers,
  ChevronRight,
  TrendingDown,
} from 'lucide-react';
import { ScenarioDescription } from '../../../../types/stressReport';

interface ScenarioAssumptionsTableProps {
  scenarios: ScenarioDescription[];
}

export const ScenarioAssumptionsTable: React.FC<ScenarioAssumptionsTableProps> = ({
  scenarios,
}) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
      <div className="p-5 border-b border-slate-800">
        <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
          <FileText className="w-4 h-4 text-rose-400" />
          Stress Scenario Definitions & Assumptions
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Documented shock parameters, methodology, affected asset classes, and estimated losses
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-slate-950/60 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
              <th className="py-3 px-4">Rank</th>
              <th className="py-3 px-4">Scenario Name / ID</th>
              <th className="py-3 px-4">Type</th>
              <th className="py-3 px-4">Horizon</th>
              <th className="py-3 px-4">Shock Magnitudes</th>
              <th className="py-3 px-4 text-right">Stressed P&L</th>
              <th className="py-3 px-4 text-right">Impact %</th>
              <th className="py-3 px-4">Methodology</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {scenarios.map((sc) => (
              <tr key={sc.scenario_id} className="hover:bg-slate-800/40 transition-colors">
                <td className="py-3 px-4 font-sans text-slate-500">{sc.comparison_rank}</td>
                <td className="py-3 px-4 font-sans">
                  <div className="font-semibold text-slate-200">{sc.scenario_name}</div>
                  <div className="text-[10px] text-slate-500 font-mono">{sc.scenario_id}</div>
                </td>
                <td className="py-3 px-4 font-sans">
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] font-semibold">
                    {sc.scenario_type}
                  </span>
                </td>
                <td className="py-3 px-4 font-sans text-slate-300">{sc.scenario_horizon}</td>
                <td className="py-3 px-4 font-sans text-slate-300 max-w-xs truncate" title={sc.shock_magnitude_summary}>
                  {sc.shock_magnitude_summary}
                </td>
                <td className="py-3 px-4 text-right font-semibold text-rose-400">
                  -${Math.abs(sc.stressed_pnl).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </td>
                <td className="py-3 px-4 text-right font-semibold text-rose-300">
                  {sc.stress_impact_percentage.toFixed(2)}%
                </td>
                <td className="py-3 px-4 font-sans text-[11px] text-slate-400">
                  {sc.methodology}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
