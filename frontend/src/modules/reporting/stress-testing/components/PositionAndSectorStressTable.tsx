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
    <div className="bg-surface border border-line rounded-xl overflow-hidden">
      {/* Header & Tabs */}
      <div className="p-5 border-b border-line flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-ink flex items-center gap-2">
            <Layers className="w-4 h-4 text-brand" />
            Stressed Portfolio Breakdown ({activeTab === 'POSITIONS' ? 'Positions' : 'Sectors'})
          </h2>
          <p className="text-xs text-muted mt-0.5">
            Granular valuation changes and signed P&L attribution
          </p>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          {activeTab === 'POSITIONS' && (
            <div className="relative flex-1 sm:w-60">
              <Search className="w-4 h-4 text-muted absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search symbol, sector..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-canvas border border-line rounded-lg pl-9 pr-3 py-1.5 text-xs text-secondary placeholder-muted focus:outline-none focus:border-rose-500"
              />
            </div>
          )}

          <div className="flex items-center gap-1 bg-canvas p-1 rounded-lg border border-line">
            <button
              onClick={() => setActiveTab('POSITIONS')}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                activeTab === 'POSITIONS'
                  ? 'bg-rose-600/20 text-negative border border-rose-500/30'
                  : 'text-muted hover:text-secondary'
              }`}
            >
              Positions ({positions.length})
            </button>
            <button
              onClick={() => setActiveTab('SECTORS')}
              className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                activeTab === 'SECTORS'
                  ? 'bg-rose-600/20 text-negative border border-rose-500/30'
                  : 'text-muted hover:text-secondary'
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
              <tr className="bg-canvas/60 border-b border-line text-muted font-semibold uppercase ">
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
            <tbody className="divide-y divide-slate-800/60 font-sans">
              {filteredPositions.map((p) => {
                const isGain = p.stressed_pnl > 0;
                return (
                  <tr key={`${p.scenario_id}-${p.instrument_id}`} className="hover:bg-subtle/40 transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-secondary">{p.symbol}</div>
                      <div className="text-[10px] text-muted font-sans">{p.instrument_name}</div>
                    </td>
                    <td className="py-3 px-4 font-sans text-secondary">{p.sector}</td>
                    <td className="py-3 px-4 font-sans">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold ${
                          p.position_side === 'LONG'
                            ? 'bg-brand/10 text-positive border border-emerald-500/20'
                            : 'bg-amber-500/10 text-warning border border-amber-500/20'
                        }`}
                      >
                        {p.position_side}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right text-secondary">${p.baseline_price.toFixed(2)}</td>
                    <td className="py-3 px-4 text-right text-secondary">${p.stressed_price.toFixed(2)}</td>
                    <td className="py-3 px-4 text-right text-secondary">
                      ${p.baseline_market_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4 text-right text-secondary">
                      ${p.stressed_market_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4 text-right font-semibold">
                      <span className={isGain ? 'text-positive' : 'text-negative'}>
                        {isGain ? '+' : '-'}${Math.abs(p.stressed_pnl).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right font-semibold">
                      <span className={isGain ? 'text-positive' : 'text-negative'}>
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
              <tr className="bg-canvas/60 border-b border-line text-muted font-semibold uppercase ">
                <th className="py-3 px-4">Sector</th>
                <th className="py-3 px-4 text-center">Holdings Count</th>
                <th className="py-3 px-4 text-right">Baseline Market Value</th>
                <th className="py-3 px-4 text-right">Stressed Market Value</th>
                <th className="py-3 px-4 text-right">Stressed P&L</th>
                <th className="py-3 px-4 text-right">Impact %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-sans">
              {sectors.map((s) => {
                const isGain = s.stressed_pnl > 0;
                return (
                  <tr key={s.sector_name} className="hover:bg-subtle/40 transition-colors">
                    <td className="py-3 px-4 font-sans font-semibold text-secondary flex items-center gap-2">
                      <Building className="w-3.5 h-3.5 text-brand" />
                      <span>{s.sector_name}</span>
                    </td>
                    <td className="py-3 px-4 text-center font-sans">
                      <span className="px-2 py-0.5 rounded-full bg-subtle text-secondary text-[11px]">
                        {s.position_count}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right text-secondary">
                      ${s.baseline_market_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4 text-right text-secondary">
                      ${s.stressed_market_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4 text-right font-semibold">
                      <span className={isGain ? 'text-positive' : 'text-negative'}>
                        {isGain ? '+' : '-'}${Math.abs(s.stressed_pnl).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right font-semibold">
                      <span className={isGain ? 'text-positive' : 'text-negative'}>
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
