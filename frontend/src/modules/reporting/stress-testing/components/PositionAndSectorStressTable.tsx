import React, { useState } from 'react';
import {
  Table,
  Search,
  ArrowUpDown,
  Building,
  TrendingDown,
  TrendingUp,
  Layers,
} from 'lucide-react';
import {
  PositionStressResult,
  SectorStressBreakdown,
} from '../../../../types/stressReport';

interface PositionAndSectorStressTableProps {
  positions: PositionStressResult[];
  sectors: SectorStressBreakdown[];
}

export const PositionAndSectorStressTable: React.FC<PositionAndSectorStressTableProps> = ({
  positions,
  sectors,
}) => {
  const [activeTab, setActiveTab] = useState<'POSITIONS' | 'SECTORS'>('POSITIONS');
  const [searchTerm, setSearchTerm] = useState('');

  const filteredPositions = positions.filter((p) =>
    p.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.sector.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.instrument_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
      {/* Header & Tabs */}
      <div className="p-5 border-b border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <Layers className="w-4 h-4 text-indigo-400" />
            Stressed Portfolio Breakdown ({activeTab === 'POSITIONS' ? 'Positions' : 'Sectors'})
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Granular valuation changes and signed P&L attribution
          </p>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          {activeTab === 'POSITIONS' && (
            <div className="relative flex-1 sm:w-60">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search symbol, sector..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-rose-500"
              />
            </div>
          )}

          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
            <button
              onClick={() => setActiveTab('POSITIONS')}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                activeTab === 'POSITIONS'
                  ? 'bg-rose-600/20 text-rose-300 border border-rose-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Positions ({positions.length})
            </button>
            <button
              onClick={() => setActiveTab('SECTORS')}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                activeTab === 'SECTORS'
                  ? 'bg-rose-600/20 text-rose-300 border border-rose-500/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Sectors ({sectors.length})
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="overflow-x-auto">
        {activeTab === 'POSITIONS' ? (
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-950/60 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
                <th className="py-3 px-4">Symbol / ID</th>
                <th className="py-3 px-4">Sector</th>
                <th className="py-3 px-4">Side</th>
                <th className="py-3 px-4 text-right">Baseline Price</th>
                <th className="py-3 px-4 text-right">Stressed Price</th>
                <th className="py-3 px-4 text-right">Baseline MV</th>
                <th className="py-3 px-4 text-right">Stressed MV</th>
                <th className="py-3 px-4 text-right">Stressed P&L</th>
                <th className="py-3 px-4 text-right">Impact %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {filteredPositions.map((p) => {
                const isGain = p.stressed_pnl > 0;
                return (
                  <tr key={`${p.scenario_id}-${p.instrument_id}`} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-200">{p.symbol}</div>
                      <div className="text-[10px] text-slate-500 font-sans">{p.instrument_name}</div>
                    </td>
                    <td className="py-3 px-4 font-sans text-slate-300">{p.sector}</td>
                    <td className="py-3 px-4 font-sans">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold ${
                          p.position_side === 'LONG'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                        }`}
                      >
                        {p.position_side}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right text-slate-300">${p.baseline_price.toFixed(2)}</td>
                    <td className="py-3 px-4 text-right text-slate-300">${p.stressed_price.toFixed(2)}</td>
                    <td className="py-3 px-4 text-right text-slate-300">
                      ${p.baseline_market_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4 text-right text-slate-300">
                      ${p.stressed_market_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4 text-right font-semibold">
                      <span className={isGain ? 'text-emerald-400' : 'text-rose-400'}>
                        {isGain ? '+' : '-'}${Math.abs(p.stressed_pnl).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right font-semibold">
                      <span className={isGain ? 'text-emerald-400' : 'text-rose-400'}>
                        {p.impact_percentage.toFixed(2)}%
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-950/60 border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
                <th className="py-3 px-4">Sector</th>
                <th className="py-3 px-4 text-center">Holdings Count</th>
                <th className="py-3 px-4 text-right">Baseline Market Value</th>
                <th className="py-3 px-4 text-right">Stressed Market Value</th>
                <th className="py-3 px-4 text-right">Stressed P&L</th>
                <th className="py-3 px-4 text-right">Impact %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {sectors.map((s) => {
                const isGain = s.stressed_pnl > 0;
                return (
                  <tr key={s.sector_name} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3 px-4 font-sans font-semibold text-slate-200 flex items-center gap-2">
                      <Building className="w-3.5 h-3.5 text-indigo-400" />
                      <span>{s.sector_name}</span>
                    </td>
                    <td className="py-3 px-4 text-center font-sans">
                      <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 text-[11px]">
                        {s.position_count}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right text-slate-300">
                      ${s.baseline_market_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4 text-right text-slate-300">
                      ${s.stressed_market_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4 text-right font-semibold">
                      <span className={isGain ? 'text-emerald-400' : 'text-rose-400'}>
                        {isGain ? '+' : '-'}${Math.abs(s.stressed_pnl).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right font-semibold">
                      <span className={isGain ? 'text-emerald-400' : 'text-rose-400'}>
                        {s.impact_percentage.toFixed(2)}%
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
