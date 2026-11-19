import { useLiveRefresh } from '../hooks/useLiveRefresh';
import React, { useEffect, useState } from 'react';
import { cn } from '../utils/cn';

const marks = new Set(['AAPL', 'MSFT', 'AMZN', 'NVDA', 'TSLA', 'GOOGL', 'GOOG', 'META']);
export function CompanyLogo({ symbol }: { symbol: string }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [symbol]);
  return <span aria-hidden="true" className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-subtle p-2 text-xs font-semibold text-secondary">
    {marks.has(symbol) && !failed ? <img src={`/company-logos/${symbol}.svg`} alt="" width="20" height="20" loading="lazy" onError={() => setFailed(true)} className="size-5 object-contain" /> : symbol.slice(0, 2)}
  </span>;
}
type History = { retrieved_at?:string; status: string; currency?: string; points: { timestamp: string; close: number }[] };
export function StockSparkline({ symbol }: { symbol: string }) {
  const [data, setData] = useState<History | null>(null);
  useEffect(()=>setData(null),[symbol]);
  const refresh=useLiveRefresh(`stock:${symbol}`,async signal=>{
    const r=await fetch(`/api/v1/dashboard/liquidity/stock-history?symbol=${encodeURIComponent(symbol)}`,{signal});
    if(!r.ok)throw new Error(`Price-history refresh failed (HTTP ${r.status}).`);
    const result=await r.json();
    if(result.symbol!==symbol||result.status!=='available'||!Array.isArray(result.points))throw new Error('Price history unavailable.');
    const points=result.points.filter((p:any)=>typeof p.close==='number'&&Number.isFinite(p.close)&&p.close>0&&Number.isFinite(Date.parse(p.timestamp)));
    if(points.length<2)throw new Error('Insufficient price history.');
    if(!signal.aborted)setData({...result,points});
  });
  const loading=!data&&refresh.running;
  const points = data?.points || [];
  if (loading) return <span role="status" className="mt-4 flex h-20 items-center text-xs text-muted">Loading price history…</span>;
  if (data?.status !== 'available' || points.length < 2) return <span className="mt-4 flex h-20 items-center text-xs text-muted">Price history unavailable</span>;
  const min = Math.min(...points.map(p => p.close)), max = Math.max(...points.map(p => p.close));
  const change = (points[points.length - 1].close / points[0].close - 1) * 100;
  const positive = change >= 0;
  const label = `${symbol}: ${change >= 0 ? '+' : ''}${change.toFixed(2)}% over one month of adjusted daily closes. ${points[0].timestamp.slice(0, 10)} to ${points[points.length - 1].timestamp.slice(0, 10)}. Source: Yahoo Finance.`;
  return <span className="mt-4 block">
    <span className="mb-2 flex items-center justify-between gap-2 text-xs"><span className="text-muted">Stock price · 1M</span><span className={cn('tabular-nums', positive ? 'text-positive' : 'text-negative')}>{positive ? '+' : ''}{change.toFixed(2)}%</span></span>
    <svg role="img" aria-label={label} viewBox="0 0 240 52" className="h-12 w-full" preserveAspectRatio="none"><title>{label}</title><line x1="2" x2="238" y1="49" y2="49" stroke="#e5e5ea" /><polyline fill="none" stroke={positive ? '#18743b' : '#b4232c'} strokeWidth="1.8" vectorEffect="non-scaling-stroke" strokeLinejoin="round" points={points.map((p, i) => `${2 + i / (points.length - 1) * 236},${max === min ? 26 : 47 - (p.close - min) / (max - min) * 42}`).join(' ')} /></svg>
    <span title={refresh.error||'Provider historical bars, automatically checked; not a tick feed.'} className="mt-1 block text-xs text-muted">Daily bar · {points[points.length - 1]?.timestamp.slice(0, 10)} · {refresh.error?'refresh failed':refresh.lastChecked?`checked ${new Date(refresh.lastChecked).toLocaleTimeString()}`:'checking…'}</span>
  </span>;
}
