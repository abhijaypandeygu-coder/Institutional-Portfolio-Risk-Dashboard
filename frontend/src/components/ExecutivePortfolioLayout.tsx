import { currentPortfolioValue } from '../utils/currentPortfolioValue';
import type { PortfolioLiquidityDashboardResponse } from '../types/dashboard';
import { PerformanceChart } from './performance/PerformanceChart';
import { CompanyLogo, StockSparkline } from './StockIdentity';
import React, { useMemo, useState } from 'react';
import { ArrowDownRight, ArrowUpRight, ArrowRight, Wallet, Search, RefreshCw } from 'lucide-react';
import { useLiveRefresh } from '../hooks/useLiveRefresh';
import { cn } from '../utils/cn';
import type { PortfolioOverviewResponse, StandardMetricValue } from '../types/dashboard';
type Quote = { symbol: string; name: string; price: string; change: string; up: boolean; session?: string };
type MarketSession = { label: string; open: boolean; market: 'US' | 'India' | 'Other' };
type Holding = { position_shares?: number; instrument_id: string; symbol: string; sector?: string; position_notional: number; weight_pct: number };
type Range = '1D' | '1W' | '1M' | '3M' | '6M' | '1Y' | 'All';
type Props = { currentValuation: PortfolioLiquidityDashboardResponse | null; overview: PortfolioOverviewResponse | null; holdings: Holding[]; quotes: Quote[]; portfolioId: string; holdingsPending: boolean; range: Range; onRange: (r: Range) => void; onInstrument: (s: string) => void };
const panel = 'min-w-0 rounded-2xl border border-line bg-surface';
function numeric(value: unknown): number | null { if (value === null || value === undefined || value === '' || (typeof value !== 'number' && typeof value !== 'string')) return null; const n = Number(value); return Number.isFinite(n) ? n : null; }
function metric(m?: StandardMetricValue) { return m?.value_display || (numeric(m?.value) !== null ? Number(m!.value).toLocaleString() : 'Unavailable'); }
function marketSession(symbol: string, providerSession?: string): MarketSession {
  const india = /(^\^NSEI$|\.NS$|\.BO$|^NSE_|^BSE_)/i.test(symbol);
  const market = india ? 'India' : /^(\^?[A-Z][A-Z0-9.-]*$)/i.test(symbol) ? 'US' : 'Other';
  const session = String(providerSession || '').toUpperCase();
  if (session === 'REGULAR') return { label: 'Open · regular session', open: true, market };
  if (session === 'PRE' || session === 'POST') return { label: 'Open · extended session', open: true, market };
  if (market === 'Other') return { label: 'Session unavailable', open: false, market };
  const timezone = market === 'India' ? 'Asia/Kolkata' : 'America/New_York';
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: timezone, weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false }).formatToParts(new Date());
  const weekday = parts.find(part => part.type === 'weekday')?.value || 'Sun';
  const hour = Number(parts.find(part => part.type === 'hour')?.value || 0);
  const minute = Number(parts.find(part => part.type === 'minute')?.value || 0);
  const minutes = hour * 60 + minute;
  const open = !['Sat', 'Sun'].includes(weekday) && (market === 'India' ? minutes >= 9 * 60 + 15 && minutes < 15 * 60 + 30 : minutes >= 9 * 60 + 30 && minutes < 16 * 60);
  return { label: open ? 'Open · regular session' : 'Closed · regular session', open, market };
}

function ExploreStocks({ onInstrument }: { onInstrument: (symbol: string) => void }) {
  const [symbols, setSymbols] = useState('SPY, QQQ, ^NSEI');
  const [query, setQuery] = useState(symbols);
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const normalized = [...new Set(symbols.split(',').map(s => s.trim().toUpperCase()).filter(Boolean))].slice(0, 12);
  const refresh = useLiveRefresh(`explore-quotes:${normalized.join(',')}`, async signal => {
    if (!normalized.length) { setQuotes([]); return; }
    const response = await fetch(`/api/v1/dashboard/liquidity/market-watch?symbols=${encodeURIComponent(normalized.join(','))}`, { signal });
    if (!response.ok) throw new Error('Stock quotes are temporarily unavailable.');
    const result = await response.json();
    if (!Array.isArray(result)) throw new Error('The quote response could not be read.');
    if (!signal.aborted) setQuotes(result.filter(q => typeof q?.symbol === 'string' && typeof q?.change === 'string'));
  }, 60000);
  return <section className="mt-5 border-t border-line pt-5" aria-labelledby="explore-stocks-heading">
    <div className="flex items-center justify-between gap-2"><h2 id="explore-stocks-heading" className="text-base font-semibold text-ink">Explore stocks</h2><Search className="size-4 text-muted" /></div>
    <p className="mt-2 text-xs leading-relaxed text-muted">Follow symbols outside this portfolio. Separate from portfolio holdings.</p>
    <form className="mt-3 flex gap-2" onSubmit={e => { e.preventDefault(); setSymbols(query); }}>
      <label className="sr-only" htmlFor="explore-symbols">Stock symbols</label>
      <input id="explore-symbols" value={query} onChange={e => setQuery(e.target.value)} placeholder="SPY, QQQ, ^NSEI" className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-2.5 py-2 text-xs" maxLength={160} />
      <button type="submit" className="rounded-lg bg-brand px-2.5 text-xs font-semibold text-white">Track</button>
    </form>
    <div className="mt-3 space-y-2">{refresh.running && !quotes.length && <p role="status" className="text-xs text-muted">Loading quotes…</p>}
      {refresh.error && <p role="status" className="text-xs text-warning">{refresh.error}</p>}
      {quotes.map(q => { const pct = Number.parseFloat(q.change.replace(/[^0-9.+-]/g, '')); const session = marketSession(q.symbol, q.session); return <button type="button" key={q.symbol} onClick={() => onInstrument(q.symbol)} className={cn('quote-session-row flex w-full items-center justify-between rounded-lg bg-canvas px-2.5 py-2 text-left text-xs hover:bg-subtle', session.open && 'quote-session-row-open')}>
        <span className="min-w-0"><span className="flex items-center gap-2 font-semibold text-secondary"><CompanyLogo symbol={q.symbol} /><span className="truncate">{q.symbol}</span></span><span className={cn('market-session-label', session.open ? 'market-session-label-open' : 'market-session-label-closed')}><span aria-hidden className="market-session-dot" />{session.label}</span></span>
        <span className={cn('flex shrink-0 items-center tabular-nums', pct >= 0 ? 'text-positive' : 'text-negative')}>{pct >= 0 ? <ArrowUpRight className="size-3" /> : <ArrowDownRight className="size-3" />}{q.change}</span>
      </button>; })}
      {!refresh.running && !refresh.error && !quotes.length && <p className="text-xs text-muted">No quotes found for these symbols.</p>}
    </div>
    <button type="button" onClick={refresh.refresh} disabled={refresh.running} className="mt-3 flex items-center gap-1.5 text-xs font-medium text-brand"><RefreshCw className={cn('size-3', refresh.running && 'animate-spin')} />Refresh quotes</button>
  </section>;
}
export function ExecutivePortfolioLayout({ currentValuation, overview, holdings, quotes, portfolioId, holdingsPending, range, onRange, onInstrument }: Props) {
  const currency = overview?.portfolio.base_currency || 'USD';
  const money = (value: unknown) => numeric(value) === null ? 'Unavailable' : new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 2 }).format(Number(value));
  const headline = currentPortfolioValue(currentValuation);
  const held = new Set(holdings.filter(h => h.position_shares != null ? Number(h.position_shares) !== 0 : Math.abs(Number(h.position_notional)) > 0).map(h => h.symbol.toUpperCase()));
  const movers = quotes.filter(q => held.has(q.symbol.toUpperCase())).map(q => ({ ...q, pct: Number.parseFloat(q.change.replace(/[^0-9.+-]/g, '')) })).filter(q => Number.isFinite(q.pct)).sort((a, b) => b.pct - a.pct);
  const ranked = [...holdings].sort((a, b) => Math.abs(b.position_notional) - Math.abs(a.position_notional));
  const balanceMetrics: [string, StandardMetricValue | undefined][] = [['Total P&L', overview?.total_pnl], ['Unrealized P&L', overview?.unrealized_pnl], ['Realized P&L', overview?.realized_pnl]];
  const date = (d: string) => new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  return <div className="grid min-w-0 grid-cols-1 gap-5 xl:grid-cols-12">
    <PerformanceChart headline={headline} portfolioId={portfolioId} overview={overview} range={range} onRange={onRange} />
    <aside className={cn(panel, 'self-start p-6 xl:col-span-3')} aria-labelledby="movers-heading"><div className="flex items-center justify-between gap-2"><h2 id="movers-heading" className="text-base font-semibold text-ink">Market movers</h2><span className="text-xs text-muted">Quote change</span></div><p className="mt-2 text-xs leading-relaxed text-muted">Current portfolio holdings, ranked by reported quote change.</p><div className="mt-5 space-y-4">{movers.length ? movers.map(q => { const session = marketSession(q.symbol, q.session); return <button type="button" key={q.symbol} onClick={() => onInstrument(q.symbol)} className={cn('quote-session-row relative block w-full overflow-hidden rounded-lg bg-canvas p-3 text-left hover:bg-subtle', session.open && 'quote-session-row-open')}><span aria-hidden className={cn('absolute inset-y-0 left-0 opacity-5', q.pct >= 0 ? 'bg-emerald-400' : 'bg-rose-400')} style={{ width: `${Math.min(100, Math.abs(q.pct) / Math.max(...movers.map(m => Math.abs(m.pct)), 1) * 100)}%` }} /><span className="relative flex justify-between gap-2 text-xs"><span><span className="flex items-center gap-2 font-semibold text-secondary"><CompanyLogo symbol={q.symbol} />{q.symbol}</span><span className={cn('market-session-label', session.open ? 'market-session-label-open' : 'market-session-label-closed')}><span aria-hidden className="market-session-dot" />{session.label}</span></span><span className={cn('flex items-center tabular-nums', q.pct >= 0 ? 'text-positive' : 'text-negative')}>{q.pct >= 0 ? <ArrowUpRight className="size-3" /> : <ArrowDownRight className="size-3" />}{q.change}</span></span></button>; }) : <p className="text-sm text-muted">No market quotes available.</p>}</div><p className="mt-4 text-[10px] leading-relaxed text-muted">Session status follows regular exchange hours; holidays and trading halts may differ.</p><button type="button" onClick={() => onInstrument(holdings[0]?.symbol || 'AAPL')} className="mt-6 flex items-center gap-2 rounded text-xs font-medium text-positive">Open market analytics <ArrowRight className="size-3" /></button><ExploreStocks onInstrument={onInstrument} /></aside>
    <section className="min-w-0 xl:col-span-9" aria-labelledby="holdings-heading"><div className="mb-4 flex items-center justify-between"><h2 id="holdings-heading" className="text-base font-semibold text-ink">Your portfolio</h2><span className="text-xs text-muted">{holdings.length} holdings · by position size</span></div><div className="grid grid-cols-1 gap-3 sm:grid-cols-3">{ranked.slice(0, 3).map(h => <button type="button" key={h.instrument_id || h.symbol} onClick={() => onInstrument(h.symbol)} className={cn(panel, 'p-4 text-left hover:border-line-strong')}><span className="flex justify-between gap-2"><CompanyLogo symbol={h.symbol} /><span className="text-xs tabular-nums text-muted">{numeric(h.weight_pct) === null ? 'Weight unavailable' : `${Number(h.weight_pct).toFixed(1)}% weight`}</span></span><span className="mt-4 block text-sm font-semibold text-ink">{h.symbol}</span><span className="mt-1 block text-xs text-muted">{h.sector || 'Portfolio holding'}</span><span className="mt-4 block text-base font-semibold tabular-nums text-ink">{money(h.position_notional)}</span><StockSparkline symbol={h.symbol} /></button>)}</div>{!holdings.length && <p className={cn(panel, 'p-5 text-sm text-muted')}>{holdingsPending ? 'Loading portfolio holdings…' : 'No holdings returned for this portfolio.'}</p>}
      <div className={cn(panel, 'mt-4 overflow-x-auto')}><table className="w-full text-left text-xs"><caption className="sr-only">Portfolio position values and weights</caption><thead className="text-muted"><tr><th scope="col" className="px-4 py-3">Holding</th><th scope="col" className="px-4 py-3">Sector</th><th scope="col" className="px-4 py-3 text-right">Position value</th><th scope="col" className="px-4 py-3 text-right">Weight</th></tr></thead><tbody>{ranked.map(h => <tr key={h.instrument_id || h.symbol} className="border-t border-line"><th scope="row" className="px-4 py-4"><button type="button" onClick={() => onInstrument(h.symbol)} className="flex items-center gap-2 rounded font-semibold text-ink hover:text-positive"><CompanyLogo symbol={h.symbol} />{h.symbol}</button></th><td className="px-4 py-4 text-muted">{h.sector || '—'}</td><td className="whitespace-nowrap px-4 py-4 text-right tabular-nums text-secondary">{money(h.position_notional)}</td><td className="px-4 py-4 text-right tabular-nums text-secondary">{numeric(h.weight_pct) === null ? '—' : `${Number(h.weight_pct).toFixed(1)}%`}</td></tr>)}</tbody></table></div>
    </section>
    <aside aria-labelledby="balance-heading" className={cn(panel, 'self-start p-6 xl:col-span-3')}><div className="flex items-center justify-between"><h2 id="balance-heading" className="text-sm font-semibold text-ink">Portfolio balance</h2><Wallet className="size-4 text-muted" /></div><p className="mt-5 text-xs text-muted">{headline.label}</p><p className="mt-2 break-words text-2xl font-semibold tabular-nums text-ink">{headline.display}</p><p className="mt-2 text-xs text-muted">{currency} · selected local portfolio</p><dl className="mt-6 space-y-5 border-t border-line pt-5">{balanceMetrics.map(([label, m]) => <div key={label}><dt className="text-xs text-muted">{label}</dt><dd className={cn('mt-1 text-lg font-medium tabular-nums', numeric(m?.value) === null ? 'text-muted' : Number(m?.value) < 0 ? 'text-negative' : Number(m?.value) > 0 ? 'text-positive' : 'text-ink')}>{metric(m)}</dd></div>)}</dl><p className="mt-6 border-t border-line pt-4 text-xs text-muted">{overview?.total_nav?.as_of ? `Valued ${date(overview.total_nav.as_of)}` : 'Valuation timestamp unavailable'}</p></aside>
  </div>;
}
