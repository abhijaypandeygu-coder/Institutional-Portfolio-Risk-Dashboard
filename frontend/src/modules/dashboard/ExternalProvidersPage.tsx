import React, { useState } from 'react';

type Provider = { provider: string; status: string; operations: string[]; missing_configuration: string[] };

export const ExternalProvidersPage: React.FC = () => {
  const [key, setKey] = useState('');
  const [rows, setRows] = useState<Provider[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function load() {
    setBusy(true); setError(''); setRows([]);
    try {
      const response = await fetch('/api/v1/external-data/providers', { headers: { 'X-API-Key': key } });
      if (!response.ok) throw new Error(`Cannot load providers (HTTP ${response.status}). Use your dashboard access key.`);
      setRows(await response.json());
    } catch (e) { setError(e instanceof Error ? e.message : 'Request failed'); }
    finally { setBusy(false); }
  }
  return <section style={{ color: '#f1f5f9', maxWidth: 1100 }}>
    <h1>External data providers</h1>
    <p>Free-only configuration. Configured does not mean live verified. Market data can be delayed.</p>
    <label>Dashboard access key (kept only in memory)<br />
      <input type="password" autoComplete="off" value={key} onChange={e => setKey(e.target.value)}
        style={{ padding: 10, marginTop: 8, width: 320 }} />
    </label>{' '}
    <button disabled={busy || !key} onClick={load}>{busy ? 'Checking…' : 'Load provider status'}</button>
    {error && <p role="alert">{error}</p>}
    <table style={{ width: '100%', marginTop: 24, textAlign: 'left', borderCollapse: 'collapse' }}>
      <thead><tr>{['Provider', 'Status', 'Available operations', 'Configuration needed'].map(t => <th key={t} style={{ padding: 10 }}>{t}</th>)}</tr></thead>
      <tbody>{rows.map(row => <tr key={row.provider} style={{ borderTop: '1px solid #475569' }}>
        <td style={{ padding: 10 }}>{row.provider}</td><td>{row.status.replace(/_/g, ' ').toLowerCase()}</td>
        <td>{row.operations.join(', ') || 'Unavailable'}</td><td>{row.missing_configuration.join(', ') || '—'}</td>
      </tr>)}</tbody>
    </table>
    <p>External provider keys belong in the server .env file. Do not enter them here.</p>
  </section>;
};
