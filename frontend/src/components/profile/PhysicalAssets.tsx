import React, { useEffect, useState } from 'react';
import { Gem, Plus } from 'lucide-react';
import { ModalSurface } from '../ModalSurface';

const kinds = ['Gold', 'Land', 'Property', 'Other'] as const;
type Asset = { id: string; name: string; kind: typeof kinds[number]; value: string; currency: string; date: string };
const money = (value: number, currency: string) => new Intl.NumberFormat(undefined, { style: 'currency', currency, currencyDisplay: 'code' }).format(value);
function localDate() {
  const today = new Date();
  return new Date(today.getTime() - today.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}
function valid(asset: Asset) {
  return !!asset && typeof asset.id === 'string' && typeof asset.name === 'string' && !!asset.name.trim()
    && kinds.includes(asset.kind) && /^[A-Z]{3}$/.test(asset.currency) && /^\d{4}-\d{2}-\d{2}$/.test(asset.date)
    && /^\d{1,12}(\.\d{1,2})?$/.test(asset.value);
}

export function PhysicalAssets({ portfolioId, baseCurrency }: { portfolioId: string; baseCurrency: string }) {
  const prefix = 'finsight:physical:v1:' + encodeURIComponent(portfolioId) + ':';
  const [assets, setAssets] = useState<Asset[]>([]);
  const [draft, setDraft] = useState<Asset | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const [error, setError] = useState('');

  function reload() {
    try {
      const rows: Asset[] = [];
      for (const key of Object.keys(localStorage)) {
        if (!key.startsWith(prefix)) continue;
        const item: Asset = JSON.parse(localStorage.getItem(key)!);
        if (!valid(item) || key !== prefix + item.id) throw new Error();
        rows.push(item);
      }
      setAssets(rows.sort((a, b) => a.name.localeCompare(b.name)));
      setError('');
    } catch { setError('The saved asset register could not be read.'); }
  }
  useEffect(() => {
    reload();
    const sync = (e: StorageEvent) => { if (e.key === null || e.key.startsWith(prefix)) reload(); };
    window.addEventListener('storage', sync);
    return () => window.removeEventListener('storage', sync);
  }, [prefix]);

  function save(e: React.FormEvent) {
    e.preventDefault();
    if (!draft) return;
    if (!valid(draft) || draft.date > localDate()) { setError('Enter a name, a valid valuation date and an amount with up to two decimal places.'); return; }
    try {
      localStorage.setItem(prefix + draft.id, JSON.stringify({ ...draft, name: draft.name.trim() }));
      setDraft(null);
      reload();
    } catch { setError('This browser could not save the asset.'); }
  }
  function remove(id: string) {
    try { localStorage.removeItem(prefix + id); setRemoving(null); reload(); }
    catch { setError('This browser could not remove the asset.'); }
  }
  const totals = new Map<string, number>();
  assets.forEach(a => totals.set(a.currency, (totals.get(a.currency) || 0) + Math.round(Number(a.value) * 100)));
  return <section className="profile-card space-y-4" aria-labelledby="physical-heading">
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3"><span className="profile-icon"><Gem size={20} /></span>
        <div><h2 id="physical-heading" className="text-lg font-semibold">Physical assets</h2>
          <p className="text-xs text-muted">Your estimates for this portfolio, saved in this browser and tracked separately from trading NAV.</p></div></div>
      <button className="profile-action" onClick={() => { setError(''); setDraft({ id: crypto.randomUUID(), name: '', kind: 'Gold', value: '', currency: baseCurrency, date: localDate() }); }}>
        <Plus size={15} />Add asset</button>
    </header>
    {error && !draft && <p role="alert" className="text-sm text-negative">{error}</p>}
    {assets.length === 0 && !error && <p className="text-sm text-muted">No gold, land, property, or other assets recorded yet.</p>}
    {assets.map(a => <div key={a.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3 text-sm">
      <div><strong>{a.name}</strong><p className="text-xs text-muted">{a.kind} · Valued {a.date}</p></div>
      <div className="flex flex-wrap items-center gap-3"><strong>{money(Number(a.value), a.currency)}</strong>
        <button className="text-brand" aria-label={'Edit ' + a.name} onClick={() => { setError(''); setDraft({ ...a }); }}>Edit</button>
        {removing === a.id ? <><button className="text-negative" onClick={() => remove(a.id)}>Confirm removal</button><button onClick={() => setRemoving(null)}>Cancel</button></>
          : <button className="text-negative" aria-label={'Remove ' + a.name} onClick={() => setRemoving(a.id)}>Remove</button>}</div>
    </div>)}
    {totals.size > 0 && <p className="border-t border-line pt-3 text-sm font-semibold">Estimated total · {Array.from(totals, ([currency, cents]) => money(cents / 100, currency)).join(' + ')}</p>}
    {draft && <ModalSurface open onClose={() => setDraft(null)} label="Physical asset valuation">
      <form className="asset-form grid gap-4 p-6" onSubmit={save}>
        <h2 className="text-xl font-semibold">Physical asset valuation</h2>
        <label>Asset name<input required autoFocus maxLength={100} value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} /></label>
        <label>Type<select value={draft.kind} onChange={e => setDraft({ ...draft, kind: e.target.value as Asset['kind'] })}>{kinds.map(k => <option key={k}>{k}</option>)}</select></label>
        <div className="grid grid-cols-2 gap-3"><label>Estimated value<input required type="number" min="0" max="999999999999.99" step=".01" value={draft.value} onChange={e => setDraft({ ...draft, value: e.target.value })} /></label>
          <label>Currency<select value={draft.currency} onChange={e => setDraft({ ...draft, currency: e.target.value })}>{[...new Set([baseCurrency, draft.currency, 'USD', 'INR', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF'])].map(c => <option key={c}>{c}</option>)}</select></label></div>
        <label>Valuation date<input required type="date" max={localDate()} value={draft.date} onChange={e => setDraft({ ...draft, date: e.target.value })} /></label>
        {error && <p role="alert" className="text-sm text-negative">{error}</p>}
        <div className="flex justify-end gap-4"><button type="button" onClick={() => setDraft(null)}>Cancel</button><button className="profile-action" type="submit">Save asset</button></div>
      </form>
    </ModalSurface>}
  </section>;
}
