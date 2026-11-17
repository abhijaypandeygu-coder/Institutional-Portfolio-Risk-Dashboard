import React from 'react';
import { PortfolioLiquidityDashboardResponse, HoldingLiquiditySummary } from '../../../types/dashboard';

interface PortfolioLiquidityTableProps {
  portfolioData: PortfolioLiquidityDashboardResponse | null;
  selectedInstrumentId: string | null;
  onSelectInstrument: (instrumentId: string) => void;
}

export const PortfolioLiquidityTable: React.FC<PortfolioLiquidityTableProps> = ({
  portfolioData,
  selectedInstrumentId,
  onSelectInstrument,
}) => {
  if (!portfolioData) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 text-slate-400 text-sm">
        No portfolio liquidity data loaded.
      </div>
    );
  }

  const getBucketBadge = (bucket: string) => {
    switch (bucket) {
      case 'TIER_1_HIGH':
        return <span className="px-1.5 py-0.5 text-[10px] rounded bg-emerald-950 text-emerald-400 border border-emerald-800">TIER 1</span>;
      case 'TIER_2_MODERATE':
        return <span className="px-1.5 py-0.5 text-[10px] rounded bg-blue-950 text-blue-400 border border-blue-800">TIER 2</span>;
      case 'TIER_3_LOW':
        return <span className="px-1.5 py-0.5 text-[10px] rounded bg-amber-950 text-amber-400 border border-amber-800">TIER 3</span>;
      case 'TIER_4_ILLIQUID':
        return <span className="px-1.5 py-0.5 text-[10px] rounded bg-rose-950 text-rose-400 border border-rose-800">TIER 4</span>;
      default:
        return <span className="px-1.5 py-0.5 text-[10px] rounded bg-slate-800 text-slate-300">{bucket}</span>;
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg flex flex-col gap-4">
      {/* KPI Overview Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-slate-950 p-3 rounded border border-slate-800">
          <span className="text-xs text-slate-400">Weighted Liquidity Score</span>
          <div className="text-2xl font-bold text-cyan-400 font-mono">
            {portfolioData.weighted_composite_score.toFixed(1)} <span className="text-xs font-normal text-slate-500">/ 100</span>
          </div>
        </div>

        <div className="bg-slate-950 p-3 rounded border border-slate-800">
          <span className="text-xs text-slate-400">Weighted Spread</span>
          <div className="text-2xl font-bold text-emerald-400 font-mono">
            {portfolioData.weighted_spread_bps.toFixed(2)} <span className="text-xs font-normal text-slate-500">bps</span>
          </div>
        </div>

        <div className="bg-slate-950 p-3 rounded border border-slate-800">
          <span className="text-xs text-slate-400">Full Liquidation Cost</span>
          <div className="text-2xl font-bold text-rose-400 font-mono">
            ${(portfolioData.total_full_liquidation_cost_usd / 1000).toFixed(1)}k
          </div>
          <span className="text-[11px] text-slate-500 font-mono">
            {portfolioData.portfolio_liquidation_cost_bps.toFixed(1)} bps of NAV
          </span>
        </div>

        <div className="bg-slate-950 p-3 rounded border border-slate-800">
          <span className="text-xs text-slate-400">Max Days to Liquidate</span>
          <div className="text-2xl font-bold text-amber-400 font-mono">
            {portfolioData.max_days_to_liquidate.toFixed(1)} <span className="text-xs font-normal text-slate-500">days</span>
          </div>
          <span className="text-[11px] text-slate-500 font-mono">
            Low Liq Capital: {portfolioData.low_liquidity_capital_pct.toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Holdings Table */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold text-slate-300">Portfolio Holdings Liquidity Breakdown</span>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 uppercase text-[11px]">
                <th className="py-2 px-3">Symbol</th>
                <th className="py-2 px-3">Position</th>
                <th className="py-2 px-3">Weight</th>
                <th className="py-2 px-3">Spread (bps)</th>
                <th className="py-2 px-3">Score</th>
                <th className="py-2 px-3">Tier</th>
                <th className="py-2 px-3">Imbalance</th>
                <th className="py-2 px-3">100% Liq Cost</th>
                <th className="py-2 px-3">Days</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {portfolioData.holdings.map((h: HoldingLiquiditySummary) => {
                const isSelected = h.instrument_id === selectedInstrumentId;
                const shares = Number(h.position_shares);
                const weight = Number(h.weight_pct);
                const spread = h.spread_bps !== null && h.spread_bps !== undefined ? Number(h.spread_bps) : null;
                const compScore = h.composite_score !== null && h.composite_score !== undefined ? Number(h.composite_score) : null;
                const depthImb = h.depth_imbalance !== null && h.depth_imbalance !== undefined ? Number(h.depth_imbalance) : null;
                const liqCost = h.full_liquidation_cost_bps !== null && h.full_liquidation_cost_bps !== undefined ? Number(h.full_liquidation_cost_bps) : null;
                const liqDays = h.full_liquidation_days !== null && h.full_liquidation_days !== undefined ? Number(h.full_liquidation_days) : null;

                return (
                  <tr
                    key={h.instrument_id}
                    onClick={() => onSelectInstrument(h.instrument_id)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-blue-900/30 border-l-2 border-blue-500 font-semibold'
                        : 'hover:bg-slate-800/40'
                    }`}
                  >
                    <td className="py-2.5 px-3 text-slate-100 font-bold">{h.symbol}</td>
                    <td className="py-2.5 px-3 text-slate-300">
                      <span className={h.position_direction === 'LONG' ? 'text-emerald-400' : 'text-rose-400'}>
                        {h.position_direction}
                      </span>{' '}
                      ({shares.toLocaleString()})
                    </td>
                    <td className="py-2.5 px-3 text-slate-300">{weight.toFixed(2)}%</td>
                    <td className="py-2.5 px-3 text-cyan-400">
                      {spread !== null ? `${spread.toFixed(2)}` : '—'}
                    </td>
                    <td className="py-2.5 px-3 text-slate-200">
                      {compScore !== null ? compScore.toFixed(1) : '—'}
                    </td>
                    <td className="py-2.5 px-3">{getBucketBadge(h.liquidity_bucket)}</td>
                    <td className="py-2.5 px-3">
                      {depthImb !== null ? (
                        <span className={depthImb > 0 ? 'text-emerald-400' : 'text-rose-400'}>
                          {(depthImb * 100).toFixed(1)}%
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-rose-400 font-semibold">
                      {liqCost !== null ? `${liqCost.toFixed(1)} bps` : '—'}
                    </td>
                    <td className="py-2.5 px-3 text-slate-300">
                      {liqDays !== null ? `${liqDays.toFixed(1)}d` : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
