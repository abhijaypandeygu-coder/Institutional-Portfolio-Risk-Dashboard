import React from 'react';
import { OrderBookDepthLadder } from '../../../types/dashboard';

interface OrderBookDepthPanelProps {
  ladder: OrderBookDepthLadder | null;
  levelsCount: number;
  onLevelsCountChange: (count: number) => void;
}

export const OrderBookDepthPanel: React.FC<OrderBookDepthPanelProps> = ({
  ladder,
  levelsCount,
  onLevelsCountChange,
}) => {
  if (!ladder) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 text-slate-400 text-sm">
        No depth ladder available.
      </div>
    );
  }

  const totalBidNotional = Number(ladder.total_bid_notional) || 0;
  const totalAskNotional = Number(ladder.total_ask_notional) || 0;
  const totalBidQty = Number(ladder.total_bid_quantity) || 0;
  const totalAskQty = Number(ladder.total_ask_quantity) || 0;
  const depthImb = ladder.depth_imbalance !== null && ladder.depth_imbalance !== undefined
    ? Number(ladder.depth_imbalance)
    : null;

  const maxNotional = Math.max(
    totalBidNotional || 1,
    totalAskNotional || 1
  );

  const getImbalanceBadge = () => {
    switch (ladder.imbalance_status) {
      case 'BID_HEAVY':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-emerald-950 text-emerald-400 border border-emerald-800">BID HEAVY (Buy Pressure)</span>;
      case 'ASK_HEAVY':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-rose-950 text-rose-400 border border-rose-800">ASK HEAVY (Sell Pressure)</span>;
      case 'BALANCED':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-blue-950 text-blue-400 border border-blue-800">BALANCED</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-slate-800 text-slate-300">NEUTRAL</span>;
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-100 text-base">Order-Book Depth Ladder</span>
          {getImbalanceBadge()}
          {ladder.is_stale && (
            <span className="px-1.5 py-0.5 text-[10px] rounded bg-amber-950 text-amber-400 border border-amber-800">
              STALE DEPTH
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400">Levels:</span>
          <select
            value={levelsCount}
            onChange={(e) => onLevelsCountChange(Number(e.target.value))}
            className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded px-2.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value={3}>3 Levels</option>
            <option value={5}>5 Levels</option>
            <option value={10}>10 Levels</option>
          </select>
        </div>
      </div>

      {/* Depth Ladder Grid (Bids on Left, Asks on Right) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Bids Side */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between text-xs font-semibold text-emerald-400 border-b border-slate-800 pb-1">
            <span>BID QUANTITY</span>
            <span>CUM NOTIONAL</span>
            <span>BID PRICE</span>
          </div>

          {ladder.bids.length === 0 ? (
            <div className="text-xs text-slate-500 py-3 text-center">No bids available</div>
          ) : (
            ladder.bids.map((b, idx) => {
              const cumNotional = ladder.cumulative_bid_notional[idx] || b.notional;
              const fillPct = Math.min(100, (cumNotional / maxNotional) * 100);

              return (
                <div
                  key={`bid-${b.level_index}`}
                  className="relative flex items-center justify-between text-xs py-1 px-2 rounded bg-slate-950/60 font-mono overflow-hidden"
                >
                  <div
                    className="absolute right-0 top-0 bottom-0 bg-emerald-500/15 pointer-events-none transition-all duration-300"
                    style={{ width: `${fillPct}%` }}
                  />
                  <span className="text-slate-300 z-10">{b.quantity.toLocaleString()}</span>
                  <span className="text-slate-400 text-[11px] z-10">${(cumNotional / 1000).toFixed(1)}k</span>
                  <span className="text-emerald-400 font-bold z-10">${b.price.toFixed(2)}</span>
                </div>
              );
            })
          )}
        </div>

        {/* Asks Side */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between text-xs font-semibold text-rose-400 border-b border-slate-800 pb-1">
            <span>ASK PRICE</span>
            <span>CUM NOTIONAL</span>
            <span>ASK QUANTITY</span>
          </div>

          {ladder.asks.length === 0 ? (
            <div className="text-xs text-slate-500 py-3 text-center">No asks available</div>
          ) : (
            ladder.asks.map((a, idx) => {
              const cumNotional = ladder.cumulative_ask_notional[idx] || a.notional;
              const fillPct = Math.min(100, (cumNotional / maxNotional) * 100);

              return (
                <div
                  key={`ask-${a.level_index}`}
                  className="relative flex items-center justify-between text-xs py-1 px-2 rounded bg-slate-950/60 font-mono overflow-hidden"
                >
                  <div
                    className="absolute left-0 top-0 bottom-0 bg-rose-500/15 pointer-events-none transition-all duration-300"
                    style={{ width: `${fillPct}%` }}
                  />
                  <span className="text-rose-400 font-bold z-10">${a.price.toFixed(2)}</span>
                  <span className="text-slate-400 text-[11px] z-10">${(cumNotional / 1000).toFixed(1)}k</span>
                  <span className="text-slate-300 z-10">{a.quantity.toLocaleString()}</span>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Depth Imbalance Bar */}
      <div className="bg-slate-950 p-3 rounded border border-slate-800/80 flex flex-col gap-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-400">
            Total Bids: <strong className="text-emerald-400 font-mono">${(totalBidNotional / 1000).toFixed(1)}k</strong>
          </span>
          <span className="text-slate-300 font-medium">
            Imbalance:{' '}
            <strong className="font-mono text-cyan-400">
              {depthImb !== null ? `${(depthImb * 100).toFixed(1)}%` : '0.0%'}
            </strong>
          </span>
          <span className="text-slate-400">
            Total Asks: <strong className="text-rose-400 font-mono">${(totalAskNotional / 1000).toFixed(1)}k</strong>
          </span>
        </div>

        {/* Visual Imbalance Bar [-1, +1] */}
        <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden flex">
          <div
            className="bg-emerald-500 h-full transition-all duration-300"
            style={{
              width: `${
                totalBidQty + totalAskQty > 0
                  ? (totalBidQty / (totalBidQty + totalAskQty)) * 100
                  : 50
              }%`,
            }}
          />
          <div
            className="bg-rose-500 h-full transition-all duration-300"
            style={{
              width: `${
                totalBidQty + totalAskQty > 0
                  ? (totalAskQty / (totalBidQty + totalAskQty)) * 100
                  : 50
              }%`,
            }}
          />
        </div>
      </div>
    </div>
  );
};
