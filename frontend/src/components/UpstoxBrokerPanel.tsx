import React, { useEffect, useState } from 'react';

type Mode = 'account' | 'liquidity' | 'risk' | 'stress' | 'feeds';
const titles: Record<Mode, string> = {
  account: 'Upstox broker account', liquidity: 'Upstox depth & spread', risk: 'Upstox monitoring rules',
  stress: 'Upstox market inputs & price shocks', feeds: 'Upstox connection & subscriptions',
};
const cell = 'px-3 py-2 text-left border-b border-line';
const field = 'bg-canvas border border-line-strong rounded px-3 py-2 text-sm text-ink';
const fmt = (v: unknown, digits = 2): string => v === null || v === undefined ? 'Unavailable' :
  typeof v === 'number' ? v.toLocaleString('en-IN', { maximumFractionDigits: digits }) : String(v);

function Table({ rows, columns }: { rows: any[]; columns: [string, string][] }) {
  if (!rows.length) return <p className="text-muted text-sm">No records returned.</p>;
  return <div className="overflow-x-auto"><table className="text-xs w-full"><thead><tr>{columns.map(([k, label]) => <th className={cell} key={k}>{label}</th>)}</tr></thead>
    <tbody>{rows.map((r, i) => <tr key={i}>{columns.map(([k]) => <td key={k} className={cell}>{fmt(r[k])}</td>)}</tr>)}</tbody></table></div>;
}

export function UpstoxBrokerPanel({ mode }: { mode: Mode }) {
  const [access, setAccess] = useState('');
  const [keys, setKeys] = useState('NSE_EQ|INE002A01018');
  const [data, setData] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [poll, setPoll] = useState(false);
  const [shock, setShock] = useState(-10);
  const [quantity, setQuantity] = useState('0');
  const [movement, setMovement] = useState(5);
  const [spread, setSpread] = useState(25);
  const [loss, setLoss] = useState(10000);
  const [exposure, setExposure] = useState(1000000);
  const [volatility, setVolatility] = useState(.4);
  const [depthDrop, setDepthDrop] = useState(50);
  const [streamMode, setStreamMode] = useState('full');
  const instrumentKeys = () => keys.split(',').map(k => k.trim()).filter(Boolean);
  const body = () => ({ instrument_keys: instrumentKeys(),
    ...(mode === 'stress' ? { shock_pct: shock, quantities: Object.fromEntries(instrumentKeys().map(k => [k, Number(quantity)])) } : {}),
    ...(mode === 'risk' ? { limits: { movement_pct: movement, spread_bps: spread, loss_inr: loss,
      gross_exposure_inr: exposure, annualized_volatility: volatility, depth_drop_pct: depthDrop, stale_seconds: 120 } } : {}),
  });
  async function request(path: string, payload?: any) {
    const r = await fetch(`/api/v1/broker/upstox/${path}`, {
      method: payload === undefined ? 'GET' : 'POST',
      headers: { 'X-API-Key': access, 'Content-Type': 'application/json' },
      ...(payload !== undefined ? { body: JSON.stringify(payload) } : {}),
    });
    let result: any;
    try { result = await r.json(); }
    catch { throw new Error(`Backend unavailable or returned an invalid response (HTTP ${r.status}).`); }
    if (!r.ok) throw new Error(typeof result.detail === 'string' ? result.detail : result.detail?.code || result.error?.message || `HTTP ${r.status}`);
    return result;
  }
  async function load() {
    if (!access || busy) return;
    setBusy(true); setError('');
    try {
      const response = await request(mode === 'feeds' ? 'status' : mode, mode === 'feeds' ? undefined : mode === 'account' ? {} : body());
      setData(response);
      if (mode !== 'feeds') setStatus(await request('status'));
    } catch (e) { setError(e instanceof Error ? e.message : 'Broker request failed'); setData(null); }
    finally { setBusy(false); }
  }
  async function action(path: string, payload: any) {
    setBusy(true); setError('');
    try { await request(path, payload); setData(await request('status')); }
    catch (e) { setError(e instanceof Error ? e.message : 'Action failed'); }
    finally { setBusy(false); }
  }
  useEffect(() => {
    if (!poll || !access || mode === 'stress') return;
    const id = window.setInterval(load, 30000);
    return () => window.clearInterval(id);
  }, [poll, access, keys, mode, movement, spread, loss, exposure, volatility, depthDrop, busy]);
  return <section aria-busy={busy} aria-label={titles[mode]} className="broker-panel my-5 min-w-0 rounded-lg border border-line bg-surface p-5 sm:p-6 space-y-4 text-ink">
    <div><h2 className="text-base font-semibold">{titles[mode]}</h2>
      <p className="text-xs text-muted mt-1">Configured broker account · INR · separate from the selected local portfolio. Market data may be stale when the exchange is closed.</p></div>
    <details className="rounded border border-line p-3">
    <summary className="text-sm font-medium text-secondary">Broker connection settings</summary>
    <div className="mt-3 flex flex-wrap items-end gap-3">
      <label className="text-xs">Internal operator access key<br /><input className={field} type="password" autoComplete="off" value={access} onChange={e => { setAccess(e.target.value); setData(null); setStatus(null); }} /></label>
      {mode !== 'account' && <label className="text-xs flex-1">Upstox instrument keys (comma separated, max 20)<br /><input className={`${field} w-full`} value={keys} onChange={e => { setKeys(e.target.value); setData(null); }} /></label>}
      <button className={field} disabled={!access || busy} onClick={load}>{busy ? 'Loading…' : 'Fetch broker data'}</button>
      {mode !== 'stress' && <label className="text-xs"><input type="checkbox" checked={poll} onChange={e => setPoll(e.target.checked)} /> Refresh every 30 seconds</label>}
    </div>
    </details>
    {busy && <p role="status" className="text-sm text-secondary">Fetching broker data…</p>}
    {!data && !busy && <p className="text-xs text-muted">Open connection settings to request broker data. The operator key is kept in memory only.</p>}
    {mode === 'risk' && <div className="flex flex-wrap gap-3">{[
      ['Price movement %', movement, setMovement], ['Spread bps', spread, setSpread], ['Depth drop %', depthDrop, setDepthDrop],
      ['Annual volatility (0.4 = 40%)', volatility, setVolatility], ['Position loss INR', loss, setLoss], ['Gross position exposure INR', exposure, setExposure],
    ].map(([label, value, setter]) => <label className="text-xs" key={String(label)}>{String(label)}<br /><input type="number" className={`${field} w-36`} value={Number(value)} onChange={e => (setter as (v: number) => void)(Number(e.target.value))} /></label>)}</div>}
    {mode === 'risk' && <div className="flex gap-3"><button className={field} disabled={!access || busy} onClick={() => action('monitor/start', body())}>Start server monitoring</button><button className={field} disabled={!access || busy} onClick={() => action('monitor/stop', {})}>Stop monitoring</button><span className="text-xs text-muted">30-second evaluation; process-local results, no automatic trades.</span></div>}
    {mode === 'stress' && <div className="flex flex-wrap gap-3"><label className="text-xs">Parallel shock %<br /><input className={field} type="number" min={-100} max={100} value={shock} onChange={e => setShock(Number(e.target.value))} /></label><label className="text-xs">Signed quantity per entered instrument<br /><input className={field} type="number" value={quantity} onChange={e => setQuantity(e.target.value)} /></label><p className="text-xs text-muted">Explicit scenario quantities. Daily history defaults to the last 120 days; history does not imply a forecast.</p></div>}
    {mode === 'feeds' && <div className="flex flex-wrap gap-3"><select aria-label="Market depth subscription level" className={field} value={streamMode} onChange={e => setStreamMode(e.target.value)}><option value="full">Five-level stream</option><option value="full_d30">30 levels (requires entitlement)</option></select><button className={field} disabled={!access || busy} onClick={() => action('stream/start', { instrument_keys: instrumentKeys(), mode: streamMode })}>Start subscriptions</button><button className={field} disabled={!access || busy} onClick={() => action('stream/stop', {})}>Disconnect stream</button></div>}
    {error && <p role="alert" className="text-negative">{error}</p>}
    {data?.monitor && <div role="status" className="text-sm">
      Server monitoring: {data.monitor.running ? 'RUNNING' : 'STOPPED'} · Evaluation every {data.monitor.interval_seconds} seconds.
      {data.monitor.error && <span className="text-negative"> {data.monitor.error}</span>}
      {data.monitor.latest && <Table rows={data.monitor.latest.alerts || []} columns={[
        ['code', 'Latest rule'], ['instrument_key', 'Instrument'], ['value', 'Observed'], ['observed_at', 'Evaluation time'],
      ]} />}
    </div>}
    {data?.errors && Object.keys(data.errors).length > 0 && <p role="alert" className="text-warning text-xs">Partial/unavailable inputs: {JSON.stringify(data.errors)}</p>}
    {data && mode === 'account' && <>
      <p className="text-sm">Position P&amp;L: INR {fmt(data.position_pnl)} · Holdings P&amp;L: INR {fmt(data.holdings_pnl)} · Position gross exposure: INR {fmt(data.gross_position_exposure)}</p>
      <h3>Available and utilized margin (INR)</h3><Table rows={Object.entries(data.funds_and_margin || {}).filter(([,v]) => typeof v === 'object' && v !== null).map(([segment,v]) => ({ segment, ...(v as object) }))}
        columns={[[ 'segment', 'Segment' ], [ 'available_margin', 'Available' ], [ 'used_margin', 'Utilized' ], [ 'span_margin', 'SPAN' ], [ 'exposure_margin', 'Exposure margin' ]]} />
      <p className="text-sm">NSE market status: {fmt(data.market_status?.status)}</p>
      <h3>Positions</h3><Table rows={data.positions || []} columns={[['trading_symbol', 'Symbol'], ['quantity', 'Signed quantity'], ['last_price', 'LTP'], ['pnl', 'Broker P&L']]} />
      <h3>Long-term holdings</h3><Table rows={data.holdings || []} columns={[['trading_symbol', 'Symbol'], ['quantity', 'Quantity'], ['last_price', 'LTP'], ['pnl', 'Broker P&L']]} />
      <h3>Holding market movement</h3><Table rows={data.holding_quotes || []} columns={[['symbol', 'Symbol'], ['ltp', 'LTP INR'], ['movement_pct', 'Movement %'], ['timestamp', 'Source time'], ['freshness', 'Freshness']]} />
      <details><summary>Available/utilized margin and market status (provider fields)</summary><pre className="text-xs overflow-auto max-h-64">{JSON.stringify({ funds_and_margin: data.funds_and_margin, market_status: data.market_status, quote_coverage: data.quote_coverage }, null, 2)}</pre></details>
    </>}
    {data && (mode === 'liquidity' || data.liquidity) && <>
      <Table rows={(data.liquidity || data).quotes || []} columns={[['symbol', 'Symbol'], ['ltp', 'LTP INR'], ['best_bid', 'Bid'], ['best_ask', 'Ask'], ['spread_bps', 'Spread bps'], ['bid_ask_imbalance', 'Imbalance ratio'], ['book_state', 'Book'], ['freshness', 'Freshness'], ['timestamp', 'Source time']]} />
      {((data.liquidity || data).quotes || []).map((q: any) => <details key={q.instrument_key}><summary>{q.symbol}: {q.depth_levels} visible levels</summary><div className="grid md:grid-cols-2 gap-4"><Table rows={q.bids} columns={[['price', 'Bid price'], ['quantity', 'Quantity']]} /><Table rows={q.asks} columns={[['price', 'Ask price'], ['quantity', 'Quantity']]} /></div></details>)}
      <p className="text-xs text-muted">{data.transport || data.liquidity?.transport} · Missing keys: {JSON.stringify((data.liquidity || data).missing_instruments || [])}</p>
      {(data.liquidity || data).depth_changes?.length > 0 && <details><summary>Depth changes since the preceding snapshot</summary>
        <Table rows={(data.liquidity || data).depth_changes.map((r: any) => ({ ...r, comparable: r.comparable ? 'Comparable' : 'Awaiting a different source timestamp' }))}
          columns={[[ 'instrument_key', 'Instrument' ], [ 'comparable', 'Comparison' ], [ 'depth_quantity_change', 'Visible quantity change' ]]} />
      </details>}
    </>}
    {data?.alerts && <><h3>Rule evaluations</h3><Table rows={data.alerts} columns={[['code', 'Rule'], ['instrument_key', 'Instrument'], ['value', 'Observed'], ['limit', 'Threshold'], ['observed_at', 'Evaluation time']]} /><p className="text-xs text-muted">No triggered rules does not establish full coverage; inspect unavailable inputs above. Volatility uses the first entered instrument.</p></>}
    {data?.history && <>
      <p>Scenario P&amp;L: INR {fmt(data.scenario_pnl)} · India VIX: {fmt(data.india_vix?.ltp)} ({data.india_vix?.freshness || 'Unavailable'})</p>
      <Table rows={data.components || []} columns={[['instrument_key', 'Instrument'], ['quantity', 'Quantity'], ['baseline_value', 'Reference value INR'], ['stressed_value', 'Stressed INR'], ['pnl', 'P&L INR'], ['freshness', 'Quote freshness']]} />
      {Object.entries(data.history).map(([k, h]: [string, any]) => <details key={k}><summary>{k}: volatility {h.annualized_volatility == null ? 'Unavailable' : `${fmt(h.annualized_volatility * 100)}%`} · {h.return_observations} returns</summary><Table rows={h.points} columns={[['timestamp', 'Date'], ['close', 'Close INR'], ['volume', 'Volume']]} /></details>)}
      <p className="text-xs text-muted">{data.assumptions?.join(' ')}</p>
    </>}
    {(mode === 'feeds' && data || status) && <details open={mode === 'feeds'}><summary>Connection, token expiry and monitoring diagnostics</summary><pre className="text-xs overflow-auto max-h-72">{JSON.stringify(mode === 'feeds' ? data : status, null, 2)}</pre></details>}
    <p className="text-xs text-muted">Access key remains in component memory. Upstox access tokens stay on the server. Server monitor/subscriptions continue until stopped or the backend exits.</p>
  </section>;
}
