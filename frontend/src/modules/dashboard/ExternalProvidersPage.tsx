import { UpstoxBrokerPanel } from '../../components/UpstoxBrokerPanel';
import React, { useState } from 'react';
import { Activity, CheckCircle2, AlertCircle, RefreshCw, Layers, Database, Radio, TrendingUp, UserCheck, ShieldCheck } from 'lucide-react';

type Provider = { provider: string; status: string; operations: string[]; missing_configuration: string[]; modules?: string[] };

export const ExternalProvidersPage: React.FC = () => {
  const [key, setKey] = useState('');
  const [rows, setRows] = useState<Provider[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  // User Profile state
  const [userProfile, setUserProfile] = useState<any>(null);
  const [loadingProfile, setLoadingProfile] = useState(false);

  // Auto-load provider registry status and user profile on mount
  React.useEffect(() => {
    load();
    loadProfile();
  }, []);

  async function loadProfile() {
    if (!key) return;
    setLoadingProfile(true);
    try {
      const res = await fetch('/api/v1/external-data/upstox/profile', {
        method: 'POST',
        headers: { 'X-API-Key': key, 'Content-Type': 'application/json' },
        body: JSON.stringify({ parameters: {} }),
      });
      if (res.ok) {
        const json = await res.json();
        setUserProfile(json.data?.data || null);
      }
    } catch {
      // Ignore initial profile failure
    } finally {
      setLoadingProfile(false);
    }
  }

  // Live test states
  const [testSymbol, setTestSymbol] = useState('NSE_EQ|INE848E01016,NSE_INDEX|India VIX');
  const [testResult, setTestResult] = useState<any>(null);
  const [testingQuote, setTestingQuote] = useState(false);
  const [testError, setTestError] = useState('');

  async function load() {
    if (!key) return;
    setBusy(true);
    setError('');
    setRows([]);
    try {
      const response = await fetch('/api/v1/external-data/providers', {
        headers: { 'X-API-Key': key },
      });
      if (!response.ok)
        throw new Error(`Cannot load providers (HTTP ${response.status}). Check your dashboard access key.`);
      setRows(await response.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed');
    } finally {
      setBusy(false);
    }
  }

  async function testUpstoxV3() {
    setTestingQuote(true);
    setTestError('');
    setTestResult(null);
    try {
      const response = await fetch('/api/v1/external-data/upstox/quotes', {
        method: 'POST',
        headers: {
          'X-API-Key': key,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          parameters: { instrument_key: testSymbol },
        }),
      });
      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.detail?.code || errJson.detail || `HTTP ${response.status}`);
      }
      const data = await response.json();
      setTestResult(data);
    } catch (e: any) {
      setTestError(e instanceof Error ? e.message : 'Failed to query Upstox V3 endpoint');
    } finally {
      setTestingQuote(false);
    }
  }

  return (
    <div className="min-w-0 space-y-7 text-ink">
      {/* Header */}
      <div className="workspace-hero">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold text-ink ">
            Data Feeds
          </h1>
          <span className="px-2.5 py-0.5 text-xs font-semibold rounded bg-positive-soft/80 text-positive border border-positive/20 flex items-center gap-1.5">
            <Radio className="size-3 text-positive " />
            Upstox V3 · verify connection below
          </span>
        </div>
        <p className="text-sm text-muted mt-2">
          Manage provider access, check connection status, and verify market data.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs text-muted">Provider-console operator key<br />
          <input type="password" autoComplete="off" value={key} onChange={e => { setKey(e.target.value); setUserProfile(null); setRows([]); }}
            className="bg-canvas border border-line-strong rounded px-3 py-2 text-ink" />
        </label>
        <button disabled={!key || busy || loadingProfile} onClick={() => { load(); loadProfile(); }}
          className="border border-line-strong rounded px-3 py-2 text-sm">Verify provider console</button>
      </div>
      {/* Upstox Authenticated Profile Card (M05, M11, M14) */}
      {userProfile && (
        <div className="bg-surface border border-line rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-line pb-3">
            <div className="flex items-center gap-2">
              <UserCheck className="size-5 text-positive" />
              <div>
                <h2 className="text-sm font-semibold text-ink">
                  Active Upstox Broker Profile (Modules M05, M11, M14)
                </h2>
                <div className="text-[11px] text-muted">
                  UCC ID: <span className="font-sans text-positive font-semibold">{userProfile.user_id ? `${userProfile.user_id.slice(0, 2)}***${userProfile.user_id.slice(-1)}` : '***'}</span> ({userProfile.user_name ? `${userProfile.user_name.slice(0, 2)}***` : '***'}) &bull; {userProfile.email ? `${userProfile.email.slice(0, 3)}***@***` : '***@***'}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 text-[10px] font-semibold rounded bg-positive-soft text-positive border border-positive/20 flex items-center gap-1">
                <ShieldCheck className="size-3" /> Account Active
              </span>
              <span className="px-2 py-0.5 text-[10px] font-sans rounded bg-subtle text-secondary">
                {userProfile.user_type || 'individual'}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div className="bg-canvas/60 p-2.5 rounded border border-line/80">
              <span className="text-[10px] text-muted uppercase  block font-semibold mb-1">
                Enabled Exchanges
              </span>
              <div className="flex flex-wrap gap-1">
                {(userProfile.exchanges || []).map((ex: string) => (
                  <span key={ex} className="px-1.5 py-0.5 text-[10px] font-sans bg-brand-soft/80 text-brand rounded border border-brand/20">
                    {ex}
                  </span>
                ))}
              </div>
            </div>

            <div className="bg-canvas/60 p-2.5 rounded border border-line/80">
              <span className="text-[10px] text-muted uppercase  block font-semibold mb-1">
                Product Offerings
              </span>
              <div className="flex flex-wrap gap-1">
                {(userProfile.products || []).map((p: string) => (
                  <span key={p} className="px-1.5 py-0.5 text-[10px] font-sans bg-info-soft/80 text-info rounded border border-info/20">
                    {p === 'D' ? 'Delivery (D)' : p === 'I' ? 'Intraday (I)' : p === 'CO' ? 'Cover Order (CO)' : p === 'OCO' ? 'OCO / Bracket' : p}
                  </span>
                ))}
              </div>
            </div>

            <div className="bg-canvas/60 p-2.5 rounded border border-line/80">
              <span className="text-[10px] text-muted uppercase  block font-semibold mb-1">
                Permitted Order Types
              </span>
              <div className="flex flex-wrap gap-1">
                {(userProfile.order_types || []).map((ot: string) => (
                  <span key={ot} className="px-1.5 py-0.5 text-[10px] font-sans bg-subtle text-secondary rounded">
                    {ot}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Upstox V3 Live Interactive Testing Console */}
      <div className="bg-surface border border-line rounded-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="size-5 text-brand" />
            <h2 className="text-base font-semibold text-ink">
              Upstox Full Market Quotes V3 Live Console
            </h2>
          </div>
          <span className="text-[11px] bg-brand/10 text-brand px-2 py-0.5 rounded border border-blue-500/20">
            Closing Auction Session (CAS) & 500-Batch Snapshot
          </span>
        </div>
        <p className="text-xs text-muted">
          Query live V3 quotes with OHLC, Year High/Low, Indicative Equilibrium Price (IEP), and CAS eligibility.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center">
          <div className="flex-1">
            <input
              type="text"
              value={testSymbol}
              onChange={(e) => setTestSymbol(e.target.value)}
              placeholder="e.g. NSE_EQ|INE848E01016,NSE_INDEX|India VIX"
              className="w-full bg-canvas border border-line rounded-lg px-3.5 py-2 text-xs font-sans text-ink focus:outline-none focus:border-blue-500"
            />
          </div>
          <button
            onClick={testUpstoxV3}
            disabled={testingQuote || !testSymbol}
            className="flex items-center justify-center gap-2 px-4 py-2 bg-brand hover:bg-brand-hover disabled:opacity-50 text-white text-xs font-semibold rounded-lg transition"
          >
            {testingQuote ? (
              <>
                <RefreshCw className="size-3.5 animate-spin" /> Fetching Upstox V3...
              </>
            ) : (
              'Query Upstox V3 Quotes'
            )}
          </button>
        </div>

        {testError && (
          <div className="bg-negative-soft/40 border border-negative/20 p-3 rounded-lg text-negative text-xs flex items-center gap-2">
            <AlertCircle className="size-4 shrink-0" />
            <span>{testError}</span>
          </div>
        )}

        {testResult && testResult.data?.data && (
          <div className="space-y-3 pt-2">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {Object.entries(testResult.data.data).map(([sym, item]: [string, any]) => (
                <div
                  key={sym}
                  className="bg-canvas/80 border border-line rounded-lg p-3.5 space-y-2"
                >
                  <div className="flex justify-between items-start border-b border-line/80 pb-2">
                    <div>
                      <div className="font-bold text-xs text-ink">{sym}</div>
                      <div className="text-[10px] text-muted">{item.instrument_token || item.symbol}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs font-bold font-sans text-positive">
                        ₹{item.last_price != null ? item.last_price.toFixed(2) : '—'}
                      </div>
                      <div className="text-[10px] text-muted">
                        Net: {item.net_change > 0 ? `+${item.net_change}` : item.net_change ?? '0.00'}
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-[11px] font-sans">
                    <div>
                      <span className="text-muted block text-[10px]">52W High / Low</span>
                      <span className="text-secondary">
                        {item.year_high ?? '—'} / {item.year_low ?? '—'}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted block text-[10px]">CAS Eligible</span>
                      <span className={item.cas_eligible ? 'text-positive' : 'text-muted'}>
                        {item.cas_eligible ? 'YES (Live)' : 'No'}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted block text-[10px]">Indicative Eq. Price (IEP)</span>
                      <span className="text-brand font-semibold">
                        ₹{item.indicative_equilibrium_price ?? '0.00'}
                      </span>
                    </div>
                    <div>
                      <span className="text-muted block text-[10px]">Volume</span>
                      <span className="text-secondary">
                        {item.volume ? Number(item.volume).toLocaleString('en-IN') : item.ohlc?.volume ? Number(item.ohlc.volume).toLocaleString('en-IN') : '—'}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="text-[11px] text-muted font-sans">
              Retrieved at: {testResult.retrieved_at} | Provider: {testResult.provider} ({testResult.format})
            </div>
          </div>
        )}
      </div>

      {/* Module Architecture Coverage */}
      <details className="bg-surface border border-line rounded-2xl p-5 space-y-4">
        <summary className="text-sm font-semibold text-secondary">Provider capabilities and module reference</summary>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {[
            { id: 'M02', name: 'Market Data Ingestion', desc: '500-symbol batch streaming, OHLC candles & India VIX integration' },
            { id: 'M03', name: 'Market Data Quality', desc: 'Price spike validation, circuit limit adherence & volume consistency' },
            { id: 'M09', name: 'Market Microstructure', desc: 'Order Book Depth (5-level), OBI & Closing Auction Session (CAS)' },
            { id: 'M12', name: 'Risk Alerts Engine', desc: 'Intraday margin breach, sudden MTF drawdown & circuit warnings' },
            { id: 'M15.02', name: 'Portfolio Synchronization', desc: 'Real-time short-term positions, MTF leverage, overnight holdings & product conversion' },
          ].map((m) => (
            <div key={m.id} className="p-3 bg-canvas/60 border border-line rounded-lg">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[11px] font-bold px-1.5 py-0.5 rounded bg-brand-soft text-brand border border-brand/20">
                  {m.id}
                </span>
                <span className="font-semibold text-xs text-ink">{m.name}</span>
              </div>
              <p className="text-[11px] text-muted">{m.desc}</p>
            </div>
          ))}
        </div>
      </details>

      {/* Provider Status Registry */}
      <div className="bg-surface border border-line rounded-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="size-5 text-positive" />
            <h2 className="text-base font-semibold text-ink">
              Data Provider Status Registry
            </h2>
          </div>
          <button
            onClick={load}
            disabled={busy || !key}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-subtle hover:bg-hover disabled:opacity-50 text-xs font-semibold rounded text-ink transition"
          >
            <RefreshCw className={`size-3.5 ${busy ? 'animate-spin' : ''}`} />
            {busy ? 'Verifying...' : 'Refresh Status'}
          </button>
        </div>

        {error && (
          <div className="bg-negative-soft/40 border border-negative/20 p-3 rounded-lg text-negative text-xs">
            {error}
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-line text-muted">
                <th className="py-2.5 px-3">Provider</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3">Operations</th>
                <th className="py-2.5 px-3">Active Modules</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-sans">
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-4 text-center text-muted font-sans">
                    Click "Refresh Status" to load real-time configuration status.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <tr key={row.provider} className="hover:bg-subtle/50">
                    <td className="py-2.5 px-3 font-semibold text-ink font-sans flex items-center gap-1.5">
                      {row.provider === 'upstox' && <CheckCircle2 className="size-3.5 text-positive" />}
                      {row.provider}
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          row.status.includes('CONFIGURED')
                            ? 'bg-positive-soft/80 text-positive border border-positive/20'
                            : 'bg-subtle text-muted'
                        }`}
                      >
                        {row.status.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-secondary">
                      {row.operations.join(', ') || 'Unavailable'}
                    </td>
                    <td className="py-2.5 px-3 text-brand">
                      {row.modules ? row.modules.join(', ') : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
      <UpstoxBrokerPanel mode="feeds" />
    </div>
  );
};
