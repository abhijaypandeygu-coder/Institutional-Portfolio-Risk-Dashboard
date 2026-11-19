import React, { useState } from 'react';
import {
  PositionLiquidity,
  LiquidationEstimate,
} from '../../../../types/liquidityReport';

interface Props {
  positions: PositionLiquidity[];
  liquidations: LiquidationEstimate[];
  currency: string;
}

export const PositionLiquidityAndCostTable: React.FC<Props> = ({ positions, liquidations, currency }) => {
  const [activeTab, setActiveTab] = useState<'liquidity' | 'liquidation'>('liquidation');
  const [searchTerm, setSearchTerm] = useState('');

  // Map instrument ID to liquidation estimate
  const liqMap = new Map(liquidations.map((l) => [l.instrument_id, l]));

  const filteredPositions = positions.filter(
    (p) =>
      p.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (p.sector && p.sector.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div className="bg-surface border border-line rounded-lg p-5 mb-6 shadow-md">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold text-ink uppercase ">
            Instrument-Level Liquidity & Liquidation Breakdown
          </h2>
          <div className="flex bg-canvas p-0.5 rounded border border-line text-xs">
            <button
              onClick={() => setActiveTab('liquidation')}
              className={`px-3 py-1 rounded transition-colors ${
                activeTab === 'liquidation'
                  ? 'bg-subtle text-positive font-semibold'
                  : 'text-muted hover:text-secondary'
              }`}
            >
              Liquidation Time & Cost
            </button>
            <button
              onClick={() => setActiveTab('liquidity')}
              className={`px-3 py-1 rounded transition-colors ${
                activeTab === 'liquidity'
                  ? 'bg-subtle text-positive font-semibold'
                  : 'text-muted hover:text-secondary'
              }`}
            >
              Microstructure Spread & Depth
            </button>
          </div>
        </div>

        <div>
          <input
            type="text"
            placeholder="Search symbol or sector..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="bg-canvas border border-line-strong rounded px-2.5 py-1 text-xs text-secondary placeholder-muted focus:outline-none focus:border-emerald-500 w-52"
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-line text-muted font-semibold uppercase  bg-canvas/50">
              <th className="py-2.5 px-3">Symbol / Exchange</th>
              <th className="py-2.5 px-3">Sector</th>
              <th className="py-2.5 px-3 text-right">Signed Qty</th>
              <th className="py-2.5 px-3 text-right">Market Value</th>
              {activeTab === 'liquidation' ? (
                <>
                  <th className="py-2.5 px-3 text-center">Side</th>
                  <th className="py-2.5 px-3 text-right">Horizon (Days)</th>
                  <th className="py-2.5 px-3 text-right">Spread Cost</th>
                  <th className="py-2.5 px-3 text-right">Impact Cost</th>
                  <th className="py-2.5 px-3 text-right">Total Cost</th>
                  <th className="py-2.5 px-3 text-right">Cost (bps)</th>
                </>
              ) : (
                <>
                  <th className="py-2.5 px-3 text-right">Spread (bps)</th>
                  <th className="py-2.5 px-3 text-right">Bid Depth</th>
                  <th className="py-2.5 px-3 text-right">Ask Depth</th>
                  <th className="py-2.5 px-3 text-right">ADV (Shares)</th>
                  <th className="py-2.5 px-3 text-center">Score</th>
                  <th className="py-2.5 px-3 text-center">Tier</th>
                </>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 text-secondary">
            {filteredPositions.map((p) => {
              const liq = liqMap.get(p.instrument_id);
              return (
                <tr key={p.instrument_id} className="hover:bg-subtle/40 transition-colors">
                  <td className="py-2 px-3 font-medium text-secondary">
                    {p.symbol}
                    <span className="text-[10px] text-muted ml-1.5 font-sans">({p.exchange})</span>
                  </td>
                  <td className="py-2 px-3 text-muted">{p.sector || 'Unclassified'}</td>
                  <td className="py-2 px-3 text-right font-sans">
                    {p.position_quantity.toLocaleString()}
                  </td>
                  <td className="py-2 px-3 text-right font-sans text-secondary">
                    {currency} {p.position_market_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </td>

                  {activeTab === 'liquidation' ? (
                    <>
                      <td className="py-2 px-3 text-center">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            liq?.liquidation_direction === 'SELL'
                              ? 'bg-negative-soft text-negative border border-negative/20'
                              : 'bg-positive-soft text-positive border border-positive/20'
                          }`}
                        >
                          {liq?.liquidation_direction || (p.position_quantity > 0 ? 'SELL' : 'BUY')}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-right font-sans text-brand">
                        {liq?.estimated_duration_days?.toFixed(2) || '1.00'}
                      </td>
                      <td className="py-2 px-3 text-right font-sans text-secondary">
                        {liq ? `${currency} ${liq.estimated_spread_cost.toFixed(2)}` : '-'}
                      </td>
                      <td className="py-2 px-3 text-right font-sans text-secondary">
                        {liq ? `${currency} ${liq.estimated_market_impact.toFixed(2)}` : '-'}
                      </td>
                      <td className="py-2 px-3 text-right font-sans font-bold text-warning">
                        {liq ? `${currency} ${liq.estimated_total_cost.toFixed(2)}` : '-'}
                      </td>
                      <td className="py-2 px-3 text-right font-sans text-warning">
                        {liq ? `${liq.estimated_cost_bps.toFixed(1)} bps` : '-'}
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="py-2 px-3 text-right font-sans text-secondary">
                        {p.spread_bps?.toFixed(1) || '0.0'}
                      </td>
                      <td className="py-2 px-3 text-right font-sans text-muted">
                        {p.bid_depth ? (p.bid_depth / 1e5).toFixed(1) + 'L' : '-'}
                      </td>
                      <td className="py-2 px-3 text-right font-sans text-muted">
                        {p.ask_depth ? (p.ask_depth / 1e5).toFixed(1) + 'L' : '-'}
                      </td>
                      <td className="py-2 px-3 text-right font-sans text-muted">
                        {p.average_daily_volume ? p.average_daily_volume.toLocaleString() : '-'}
                      </td>
                      <td className="py-2 px-3 text-center font-sans font-semibold text-positive">
                        {p.liquidity_score?.toFixed(1) || '-'}
                      </td>
                      <td className="py-2 px-3 text-center">
                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-subtle text-secondary border border-line-strong">
                          {p.liquidity_classification}
                        </span>
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
