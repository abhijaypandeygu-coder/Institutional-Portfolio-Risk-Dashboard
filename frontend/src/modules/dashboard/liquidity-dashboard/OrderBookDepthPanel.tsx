import React from 'react';
import { imbalanceLabel, quantityImbalance } from '../../../utils/liquidityAnalytics';
import { OrderBookDepthLadder } from '../../../types/dashboard';

interface OrderBookDepthPanelProps {
  ladder: OrderBookDepthLadder | null;
  levelsCount: number;
  onLevelsCountChange: (count: number) => void;
  isStreaming?: boolean;
}

export const OrderBookDepthPanel: React.FC<OrderBookDepthPanelProps> = ({
  ladder,
  levelsCount,
  onLevelsCountChange,
  isStreaming = false,
}) => {
  if (!ladder) {
    return (
      <div className="bg-surface border border-line rounded-lg p-5 text-muted text-sm">
        No depth ladder available.
      </div>
    );
  }

  const getCurrencySymbol = () => {
    if (ladder.currency === 'INR') return '₹';
    if (ladder.currency && ladder.currency !== 'USD') return ladder.currency + ' ';
    const sym = ladder.symbol || '';
    if (sym.endsWith('.NS') || sym.endsWith('.BO')) return '₹';
    return '$';
  };
  const currSym = getCurrencySymbol();

  const visibleBids = (ladder.bids || []).slice(0, levelsCount);
  const visibleAsks = (ladder.asks || []).slice(0, levelsCount);

  const totalBidNotional = visibleBids.reduce((sum, b) => sum + (Number(b.notional) || 0), 0) || Number(ladder.total_bid_notional) || 0;
  const totalAskNotional = visibleAsks.reduce((sum, a) => sum + (Number(a.notional) || 0), 0) || Number(ladder.total_ask_notional) || 0;
  const totalBidQty = visibleBids.reduce((sum, b) => sum + (Number(b.quantity) || 0), 0) || Number(ladder.total_bid_quantity) || 0;
  const totalAskQty = visibleAsks.reduce((sum, a) => sum + (Number(a.quantity) || 0), 0) || Number(ladder.total_ask_quantity) || 0;

  const visibleImb = (totalBidQty + totalAskQty) > 0
    ? (totalBidQty - totalAskQty) / (totalBidQty + totalAskQty)
    : (ladder.depth_imbalance !== null && ladder.depth_imbalance !== undefined ? Number(ladder.depth_imbalance) : null);

  // Use max level quantity for relative bar width, exactly matching broker market depth meters
  const maxLevelQty = Math.max(
    ...visibleBids.map((b) => Number(b.quantity) || 0),
    ...visibleAsks.map((a) => Number(a.quantity) || 0),
    1
  );

  const getImbalanceBadge = () => <span className="rounded border border-line bg-subtle px-2 py-1 text-xs font-medium">{imbalanceLabel(quantityImbalance(visibleBids, visibleAsks))}</span>;

  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-lg flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-ink text-base">Order-Book Depth Ladder</span>
          {getImbalanceBadge()}
          {ladder.is_stale && (
            <span className="px-1.5 py-0.5 text-[10px] rounded bg-warning-soft text-warning border border-warning/20">
              STALE DEPTH
            </span>
          )}
        </div>

        {/* Data Freshness & Quality Badges */}
        <div className="flex flex-wrap items-center gap-2 text-[11px] font-sans">
          <span className={`px-2 py-0.5 rounded bg-canvas border flex items-center gap-1.5 ${
            isStreaming ? 'text-positive border-positive/30' : 'text-secondary border-line'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${isStreaming ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`}></span>
            {isStreaming ? 'FEED: STREAMING' : 'FEED: SNAPSHOT'}
          </span>
          <span className="px-2 py-0.5 rounded bg-canvas text-brand border border-line">
            VENUE: {ladder.venue || 'PRIMARY'}
          </span>
          <span className="px-2 py-0.5 rounded bg-canvas text-positive border border-line">
            QUALITY: {ladder.quality_status || 'UNVERIFIED'}
          </span>
          <span className={`px-2 py-0.5 rounded border ${
            ladder.is_locked_crossed 
              ? 'bg-negative-soft text-negative border-negative/20' 
              : 'bg-canvas text-muted border-line'
          }`}>
            BOOK: {ladder.is_locked_crossed ? 'LOCKED/CROSSED' : 'UNLOCKED'}
          </span>
          {ladder.snapshot_timestamp && (
            <span className="text-muted">
              {new Date(ladder.snapshot_timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-muted">Levels:</span>
          <select
            aria-label="Visible depth levels"
            value={levelsCount}
            onChange={(e) => onLevelsCountChange(Number(e.target.value))}
            className="bg-canvas border border-line-strong text-secondary text-xs rounded px-2.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value={3}>3 Levels</option>
            <option value={5}>5 Levels</option>
            <option value={10}>10 Levels</option>
          </select>
        </div>
      </div>

      <p className="text-xs text-muted">Quantity imbalance = (displayed bid quantity − displayed ask quantity) ÷ total displayed quantity, at the selected levels. Near-balanced: ±5%; leaning: 5–20%; heavy: above 20%. A book being unlocked does not establish an open exchange session.</p>
      {/* Depth Ladder Grid (Bids on Left, Asks on Right) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Bids Side */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between text-xs font-semibold text-positive border-b border-line pb-1">
            <span>LEVEL QTY</span>
            <span>CUM NOTIONAL</span>
            <span>BID PRICE</span>
          </div>

          {visibleBids.length === 0 ? (
            <div className="text-xs text-muted py-3 text-center">No bids available</div>
          ) : (
            visibleBids.map((b, idx) => {
              const cumNotional = Number(ladder.cumulative_bid_notional[idx] || b.notional) || 0;
              const bQty = Number(b.quantity) || 0;
              const fillPct = Math.min(100, (bQty / maxLevelQty) * 100);
              const bPrice = Number(b.price) || 0;

              return (
                <div
                  key={`bid-${b.level_index}`}
                  className="relative flex items-center justify-between text-xs py-1 px-2 rounded bg-canvas/60 font-sans overflow-hidden"
                >
                  <div
                    className="absolute right-0 top-0 bottom-0 bg-brand/15 pointer-events-none transition-all duration-500 ease-out"
                    style={{ width: `${fillPct}%` }}
                  />
                  <span className="text-secondary z-10 tabular-nums">{bQty.toLocaleString()}</span>
                  <span className="text-muted text-[11px] z-10 tabular-nums">{currSym}{(cumNotional / 1000).toFixed(1)}k</span>
                  <span className="text-positive font-bold z-10 tabular-nums">{currSym}{bPrice.toFixed(2)}</span>
                </div>
              );
            })
          )}
        </div>

        {/* Asks Side */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between text-xs font-semibold text-negative border-b border-line pb-1">
            <span>ASK PRICE</span>
            <span>CUM NOTIONAL</span>
            <span>LEVEL QTY</span>
          </div>

          {visibleAsks.length === 0 ? (
            <div className="text-xs text-muted py-3 text-center">No asks available</div>
          ) : (
            visibleAsks.map((a, idx) => {
              const cumNotional = Number(ladder.cumulative_ask_notional[idx] || a.notional) || 0;
              const aQty = Number(a.quantity) || 0;
              const fillPct = Math.min(100, (aQty / maxLevelQty) * 100);
              const aPrice = Number(a.price) || 0;

              return (
                <div
                  key={`ask-${a.level_index}`}
                  className="relative flex items-center justify-between text-xs py-1 px-2 rounded bg-canvas/60 font-sans overflow-hidden"
                >
                  <div
                    className="absolute left-0 top-0 bottom-0 bg-rose-500/15 pointer-events-none transition-all duration-500 ease-out"
                    style={{ width: `${fillPct}%` }}
                  />
                  <span className="text-negative font-bold z-10 tabular-nums">{currSym}{aPrice.toFixed(2)}</span>
                  <span className="text-muted text-[11px] z-10 tabular-nums">{currSym}{(cumNotional / 1000).toFixed(1)}k</span>
                  <span className="text-secondary z-10 tabular-nums">{aQty.toLocaleString()}</span>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Depth Imbalance Bar */}
      <div className="bg-canvas p-3 rounded border border-line/80 flex flex-col gap-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted">
            Total Bids: <strong className="text-positive font-sans">{currSym}{(totalBidNotional / 1000).toFixed(1)}k</strong>
          </span>
          <span className="text-secondary font-medium">
            Imbalance:{' '}
            <strong className="font-sans text-brand">
              {visibleImb !== null ? `${(visibleImb * 100).toFixed(1)}%` : '0.0%'}
            </strong>
          </span>
          <span className="text-muted">
            Total Asks: <strong className="text-negative font-sans">{currSym}{(totalAskNotional / 1000).toFixed(1)}k</strong>
          </span>
        </div>

        {/* Visual Imbalance Bar [-1, +1] */}
        <div className="w-full bg-subtle h-2.5 rounded-full overflow-hidden flex">
          <div
            className="bg-brand h-full transition-all duration-500 ease-out"
            style={{
              width: `${
                totalBidQty + totalAskQty > 0
                  ? (totalBidQty / (totalBidQty + totalAskQty)) * 100
                  : 50
              }%`,
            }}
          />
          <div
            className="bg-rose-500 h-full transition-all duration-500 ease-out"
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
