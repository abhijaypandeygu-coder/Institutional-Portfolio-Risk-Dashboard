import React from 'react';
import { CurrentQuoteItem, InstrumentSpreadDetail } from '../../../types/dashboard';

interface SpreadPanelProps {
  quote: CurrentQuoteItem | null;
  spreadDetail: InstrumentSpreadDetail | null;
  spreadUnit: 'BPS' | 'RELATIVE' | 'ABSOLUTE';
  onUnitChange: (unit: 'BPS' | 'RELATIVE' | 'ABSOLUTE') => void;
  lookbackDays: number;
  onLookbackChange: (days: number) => void;
}

export const SpreadPanel: React.FC<SpreadPanelProps> = ({
  quote,
  spreadDetail,
  spreadUnit,
  onUnitChange,
  lookbackDays,
  onLookbackChange,
}) => {
  if (!quote) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 text-slate-400 text-sm">
        No active quote selected.
      </div>
    );
  }

  const getConditionBadge = (condition: string) => {
    switch (condition) {
      case 'NORMAL':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-emerald-950 text-emerald-400 border border-emerald-800">NORMAL</span>;
      case 'WIDE':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-amber-950 text-amber-400 border border-amber-800">WIDE SPREAD</span>;
      case 'LOCKED':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-purple-950 text-purple-400 border border-purple-800">LOCKED (BID=ASK)</span>;
      case 'CROSSED':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-rose-950 text-rose-400 border border-rose-800">CROSSED (BID&gt;ASK)</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-slate-800 text-slate-300">{condition}</span>;
    }
  };

  const displaySpread = () => {
    if (spreadUnit === 'BPS') {
      return quote.spread_bps !== null && quote.spread_bps !== undefined ? `${quote.spread_bps.toFixed(2)} bps` : '—';
    } else if (spreadUnit === 'RELATIVE') {
      return quote.spread_rel !== null && quote.spread_rel !== undefined ? `${(quote.spread_rel * 100).toFixed(4)}%` : '—';
    } else {
      return quote.spread_abs !== null && quote.spread_abs !== undefined ? `$${quote.spread_abs.toFixed(4)}` : '—';
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg flex flex-col gap-4">
      {/* Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-100 text-base">Top-of-Book Spread</span>
          {getConditionBadge(quote.quote_condition)}
          <span className="text-xs text-slate-400 font-mono">[{quote.venue || 'PRIMARY'}]</span>
        </div>

        <div className="flex items-center gap-3">
          {/* Unit Toggle */}
          <div className="inline-flex rounded-md shadow-sm border border-slate-700 bg-slate-950 p-0.5">
            {(['BPS', 'RELATIVE', 'ABSOLUTE'] as const).map((u) => (
              <button
                key={u}
                onClick={() => onUnitChange(u)}
                className={`px-2.5 py-1 text-xs font-medium rounded ${
                  spreadUnit === u
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {u}
              </button>
            ))}
          </div>

          {/* Lookback select */}
          <select
            value={lookbackDays}
            onChange={(e) => onLookbackChange(Number(e.target.value))}
            className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded px-2.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value={7}>7 Days</option>
            <option value={30}>30 Days</option>
            <option value={60}>60 Days</option>
            <option value={90}>90 Days</option>
          </select>
        </div>
      </div>

      {/* Quote Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-slate-950 border border-slate-800 p-3 rounded flex flex-col">
          <span className="text-xs text-slate-400">Best Bid</span>
          <span className="text-lg font-bold text-emerald-400 font-mono">
            {quote.best_bid !== null && quote.best_bid !== undefined ? `$${quote.best_bid.toFixed(2)}` : '—'}
          </span>
        </div>

        <div className="bg-slate-950 border border-slate-800 p-3 rounded flex flex-col">
          <span className="text-xs text-slate-400">Midpoint Price</span>
          <span className="text-lg font-bold text-slate-200 font-mono">
            {quote.mid_price !== null && quote.mid_price !== undefined ? `$${quote.mid_price.toFixed(3)}` : '—'}
          </span>
        </div>

        <div className="bg-slate-950 border border-slate-800 p-3 rounded flex flex-col">
          <span className="text-xs text-slate-400">Best Ask</span>
          <span className="text-lg font-bold text-rose-400 font-mono">
            {quote.best_ask !== null && quote.best_ask !== undefined ? `$${quote.best_ask.toFixed(2)}` : '—'}
          </span>
        </div>

        <div className="bg-slate-950 border border-slate-800 p-3 rounded flex flex-col">
          <span className="text-xs text-slate-400">Quoted Spread</span>
          <span className="text-lg font-bold text-cyan-400 font-mono">{displaySpread()}</span>
          {quote.spread_in_ticks !== null && quote.spread_in_ticks !== undefined && (
            <span className="text-[11px] text-slate-500 font-mono">
              {quote.spread_in_ticks.toFixed(1)} ticks (tick={quote.tick_size})
            </span>
          )}
        </div>
      </div>

      {/* Historical Statistics Bar */}
      {spreadDetail && (
        <div className="bg-slate-950/70 border border-slate-800/80 rounded p-3 flex flex-wrap items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-4">
            <span className="text-slate-400">
              30d Mean:{' '}
              <strong className="text-slate-200 font-mono">
                {spreadDetail.avg_spread_bps_30d ? `${spreadDetail.avg_spread_bps_30d.toFixed(2)} bps` : '—'}
              </strong>
            </span>
            <span className="text-slate-400">
              Min:{' '}
              <strong className="text-emerald-400 font-mono">
                {spreadDetail.min_spread_bps_30d ? `${spreadDetail.min_spread_bps_30d.toFixed(2)} bps` : '—'}
              </strong>
            </span>
            <span className="text-slate-400">
              Max:{' '}
              <strong className="text-rose-400 font-mono">
                {spreadDetail.max_spread_bps_30d ? `${spreadDetail.max_spread_bps_30d.toFixed(2)} bps` : '—'}
              </strong>
            </span>
          </div>

          {spreadDetail.spread_percentile !== null && spreadDetail.spread_percentile !== undefined && (
            <div className="flex items-center gap-2">
              <span className="text-slate-400">Current Percentile:</span>
              <span className={`px-2 py-0.5 rounded font-mono font-semibold ${
                spreadDetail.spread_percentile > 80
                  ? 'bg-rose-950 text-rose-400 border border-rose-800'
                  : spreadDetail.spread_percentile < 30
                  ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                  : 'bg-slate-800 text-slate-200'
              }`}>
                {spreadDetail.spread_percentile.toFixed(1)}%
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
