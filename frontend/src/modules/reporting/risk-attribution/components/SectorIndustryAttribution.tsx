import React, { useState } from 'react';
import {
  PieChart,
  Layers,
  ArrowRight,
  TrendingDown,
  Building,
} from 'lucide-react';
import { GroupContribution } from '../../../../types/riskAttribution';

interface SectorIndustryAttributionProps {
  sectors: GroupContribution[];
  industries: GroupContribution[];
}

export const SectorIndustryAttribution: React.FC<SectorIndustryAttributionProps> = ({
  sectors,
  industries,
}) => {
  const [activeTab, setActiveTab] = useState<'SECTOR' | 'INDUSTRY'>('SECTOR');
  const items = activeTab === 'SECTOR' ? sectors : industries;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
      {/* Header & Tabs */}
      <div className="p-5 border-b border-slate-800 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <PieChart className="w-4 h-4 text-cyan-400" />
            Group Risk Contribution ({activeTab === 'SECTOR' ? 'Sectors' : 'Industries'})
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            M04.02 Point-in-Time Point Aggregate Risk Attribution
          </p>
        </div>

        <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
          <button
            onClick={() => setActiveTab('SECTOR')}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              activeTab === 'SECTOR'
                ? 'bg-cyan-600/20 text-cyan-300 border border-cyan-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Sectors ({sectors.length})
          </button>
          <button
            onClick={() => setActiveTab('INDUSTRY')}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              activeTab === 'INDUSTRY'
                ? 'bg-cyan-600/20 text-cyan-300 border border-cyan-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Industries ({industries.length})
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-slate-950/60 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
              <th className="py-3 px-4">Rank</th>
              <th className="py-3 px-4">Group Name</th>
              <th className="py-3 px-4 text-center">Holdings Count</th>
              <th className="py-3 px-4 text-right">Aggregated Weight</th>
              <th className="py-3 px-4 text-right">Component RC</th>
              <th className="py-3 px-4 text-right">Contribution %</th>
              <th className="py-3 px-4 text-center">Classification</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {items.map((g) => {
              const isNegative = g.component_risk_contribution < 0;
              return (
                <tr key={g.group_id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="py-3 px-4 font-sans text-slate-500">{g.group_rank}</td>
                  <td className="py-3 px-4 font-sans font-semibold text-slate-200 flex items-center gap-2">
                    <Building className="w-3.5 h-3.5 text-cyan-400" />
                    <span>{g.group_name}</span>
                  </td>
                  <td className="py-3 px-4 text-center font-sans text-slate-300">
                    <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 text-[11px]">
                      {g.security_count}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right text-slate-300">
                    {(g.total_weight * 100).toFixed(2)}%
                  </td>
                  <td className="py-3 px-4 text-right font-semibold">
                    <span
                      className={`flex items-center justify-end gap-1 ${
                        isNegative ? 'text-emerald-400' : 'text-slate-100'
                      }`}
                    >
                      {isNegative && <TrendingDown className="w-3 h-3" />}
                      {(g.component_risk_contribution * 100).toFixed(3)}%
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right font-semibold text-cyan-300">
                    {g.contribution_percentage.toFixed(2)}%
                  </td>
                  <td className="py-3 px-4 text-center font-sans text-[11px] text-slate-400">
                    {g.classification_version}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
