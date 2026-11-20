export function money(value: unknown, currency = 'USD', compact = false): string {
  if (value === null || value === undefined || value === '' || !Number.isFinite(Number(value))) return 'Unavailable';
  try { return new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 2, ...(compact ? { notation: 'compact' as const } : {}) }).format(Number(value)); }
  catch { return `${Number(value).toLocaleString()} ${currency}`; }
}

export function duration(minutes: unknown): string {
  if (minutes === null || minutes === undefined || !Number.isFinite(Number(minutes))) return 'Unavailable';
  const m = Number(minutes);
  if (m === 0) return 'No execution needed';
  if (m < 1) return '< 1 trading minute';
  return m < 60 ? `${m.toFixed(1)} trading min` : `${(m / 60).toFixed(2)} trading hours`;
}

export function quantityImbalance(bids: Array<{quantity: unknown}>, asks: Array<{quantity: unknown}>) {
  const b = bids.reduce((s, r) => s + Number(r.quantity || 0), 0);
  const a = asks.reduce((s, r) => s + Number(r.quantity || 0), 0);
  return b + a > 0 ? (b - a) / (b + a) : null;
}

export function imbalanceLabel(value: number | null) {
  if (value === null || !Number.isFinite(value)) return 'Imbalance unavailable';
  const pct = (value * 100).toFixed(1);
  if (Math.abs(value) <= 0.05) return `Near-balanced (${pct}%)`;
  if (value > 0.20) return `Bid-heavy (${pct}%)`;
  if (value < -0.20) return `Ask-heavy (${pct}%)`;
  if (value > 0.05) return `Bid-leaning (${pct}%)`;
  return `Ask-leaning (${pct}%)`;
}

export function simulated(source?: { source_kind?: string | null; venue?: string | null } | null) {
  return !!source && (/SIMULATED|ESTIMATED/.test(source.source_kind || '') || /SIMULATED|LIVE_FEED/.test(source.venue || ''));
}

export function sourceAge(timestamp: string | null | undefined, now = Date.now()) {
  if (!timestamp) return 'Unavailable';
  const normalized = /(?:Z|[+-]\d\d:\d\d)$/.test(timestamp) ? timestamp : `${timestamp}Z`;
  const ms = now - Date.parse(normalized);
  if (!Number.isFinite(ms)) return 'Unavailable';
  if (ms < 0) return 'Clock mismatch';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)} s`;
  if (ms < 3600000) return `${Math.floor(ms / 60000)} min`;
  return `${(ms / 3600000).toFixed(1)} hours`;
}

export function tierDistribution(holdings: Array<{liquidity_bucket: string; weight_pct: unknown}>) {
  const tiers = ['TIER_1_HIGH', 'TIER_2_MODERATE', 'TIER_3_LOW', 'TIER_4_ILLIQUID', 'UNCLASSIFIED'];
  return tiers.map(tier => ({ tier, weight: holdings.reduce((sum, h) => {
    const bucket = tiers.includes(h.liquidity_bucket) ? h.liquidity_bucket : 'UNCLASSIFIED';
    const w = Number(h.weight_pct);
    return sum + (tier === bucket && Number.isFinite(w) ? w : 0);
  }, 0) }));
}

export interface DepthPoint { timestamp: string; bid: number; ask: number }
export interface MarketContext { exchange: string; timezone: string; regular_hours: string; session_minutes: number; session_status: string; calendar_basis: string; calendar_id?: string | null }

export function mergeDepthPoints(points: DepthPoint[], next: DepthPoint[]) {
  const map = new Map<string, DepthPoint>();
  for (const p of [...points, ...next]) if (Number.isFinite(Date.parse(p.timestamp)) && Number.isFinite(p.bid) && Number.isFinite(p.ask)) map.set(p.timestamp, p);
  return [...map.values()].sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp)).slice(-500);
}
