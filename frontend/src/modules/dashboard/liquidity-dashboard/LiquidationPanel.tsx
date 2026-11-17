import React from 'react';
import { InstrumentLiquidationProfile } from '../../../types/dashboard';

interface LiquidationPanelProps {
  liquidationProfile: InstrumentLiquidationProfile | null;
  participationRate: number;
  onParticipationRateChange: (rate: number) => void;
}

export const LiquidationPanel: React.FC<LiquidationPanelProps> = ({
  liquidationProfile,
  participationRate,
  onParticipationRateChange,
}) => {
  if (!liquidationProfile) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 text-slate-400 text-sm">
        No liquidation scenario available.
      </div>
    );
  }

  const getDirectionBadge = () => {
    if (liquidationProfile.liquidation_direction === 'SELL') {
      return (
        <span className="px-2 py-0.5 text-xs font-semibold rounded bg-rose-950 text-rose-400 border border-rose-800">
          LONG SALE (Bid Depth Consumption)
        </span>
      );
    } else if (liquidationProfile.liquidation_direction === 'BUY') {
      return (
        <span className="px-2 py-0.5 text-xs font-semibold rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
          SHORT COVERING (Ask Depth Consumption)
        </span>
      );
    }
    return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-slate-800 text-slate-300">FLAT POSITION</span>;
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg flex flex-col gap-4">
      {/* Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-100 text-base">Liquidation Scenarios & Cost Decomposition</span>
          {getDirectionBadge()}
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400">Participation Rate:</span>
          <select
            value={participationRate}
            onChange={(e) => onParticipationRateChange(Number(e.target.value))}
            className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded px-2.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value={0.05}>5% of ADV (Conservative)</option>
            <option value={0.10}>10% of ADV (Moderate)</option>
            <option value={0.20}>20% of ADV (Aggressive)</option>
          </select>
        </div>
      </div>

      {/* Position Summary Subheader */}
      <div className="bg-slate-950/70 border border-slate-800/80 p-3 rounded flex flex-wrap items-center justify-between gap-4 text-xs">
        <div>
          <span className="text-slate-400">Current Position: </span>
          <strong className="text-slate-200 font-mono">
            {Number(liquidationProfile.current_position_shares).toLocaleString()} shares
          </strong>
        </div>
        <div>
          <span className="text-slate-400">Notional Exposure: </span>
          <strong className="text-slate-200 font-mono">
            ${(Number(liquidationProfile.current_position_notional) / 1000).toFixed(1)}k
          </strong>
        </div>
        <div className="text-slate-500 text-[11px]">
          *Zero double-counting: Spread + Market Impact + Slippage
        </div>
      </div>

      {/* Scenarios Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 uppercase text-[11px]">
              <th className="py-2 px-3">Target %</th>
              <th className="py-2 px-3">Shares</th>
              <th className="py-2 px-3">Notional ($)</th>
              <th className="py-2 px-3">Spread (bps)</th>
              <th className="py-2 px-3">Impact (bps)</th>
              <th className="py-2 px-3">Slippage (bps)</th>
              <th className="py-2 px-3 font-semibold text-cyan-400">Total (bps)</th>
              <th className="py-2 px-3 font-semibold text-rose-400">Est. Cost ($)</th>
              <th className="py-2 px-3">Est. Horizon</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {liquidationProfile.scenarios.map((scen) => {
              const targetPct = Number(scen.target_percentage);
              const shares = Number(scen.shares_to_liquidate);
              const notional = Number(scen.notional_value);
              const spreadBps = Number(scen.spread_cost_bps);
              const impactBps = Number(scen.market_impact_cost_bps);
              const slipBps = Number(scen.slippage_cost_bps);
              const totalBps = Number(scen.total_cost_bps);
              const totalUsd = Number(scen.total_cost_usd);
              const estMins = Number(scen.estimated_duration_minutes);
              const estDays = Number(scen.estimated_trading_days);

              return (
                <tr
                  key={scen.target_percentage}
                  className={`hover:bg-slate-800/40 transition-colors ${
                    targetPct === 1.0 ? 'bg-slate-950/80 font-bold' : ''
                  }`}
                >
                  <td className="py-2.5 px-3 text-slate-200 font-semibold">
                    {(targetPct * 100).toFixed(0)}%
                  </td>
                  <td className="py-2.5 px-3 text-slate-300">
                    {shares.toLocaleString()}
                  </td>
                  <td className="py-2.5 px-3 text-slate-300">
                    ${(notional / 1000).toFixed(1)}k
                  </td>
                  <td className="py-2.5 px-3 text-slate-400">
                    {spreadBps.toFixed(2)}
                  </td>
                  <td className="py-2.5 px-3 text-amber-400">
                    {impactBps.toFixed(2)}
                  </td>
                  <td className="py-2.5 px-3 text-purple-400">
                    {slipBps.toFixed(2)}
                  </td>
                  <td className="py-2.5 px-3 text-cyan-400 font-bold">
                    {totalBps.toFixed(2)} bps
                  </td>
                  <td className="py-2.5 px-3 text-rose-400 font-bold">
                    ${totalUsd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </td>
                  <td className="py-2.5 px-3 text-slate-300">
                    {estDays < 1
                      ? `${estMins.toFixed(0)} mins`
                      : `${estDays.toFixed(1)} days`}
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
