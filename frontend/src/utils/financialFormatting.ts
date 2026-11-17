/**
 * Financial and timestamp formatting utilities for M13.
 * Adheres strictly to M13 formatting guidelines without altering values.
 */

export function formatCurrency(
  value: number | null | undefined,
  currency: string = 'USD',
  decimalPlaces: number = 2
): string {
  if (value === null || value === undefined) {
    return 'N/A';
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: decimalPlaces,
    maximumFractionDigits: decimalPlaces,
  }).format(value);
}

export function formatPercentage(
  value: number | null | undefined,
  decimalPlaces: number = 2
): string {
  if (value === null || value === undefined) {
    return 'N/A';
  }
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(decimalPlaces)}%`;
}

export function formatUtcTimestamp(
  isoTimestamp: string | null | undefined,
  includeTimezone: boolean = true
): string {
  if (!isoTimestamp) {
    return 'N/A';
  }
  try {
    const d = new Date(isoTimestamp);
    const dateStr = d.toISOString().replace('T', ' ').substring(0, 19);
    return includeTimezone ? `${dateStr} UTC` : dateStr;
  } catch {
    return isoTimestamp;
  }
}

export function getQualityBadgeColor(status: string): string {
  switch (status.toUpperCase()) {
    case 'FRESH':
      return 'bg-emerald-100 text-emerald-800 border-emerald-300';
    case 'STALE':
    case 'DELAYED':
      return 'bg-amber-100 text-amber-800 border-amber-300';
    case 'PARTIAL':
      return 'bg-blue-100 text-blue-800 border-blue-300';
    case 'MISSING':
    case 'INVALID':
    case 'ERROR':
      return 'bg-rose-100 text-rose-800 border-rose-300';
    default:
      return 'bg-slate-100 text-slate-800 border-slate-300';
  }
}
