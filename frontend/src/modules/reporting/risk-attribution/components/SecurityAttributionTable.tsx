import React, { useState } from 'react';
import {
  Table,
  ArrowUpDown,
  Search,
  CheckCircle,
  AlertCircle,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { SecurityContribution } from '../../../../types/riskAttribution';

interface SecurityAttributionTableProps {
  securities: SecurityContribution[];
}

export const SecurityAttributionTable: React.FC<SecurityAttributionTableProps> = ({
  securities,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [sideFilter, setSideFilter] = useState<'ALL' | 'LONG' | 'SHORT'>('ALL');
  const [sortField, setSortField] = useState<keyof SecurityContribution>(
    'component_risk_contribution'
  );
  const [sortAsc, setSortAsc] = useState(false);

  const filtered = securities.filter((s) => {
    const matchesSearch =
      s.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.sector.toLowerCase().includes(searchTerm.toLowerCase()) ||
      s.instrument_id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesSide = sideFilter === 'ALL' || s.position_side === sideFilter;
    return matchesSearch && matchesSide;
  });

  const sorted = [...filtered].sort((a, b) => {
    const valA = a[sortField] ?? 0;
    const valB = b[sortField] ?? 0;
    if (typeof valA === 'string') {
      return sortAsc
        ? String(valA).localeCompare(String(valB))
        : String(valB).localeCompare(String(valA));
    }
    return sortAsc ? Number(valA) - Number(valB) : Number(valB) - Number(valA);
  });

  const handleSort = (field: keyof SecurityContribution) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
      {/* Header & Controls */}
      <div className="p-5 border-b border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <Table className="w-4 h-4 text-indigo-400" />
            Security-Level Risk Contribution
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Marginal (MRC_i) and Component (RC_i = w_i * MRC_i) risk contributions per holding
          </p>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          {/* Search */}
          <div className="relative flex-1 sm:w-60">
            <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search symbol, sector..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          {/* Side Filter */}
          <select
            value={sideFilter}
            onChange={(e) => setSideFilter(e.target.value as any)}
            className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
          >
            <option value="ALL">All Sides</option>
            <option value="LONG">Long Only</option>
            <option value="SHORT">Short Only</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-slate-950/60 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
              <th className="py-3 px-4">Rank</th>
              <th className="py-3 px-4">Symbol / ID</th>
              <th className="py-3 px-4">Sector / Industry</th>
              <th className="py-3 px-4">Side</th>
              <th
                className="py-3 px-4 text-right cursor-pointer hover:text-slate-200"
                onClick={() => handleSort('position_weight')}
              >
                <div className="flex items-center justify-end gap-1">
                  <span>Weight</span>
                  <ArrowUpDown className="w-3 h-3" />
                </div>
              </th>
              <th
                className="py-3 px-4 text-right cursor-pointer hover:text-slate-200"
                onClick={() => handleSort('marginal_risk_contribution')}
              >
                <div className="flex items-center justify-end gap-1">
                  <span>Marginal RC</span>
                  <ArrowUpDown className="w-3 h-3" />
                </div>
              </th>
              <th
                className="py-3 px-4 text-right cursor-pointer hover:text-slate-200"
                onClick={() => handleSort('component_risk_contribution')}
              >
                <div className="flex items-center justify-end gap-1">
                  <span>Component RC</span>
                  <ArrowUpDown className="w-3 h-3" />
                </div>
              </th>
              <th
                className="py-3 px-4 text-right cursor-pointer hover:text-slate-200"
                onClick={() => handleSort('contribution_percentage')}
              >
                <div className="flex items-center justify-end gap-1">
                  <span>Contrib %</span>
                  <ArrowUpDown className="w-3 h-3" />
                </div>
              </th>
              <th className="py-3 px-4 text-center">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {sorted.map((s) => {
              const isNegative = s.component_risk_contribution < 0;
              return (
                <tr key={s.instrument_id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="py-3 px-4 font-sans text-slate-500">{s.contribution_rank}</td>
                  <td className="py-3 px-4">
                    <div className="font-semibold text-slate-200">{s.symbol}</div>
                    <div className="text-[10px] text-slate-500 font-sans">{s.instrument_id}</div>
                  </td>
                  <td className="py-3 px-4 font-sans">
                    <div className="text-slate-300">{s.sector}</div>
                    <div className="text-[10px] text-slate-500">{s.industry}</div>
                  </td>
                  <td className="py-3 px-4 font-sans">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold ${
                        s.position_side === 'LONG'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}
                    >
                      {s.position_side}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right text-slate-300">
                    {(s.position_weight * 100).toFixed(2)}%
                  </td>
                  <td className="py-3 px-4 text-right text-slate-300">
                    {(s.marginal_risk_contribution * 100).toFixed(2)}%
                  </td>
                  <td className="py-3 px-4 text-right font-semibold">
                    <span
                      className={`flex items-center justify-end gap-1 ${
                        isNegative ? 'text-emerald-400' : 'text-slate-100'
                      }`}
                    >
                      {isNegative && <TrendingDown className="w-3 h-3" />}
                      {(s.component_risk_contribution * 100).toFixed(3)}%
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right font-semibold text-indigo-300">
                    {s.contribution_percentage.toFixed(2)}%
                  </td>
                  <td className="py-3 px-4 text-center font-sans">
                    {s.contribution_status === 'ACTIVE' ? (
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-400 inline-block" />
                    ) : (
                      <span className="text-[10px] text-amber-400 bg-amber-400/10 px-1.5 py-0.5 rounded border border-amber-400/20">
                        {s.contribution_status}
                      </span>
                    )}
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
