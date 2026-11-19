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
      <div className="bg-surface border border-line rounded-lg p-5 text-muted text-sm">
        No active quote selected.
      </div>
    );
  }

  const getConditionBadge = (condition: string) => {
    switch (condition) {
      case 'NORMAL':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-positive-soft text-positive border border-positive/20">NORMAL</span>;
      case 'WIDE':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-warning-soft text-warning border border-warning/20">WIDE SPREAD</span>;
      case 'LOCKED':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-info-soft text-info border border-info/20">LOCKED (BID=ASK)</span>;
      case 'CROSSED':
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-negative-soft text-negative border border-negative/20">CROSSED (BID&gt;ASK)</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-subtle text-secondary">{condition}</span>;
    }
  };

  const getCurrencySymbol = () => {
    const curr = quote.currency || (quote.symbol.endsWith('.NS') || quote.symbol.endsWith('.BO') ? 'INR' : 'USD');
    if (curr === 'INR') return '₹';
    if (curr === 'EUR') return '€';
    if (curr === 'GBP') return '£';
    return '$';
  };
  const currSym = getCurrencySymbol();

  const displaySpread = () => {
    if (spreadUnit === 'BPS') {
      return quote.spread_bps !== null && quote.spread_bps !== undefined ? `${Number(quote.spread_bps).toFixed(2)} bps` : '—';
    } else if (spreadUnit === 'RELATIVE') {
      return quote.spread_rel !== null && quote.spread_rel !== undefined ? `${(Number(quote.spread_rel) * 100).toFixed(4)}%` : '—';
    } else {
      return quote.spread_abs !== null && quote.spread_abs !== undefined ? `${currSym}${Number(quote.spread_abs).toFixed(4)}` : '—';
    }
  };

  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-lg flex flex-col gap-4">
      {/* Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-ink text-base">Top-of-Book Spread</span>
          {getConditionBadge(quote.quote_condition)}
          <span className="text-xs text-muted font-sans">[{quote.venue || 'PRIMARY'}]</span>
        </div>

        <div className="flex items-center gap-3">
          {/* Unit Toggle */}
          <div className="inline-flex rounded-md shadow-sm border border-line-strong bg-canvas p-0.5">
            {(['BPS', 'RELATIVE', 'ABSOLUTE'] as const).map((u) => (
              <button
                key={u}
                onClick={() => onUnitChange(u)}
                className={`px-2.5 py-1 text-xs font-medium rounded ${spreadUnit === u
                    ? 'bg-brand text-white'
                    : 'text-muted hover:text-secondary'
                  }`}
              >
                {u}
              </button>
            ))}
          </div>

          {/* Lookback select */}
          <select
            aria-label="Spread history lookback"
            value={lookbackDays}
            onChange={(e) => onLookbackChange(Number(e.target.value))}
            className="bg-canvas border border-line-strong text-secondary text-xs rounded px-2.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
          >
            <option value={7}>7 Days</option>
            <option value={30}>30 Days</option>
            <option value={60}>60 Days</option>
            <option value={90}>90 Days</option>
            <option value={180}>180 Days (6M)</option>
            <option value={365}>365 Days (1Y)</option>
          </select>
        </div>
      </div>

      {/* Quote Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-canvas border border-line p-3 rounded flex flex-col">
          <span className="text-xs text-muted">Best Bid</span>
          <span className="text-lg font-bold text-positive font-sans">
            {quote.best_bid !== null && quote.best_bid !== undefined ? `${currSym}${Number(quote.best_bid).toFixed(2)}` : '—'}
          </span>
        </div>

        <div className="bg-canvas border border-line p-3 rounded flex flex-col">
          <span className="text-xs text-muted">Midpoint Price</span>
          <span className="text-lg font-bold text-secondary font-sans">
            {quote.mid_price !== null && quote.mid_price !== undefined ? `${currSym}${Number(quote.mid_price).toFixed(3)}` : '—'}
          </span>
        </div>

        <div className="bg-canvas border border-line p-3 rounded flex flex-col">
          <span className="text-xs text-muted">Best Ask</span>
          <span className="text-lg font-bold text-negative font-sans">
            {quote.best_ask !== null && quote.best_ask !== undefined ? `${currSym}${Number(quote.best_ask).toFixed(2)}` : '—'}
          </span>
        </div>

        <div className="bg-canvas border border-line p-3 rounded flex flex-col">
          <span className="text-xs text-muted">Quoted Spread</span>
          <span className="text-lg font-bold text-brand font-sans">{displaySpread()}</span>
          {quote.spread_in_ticks !== null && quote.spread_in_ticks !== undefined && (
            <span className="text-[11px] text-muted font-sans">
              {Number(quote.spread_in_ticks).toFixed(1)} ticks (tick={quote.tick_size})
            </span>
          )}
        </div>
      </div>

      {/* Historical Statistics Bar */}
      {spreadDetail && (
        <div className="bg-canvas/70 border border-line/80 rounded p-3 flex flex-wrap items-center justify-between gap-4 text-xs">
          <div className="flex flex-wrap items-center gap-4">
            <span className="text-muted">
              {lookbackDays}d Mean:{' '}
              {spreadDetail.avg_spread_bps_30d != null ? (
                <strong className="text-secondary font-sans">
                  {Number(spreadDetail.avg_spread_bps_30d).toFixed(2)} bps
                </strong>
              ) : (
                <span className="text-warning/90 font-sans text-[11px] bg-warning-soft/40 px-1.5 py-0.5 rounded border border-warning/20">
                  N/A – insufficient history
                </span>
              )}
            </span>
            <span className="text-muted">
              Min:{' '}
              {spreadDetail.min_spread_bps_30d != null ? (
                <strong className="text-positive font-sans">
                  {Number(spreadDetail.min_spread_bps_30d).toFixed(2)} bps
                </strong>
              ) : (
                <span className="text-warning/90 font-sans text-[11px] bg-warning-soft/40 px-1.5 py-0.5 rounded border border-warning/20">
                  N/A – insufficient history
                </span>
              )}
            </span>
            <span className="text-muted">
              Max:{' '}
              {spreadDetail.max_spread_bps_30d != null ? (
                <strong className="text-negative font-sans">
                  {Number(spreadDetail.max_spread_bps_30d).toFixed(2)} bps
                </strong>
              ) : (
                <span className="text-warning/90 font-sans text-[11px] bg-warning-soft/40 px-1.5 py-0.5 rounded border border-warning/20">
                  N/A – insufficient history
                </span>
              )}
            </span>
          </div>

          <div className="flex items-center gap-3">
            {spreadDetail.spread_percentile !== null && spreadDetail.spread_percentile !== undefined && (
              <div className="flex items-center gap-2">
                <span className="text-muted">Historical position:</span>
                <span className={`px-2 py-0.5 rounded font-sans font-semibold ${Number(spreadDetail.spread_percentile) > 80
                    ? 'bg-negative-soft text-negative border border-negative/20'
                    : Number(spreadDetail.spread_percentile) < 30
                      ? 'bg-positive-soft text-positive border border-positive/20'
                      : 'bg-subtle text-secondary'
                  }`}>
                  {quote.spread_bps != null && spreadDetail.min_spread_bps_30d != null && Number(quote.spread_bps) < Number(spreadDetail.min_spread_bps_30d)
                    ? `Below ${lookbackDays}-day observed range`
                    : quote.spread_bps != null && spreadDetail.max_spread_bps_30d != null && Number(quote.spread_bps) > Number(spreadDetail.max_spread_bps_30d)
                    ? `Above ${lookbackDays}-day observed range`
                    : `${Number(spreadDetail.spread_percentile).toFixed(1)}th percentile`}
                </span>
              </div>
            )}
            <div className="flex items-center gap-1.5 text-[11px] font-sans text-muted pl-2 border-l border-line">
              <span>EXCHANGE: {quote.symbol.endsWith('.NS') ? 'NSE/INDIA' : (quote.symbol.endsWith('.BO') ? 'BSE/INDIA' : 'US/REGULAR')}</span>
              <span>•</span>
              <span>QUOTE: {quote.source_kind === 'ESTIMATED' ? 'ESTIMATED' : quote.source_kind === 'PROVIDER_REPORTED' ? 'PROVIDER SNAPSHOT' : 'RECORDED SNAPSHOT'}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
