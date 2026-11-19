import React, { useEffect, useState } from 'react';
import { CurrentQuoteItem, OrderBookDepthLadder, PortfolioLiquidityDashboardResponse } from '../../../types/dashboard';
import { DepthPoint, MarketContext, money, simulated, sourceAge, tierDistribution } from '../../../utils/liquidityAnalytics';

export function LiquidityDistribution({ data }: { data: PortfolioLiquidityDashboardResponse | null }) {
  if (!data) return null;
  const rows = tierDistribution(data.holdings);
  const labels: Record<string, string> = { TIER_1_HIGH: 'Tier 1 · High liquidity', TIER_2_MODERATE: 'Tier 2 · Moderate liquidity', TIER_3_LOW: 'Tier 3 · Low liquidity', TIER_4_ILLIQUID: 'Tier 4 · Illiquid', UNCLASSIFIED: 'Unclassified holdings' };
  const colors = ['bg-positive', 'bg-brand', 'bg-warning', 'bg-negative', 'bg-muted'];
  const total = rows.reduce((s, r) => s + r.weight, 0);
  return <section aria-labelledby="liquidity-distribution-heading" className="rounded-xl border border-line bg-surface p-5 space-y-4">
    <h2 id="liquidity-distribution-heading" className="text-lg font-semibold text-ink">Portfolio liquidity distribution</h2>
    <p className="text-xs text-muted">Value weights · {data.weight_basis || 'Weight basis unavailable'} · denominator {money(data.total_nav, data.reporting_currency)}</p>
    {rows.map((r, i) => <div key={r.tier} className="space-y-1">
      <div className="flex justify-between text-sm"><span>{labels[r.tier]}</span><strong className="tabular-nums">{r.weight.toFixed(2)}%</strong></div>
      <div role="img" aria-label={`${labels[r.tier]}: ${r.weight.toFixed(2)} percent`} className="h-2 overflow-hidden rounded bg-subtle"><div className={`h-full ${colors[i]}`} style={{ width: `${Math.min(100, Math.max(0, r.weight))}%` }} /></div>
    </div>)}
    {data.weight_basis === 'Portfolio NAV' && total < 99.99 && <p className="text-xs text-muted">NAV outside displayed holdings: {(100 - total).toFixed(2)}% (not assigned a liquidity tier).</p>}
    {total > 100.01 && <p className="text-xs text-muted">Gross exposure totals {total.toFixed(2)}% of NAV; long/short leverage can exceed 100%. Bars are capped visually at 100%.</p>}
    {data.holdings.length === 0 && <p className="text-sm text-muted">No recorded holdings available.</p>}
  </section>;
}

export function MarketDataStatus({ quote, ladder, connected, streaming, context }: { quote: CurrentQuoteItem | null; ladder: OrderBookDepthLadder | null; connected: boolean; streaming: boolean; context: MarketContext | null }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(id); }, []);
  const sourceTime = quote?.source_timestamp;
  const generated = simulated(quote) || simulated(ladder);
  return <section aria-label="Market session and data freshness" className="rounded-xl border border-line bg-surface p-5 space-y-3">
    <h3 className="font-semibold">Market session &amp; data freshness</h3>
    <dl className="grid grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
      <div><dt className="text-muted">Feed connection</dt><dd>{connected ? 'Connected' : 'Disconnected'} · {streaming ? 'Provider stream' : 'Snapshot view'}</dd></div>
      <div><dt className="text-muted">Exchange session</dt><dd>{context?.session_status.replace(/_/g, ' ').toLowerCase() || 'Unknown'}</dd></div>
      <div><dt className="text-muted">Quote source age</dt><dd>{simulated(quote) ? 'Unavailable · estimated quote' : sourceAge(sourceTime, now)}</dd></div>
      <div><dt className="text-muted">Last source market update</dt><dd>{sourceTime && !simulated(quote) ? new Date(sourceTime).toLocaleString() : 'Unavailable'}</dd></div>
      <div><dt className="text-muted">Data quality / provenance</dt><dd>{generated ? 'Contains simulated / estimated depth' : ladder?.quality_status || quote?.source_kind || 'Unverified'}</dd></div>
      <div><dt className="text-muted">Instrument session</dt><dd>{context ? `${context.exchange} · ${context.regular_hours} · ${context.timezone}` : 'Calendar unavailable'}</dd></div>
    </dl>
    <p className="text-xs text-muted">{quote?.timestamp_basis || 'Quote timestamp basis unavailable'}. {context?.calendar_basis || 'Exchange schedule unavailable'}. Connection status does not establish market-open status or quote freshness.</p>
  </section>;
}

export function DepthHistoryChart({ points, levels, currency }: { points: DepthPoint[]; levels: number; currency: string }) {
  const max = Math.max(1, ...points.flatMap(p => [p.bid, p.ask]));
  const first = Date.parse(points[0]?.timestamp || '') || 0;
  const lastPoint = points.length > 0 ? points[points.length - 1] : undefined;
  const span = Math.max(1, (Date.parse(lastPoint?.timestamp || '') || first) - first);
  const x = (p: DepthPoint) => 60 + (Date.parse(p.timestamp) - first) / span * 600;
  const y = (n: number) => 190 - n / max * 160;
  return <section aria-labelledby="depth-history-heading" className="rounded-xl border border-line bg-surface p-5 space-y-3">
    <h3 id="depth-history-heading" className="font-semibold">Bid and ask depth history</h3>
    <p className="text-xs text-muted">Top {levels} levels · notional in {currency} · recorded snapshots and provider updates observed in this session. Simulated depth is excluded.</p>
    {points.length < 2 ? <p className="py-8 text-sm text-muted">{points.length ? 'One observed snapshot. Waiting for another distinct source update.' : 'No recorded depth history available for this instrument and level selection.'}</p> : <>
      <div className="flex gap-5 text-xs"><span className="text-brand">— Bid notional</span><span className="text-negative">— Ask notional</span></div>
      <svg viewBox="0 0 710 230" className="w-full" role="img" aria-label={`Bid and ask notional depth history, ${points.length} observations in ${currency}`}>
        {[0, .5, 1].map(t => <g key={t}><line x1="60" x2="660" y1={y(max*t)} y2={y(max*t)} stroke="currentColor" opacity=".15"/><text x="54" y={y(max*t)+4} textAnchor="end" fontSize="11" fill="currentColor">{(max*t/1000).toFixed(0)}k</text></g>)}
        <polyline fill="none" stroke="var(--color-brand, #007aff)" strokeWidth="2" points={points.map(p => `${x(p)},${y(p.bid)}`).join(' ')}/>
        <polyline fill="none" stroke="var(--color-negative, #d92d20)" strokeWidth="2" points={points.map(p => `${x(p)},${y(p.ask)}`).join(' ')}/>
        <text x="60" y="219" fontSize="11" fill="currentColor">{new Date(first).toLocaleString()}</text>
        <text x="660" y="219" textAnchor="end" fontSize="11" fill="currentColor">{new Date(lastPoint!.timestamp).toLocaleString()}</text>
      </svg>
    </>}
    <details className="text-xs"><summary className="cursor-pointer text-muted">Observed depth data ({points.length})</summary><div className="max-h-56 overflow-auto"><table className="w-full"><thead><tr><th>Source time</th><th>Bid notional</th><th>Ask notional</th></tr></thead><tbody>{points.map(p => <tr key={p.timestamp}><td>{new Date(p.timestamp).toLocaleString()}</td><td>{money(p.bid, currency)}</td><td>{money(p.ask, currency)}</td></tr>)}</tbody></table></div></details>
  </section>;
}
