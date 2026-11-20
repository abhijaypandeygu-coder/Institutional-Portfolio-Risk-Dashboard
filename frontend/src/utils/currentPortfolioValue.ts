import type { PortfolioLiquidityDashboardResponse } from '../types/dashboard';

export function currentPortfolioValue(data: PortfolioLiquidityDashboardResponse | null) {
  const nav = data?.weight_basis === 'Portfolio NAV';
  const value = data == null || data.holdings.some(h => h.valuation_complete === false) ? null : nav ? Number(data.total_nav) : data.holdings.reduce((sum, h) => sum + (h.position_direction === 'SHORT' ? -1 : 1) * Number(h.position_notional), 0);
  const currency = data?.reporting_currency || 'USD';
  return {
    label: nav ? 'Current portfolio NAV' : 'Current holdings value',
    display: value !== null && Number.isFinite(value) ? new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(value) : 'Unavailable',
    note: data?.holdings.some(h => h.valuation_complete === false) ? 'Current value unavailable: a holding is missing a price or currency conversion.' : nav ? 'Latest available portfolio NAV snapshot.' : 'Net value of current positions in the portfolio base currency. Cash and liabilities are excluded; this is not full NAV.' + (data?.holdings.filter(h => h.fx_as_of).map(h => ` ${h.symbol}: FX ${h.fx_rate_to_base}, as of ${h.fx_as_of} (${h.fx_source}).`).join('') || ''),
  };
}
