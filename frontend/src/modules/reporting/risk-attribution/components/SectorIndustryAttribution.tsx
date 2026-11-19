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
    <div className="bg-surface border border-line rounded-xl overflow-hidden">
      {/* Header & Tabs */}
      <div className="p-5 border-b border-line flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-ink flex items-center gap-2">
            <PieChart className="w-4 h-4 text-brand" />
            Group Risk Contribution ({activeTab === 'SECTOR' ? 'Sectors' : 'Industries'})
          </h2>
          <p className="text-xs text-muted mt-0.5">
            M04.02 Point-in-Time Point Aggregate Risk Attribution
          </p>
        </div>

        <div className="flex items-center gap-1 bg-canvas p-1 rounded-lg border border-line">
          <button
            onClick={() => setActiveTab('SECTOR')}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              activeTab === 'SECTOR'
                ? 'bg-brand/20 text-brand border border-cyan-500/30'
                : 'text-muted hover:text-secondary'
            }`}
          >
            Sectors ({sectors.length})
          </button>
          <button
            onClick={() => setActiveTab('INDUSTRY')}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              activeTab === 'INDUSTRY'
                ? 'bg-brand/20 text-brand border border-cyan-500/30'
                : 'text-muted hover:text-secondary'
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
            <tr className="bg-canvas/60 border-b border-line text-muted font-semibold uppercase ">
              <th className="py-3 px-4">Rank</th>
              <th className="py-3 px-4">Group Name</th>
              <th className="py-3 px-4 text-center">Holdings Count</th>
              <th className="py-3 px-4 text-right">Aggregated Weight</th>
              <th className="py-3 px-4 text-right">Component RC</th>
              <th className="py-3 px-4 text-right">Contribution %</th>
              <th className="py-3 px-4 text-center">Classification</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-sans">
            {items.map((g) => {
              const isNegative = g.component_risk_contribution < 0;
              return (
                <tr key={g.group_id} className="hover:bg-subtle/40 transition-colors">
                  <td className="py-3 px-4 font-sans text-muted">{g.group_rank}</td>
                  <td className="py-3 px-4 font-sans font-semibold text-secondary flex items-center gap-2">
                    <Building className="w-3.5 h-3.5 text-brand" />
                    <span>{g.group_name}</span>
                  </td>
                  <td className="py-3 px-4 text-center font-sans text-secondary">
                    <span className="px-2 py-0.5 rounded-full bg-subtle text-secondary text-[11px]">
                      {g.security_count}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right text-secondary">
                    {(g.total_weight * 100).toFixed(2)}%
                  </td>
                  <td className="py-3 px-4 text-right font-semibold">
                    <span
                      className={`flex items-center justify-end gap-1 ${
                        isNegative ? 'text-positive' : 'text-ink'
                      }`}
                    >
                      {isNegative && <TrendingDown className="w-3 h-3" />}
                      {(g.component_risk_contribution * 100).toFixed(3)}%
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right font-semibold text-brand">
                    {g.contribution_percentage.toFixed(2)}%
                  </td>
                  <td className="py-3 px-4 text-center font-sans text-[11px] text-muted">
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
