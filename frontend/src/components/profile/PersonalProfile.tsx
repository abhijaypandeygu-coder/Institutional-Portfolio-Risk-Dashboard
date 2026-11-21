import React, { useState } from 'react';
import { ChartNoAxesCombined } from 'lucide-react';
import { useLiveRefresh } from '../../hooks/useLiveRefresh';
import type { HoldingLiquiditySummary, PortfolioLiquidityDashboardResponse } from '../../types/dashboard';
import { CompanyLogo } from '../StockIdentity';
import { ProfileNews } from './ProfileNews';
import { currentPortfolioValue } from '../../utils/currentPortfolioValue';

type Point = { day: number; change: number };
type Lot = { instrument_id: string; position_side: string; remaining_quantity: string | number; remaining_basis_base: string | number };
const palette = ['#2555be', '#a34416', '#007570', '#8945a3', '#a53163', '#526c17', '#654ec3', '#805723'];
const dateLabel = (day: number) => new Date(day).toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' });
const percent = (n: number) => (n > 0 ? '+' : '') + n.toFixed(2) + '%';
function sessionStatus(symbol: string) {
  const india = /(^\^NSEI$|\.NS$|\.BO$|^NSE_|^BSE_)/i.test(symbol);
  const market = india ? 'India' : 'US';
  const timezone = india ? 'Asia/Kolkata' : 'America/New_York';
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: timezone, weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false }).formatToParts(new Date());
  const weekday = parts.find(part => part.type === 'weekday')?.value || 'Sun';
  const minutes = Number(parts.find(part => part.type === 'hour')?.value || 0) * 60 + Number(parts.find(part => part.type === 'minute')?.value || 0);
  const open = !['Sat', 'Sun'].includes(weekday) && (india ? minutes >= 555 && minutes < 930 : minutes >= 570 && minutes < 960);
  return { market, open, label: open ? 'Open · regular session' : 'Closed · regular session' };
}

async function history(symbol: string, signal: AbortSignal): Promise<Point[]> {
  const response = await fetch('/api/v1/dashboard/liquidity/stock-history?symbol=' + encodeURIComponent(symbol), { signal });
  if (!response.ok) throw new Error();
  const data = await response.json();
  if (data.status !== 'available' || data.symbol !== symbol || data.adjusted !== true || !Array.isArray(data.points)) return [];
  const closes = new Map<number, number>();
  for (const p of data.points) {
    if (typeof p.timestamp !== 'string' || !/^\d{4}-\d{2}-\d{2}/.test(p.timestamp) || !Number.isFinite(p.close) || p.close <= 0) continue;
    // Preserve each exchange's session date across time zones.
    const day = Date.parse(p.timestamp.slice(0, 10) + 'T00:00:00Z');
    if (Number.isFinite(day)) closes.set(day, p.close);
  }
  const ordered = [...closes].sort(([a], [b]) => a - b);
  return ordered.length < 2 ? [] : ordered.map(([day, close]) => ({ day, change: (close / ordered[0][1] - 1) * 100 }));
}

function PositionChart({ symbols }: { symbols: string[] }) {
  const [series, setSeries] = useState<Record<string, Point[]>>({});
  const [hidden, setHidden] = useState<string[]>([]);
  const refresh = useLiveRefresh('profile-prices:' + symbols.join(','), async signal => {
    const entries: [string, Point[]][] = [];
    for (let offset = 0; offset < symbols.length && !signal.aborted; offset += 6) {
      await Promise.all(symbols.slice(offset, offset + 6).map(async symbol => {
        entries.push([symbol, await history(symbol, signal).catch(() => [])]);
      }));
      if (!signal.aborted) setSeries(previous => ({ ...previous, ...Object.fromEntries(entries) }));
    }
  }, 120000);
  const points = symbols.filter(s => !hidden.includes(s)).flatMap(s => series[s] || []);
  const low = points.reduce((v, p) => Math.min(v, p.change), 0);
  const high = points.reduce((v, p) => Math.max(v, p.change), 0);
  const span = high - low || 2;
  const bottom = low - span * .08, top = high + span * .08;
  const first = points.reduce((v, p) => Math.min(v, p.day), Infinity);
  const last = points.reduce((v, p) => Math.max(v, p.day), -Infinity);
  const x = (day: number) => 60 + (day - first) / (last - first || 1) * 631;
  const y = (change: number) => 19 + (top - change) / (top - bottom) * 180;
  return <section className="profile-card" aria-labelledby="profile-chart-heading">
    <div className="flex flex-wrap items-center justify-between gap-3"><h2 id="profile-chart-heading" className="text-lg font-semibold">Company performance</h2>
      <button className="text-sm text-brand" onClick={refresh.refresh} disabled={refresh.running}>Refresh prices</button></div>
    <p className="mt-1 text-sm text-muted">One month of adjusted daily closes from Yahoo Finance. Each line starts at 0% on its first available trading day and tracks the share price in its own currency.</p>
    <div className="mt-3 flex flex-wrap gap-2" aria-label="Market session status">{symbols.map(symbol => { const session = sessionStatus(symbol); return <span key={symbol} className={session.open ? 'market-session-chip market-session-chip-open' : 'market-session-chip market-session-chip-closed'}><span aria-hidden className="market-session-dot" />{symbol}: {session.label}</span>; })}</div>
    {points.length > 0 ? <svg viewBox="0 0 708 231" className="profile-plot" role="img" aria-label="One-month percentage price change for the selected companies">
      {[top, (top + bottom) / 2, bottom].map(v => <g key={v}><line x1="60" x2="691" y1={y(v)} y2={y(v)} stroke="#dce2ec" /><text x="52" y={y(v) + 4} textAnchor="end">{v.toFixed(1)}%</text></g>)}
      <line x1="60" x2="691" y1={y(0)} y2={y(0)} stroke="#818b9d" strokeDasharray="4 4" />
      {symbols.map((s, i) => !hidden.includes(s) && series[s]?.length > 0 && <polyline key={s} fill="none" stroke={palette[i % palette.length]} strokeWidth="2" vectorEffect="non-scaling-stroke"
        strokeDasharray={Math.floor(i / palette.length) % 2 ? '6 3' : undefined} points={series[s].map(p => x(p.day) + ',' + y(p.change)).join(' ')}><title>{s}</title></polyline>)}
      <text x="60" y="223">{dateLabel(first)}</text><text x="691" y="223" textAnchor="end">{dateLabel(last)}</text>
    </svg> : <p role="status" className="my-6 text-sm text-muted">{!symbols.length ? 'No open stock positions.' : refresh.running ? 'Loading daily prices…' : 'No price series available for the current selection.'}</p>}
    <div className="mt-3 flex flex-wrap gap-2">{symbols.map((s, i) => {
      const rows = series[s], latest = rows?.[rows.length - 1];
      return <button key={s} aria-pressed={!hidden.includes(s)} className="profile-series" onClick={() => setHidden(old => old.includes(s) ? old.filter(t => t !== s) : [...old, s])}>
        <i aria-hidden="true" style={{ background: palette[i % palette.length] }} /><strong>{s}</strong><span className={sessionStatus(s).open ? 'market-session-inline market-session-inline-open' : 'market-session-inline'}><span aria-hidden className="market-session-dot" />{sessionStatus(s).open ? 'Open' : 'Closed'}</span>
        <span>{latest ? percent(latest.change) + ' · ' + dateLabel(latest.day) : rows || refresh.error ? 'History unavailable' : 'Loading…'}</span></button>;
    })}</div>
  </section>;
}

function matchedBasis(h: HoldingLiquiditySummary, lots: Lot[]) {
  const rows = lots.filter(l => l.instrument_id === h.instrument_id && l.position_side === h.position_direction && Number(l.remaining_quantity) > 0);
  const units = rows.reduce((sum, row) => sum + Number(row.remaining_quantity), 0);
  if (!rows.length || Math.abs(units - Math.abs(h.position_shares)) > 0.000001 ||
      rows.some(row => row.remaining_basis_base == null || !Number.isFinite(Number(row.remaining_basis_base)))) return null;
  return rows.reduce((sum, row) => sum + Number(row.remaining_basis_base), 0);
}

export function PersonalProfile({ portfolioId, name, data, error, revision, children }: {
  portfolioId: string; name?: string; data: PortfolioLiquidityDashboardResponse | null; error: string | null; revision: number; children: React.ReactNode;
}) {
  const [lots, setLots] = useState<Lot[]>([]);
  const basisRefresh = useLiveRefresh('profile-lots:' + portfolioId + ':' + revision, async signal => {
    const response = await fetch('/api/v1/valuations/portfolios/' + encodeURIComponent(portfolioId) + '/lots', { signal });
    if (!response.ok) throw new Error('Cost basis unavailable.');
    const rows = await response.json();
    if (!Array.isArray(rows)) throw new Error('Cost basis unavailable.');
    if (!signal.aborted) setLots(rows.filter(row => row.portfolio_id === portfolioId));
  }, 120000);
  const holdings = (data?.holdings || []).filter(h => Number.isFinite(Number(h.position_shares)) && Number(h.position_shares) !== 0);
  const symbols = [...new Set(holdings.map(h => h.symbol.toUpperCase()))].sort();
  const currency = data?.reporting_currency;
  const money = (value: number | null) => currency && value !== null && Number.isFinite(value) ? new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value) : 'Unavailable';
  const headline = currentPortfolioValue(data);
  return <div className="space-y-5">
    <header className="workspace-hero flex flex-wrap items-center justify-between gap-4"><div><h1>Personal profile</h1><p className="mt-2 text-sm">{name || 'Selected portfolio'}</p></div>
      <div><p className="text-xs">{headline.label}</p><strong className="text-2xl tabular-nums">{headline.display}</strong></div></header>
    {error && <p role="status" className="text-sm text-warning">{error}</p>}
    {data ? <PositionChart symbols={symbols} /> : <p role="status" className="text-sm text-muted">{error ? 'Holdings unavailable.' : 'Loading portfolio holdings…'}</p>}
    {!!holdings.length && <section className="profile-card"><h2 className="flex items-center gap-2 text-lg font-semibold"><ChartNoAxesCombined size={18} />Open positions</h2>
      <p className="mt-1 text-xs text-muted">Cost basis covers the remaining units with matching recorded lots. Position values are in {currency || 'the portfolio currency'}.</p>
      <div className="mt-4 overflow-x-auto"><table className="profile-table w-full text-left text-sm"><thead><tr><th>Company</th><th>Shares</th><th>Cost basis</th><th>Position value</th></tr></thead>
        <tbody>{holdings.map(h => <tr key={h.instrument_id}><th><span className="inline-flex items-center gap-2"><CompanyLogo symbol={h.symbol} />{h.symbol}</span></th><td>{h.position_direction} · {Math.abs(h.position_shares)}</td>
          <td>{money(basisRefresh.error ? null : matchedBasis(h, lots))}</td><td>{money(h.valuation_complete === false || h.position_notional == null ? null : (h.position_direction === 'SHORT' ? -1 : 1) * Math.abs(h.position_notional))}</td></tr>)}</tbody></table></div></section>}
    <ProfileNews symbols={symbols} />
    {children}
  </div>;
}
