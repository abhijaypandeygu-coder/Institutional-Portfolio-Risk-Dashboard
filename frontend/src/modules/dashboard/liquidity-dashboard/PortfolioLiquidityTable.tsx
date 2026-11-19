import React, { useState, useMemo } from 'react';
import { money, duration } from '../../../utils/liquidityAnalytics';
import { PortfolioLiquidityDashboardResponse, HoldingLiquiditySummary } from '../../../types/dashboard';
import { ModalSurface } from '../../../components/ModalSurface';
import { Plus, Trash2, Globe, TrendingUp, RefreshCw } from 'lucide-react';

interface PortfolioLiquidityTableProps {
  portfolioData: PortfolioLiquidityDashboardResponse | null;
  selectedInstrumentId: string | null;
  onSelectInstrument: (instrumentId: string) => void;
  onOpenOrderModal?: () => void;
  onPositionChange?: () => void;
}

type SortField = 'symbol' | 'position_shares' | 'weight_pct' | 'spread_bps' | 'composite_score' | 'full_liquidation_cost_bps' | 'full_liquidation_days';
type SortOrder = 'asc' | 'desc';

export const PortfolioLiquidityTable: React.FC<PortfolioLiquidityTableProps> = ({
  portfolioData,
  selectedInstrumentId,
  onSelectInstrument,
  onOpenOrderModal,
  onPositionChange,
}) => {
  const [marketFilter, setMarketFilter] = useState<'ALL' | 'INDIAN_MARKET' | 'US_MARKET' | 'OTHER_GLOBAL'>('ALL');
  const [searchTerm, setSearchTerm] = useState('');
  const [tierFilter, setTierFilter] = useState<'ALL' | 'TIER_1_HIGH' | 'TIER_2_MODERATE' | 'TIER_3_LOW' | 'TIER_4_ILLIQUID'>('ALL');
  const [directionFilter, setDirectionFilter] = useState<'ALL' | 'LONG' | 'SHORT' | 'FLAT'>('ALL');
  const [sortField, setSortField] = useState<SortField>('weight_pct');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [isDeleting, setIsDeleting] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const [pendingRemoval, setPendingRemoval] = useState<HoldingLiquiditySummary | null>(null);

  // Helper to determine market region for any stock
  const getHoldingMarketRegion = (h: HoldingLiquiditySummary): 'INDIAN_MARKET' | 'US_MARKET' | 'OTHER_GLOBAL' => {
    const s = (h.symbol || '').toUpperCase();
    if (s.endsWith('.NS') || s.endsWith('.BO') || ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'SBIN', 'ITC'].includes(s)) {
      return 'INDIAN_MARKET';
    }
    if (h.market_region && h.market_region !== 'US_MARKET') return h.market_region;
    if (['AAPL', 'MSFT', 'NVDA', 'AMZN', 'TSLA', 'GOOGL', 'GOOG', 'META', 'JPM', 'SPY', 'QQQ', 'VOO', 'IWM'].includes(s)) {
      return 'US_MARKET';
    }
    return 'OTHER_GLOBAL';
  };

  const handleRemoveStock = async (h: HoldingLiquiditySummary) => {
    if (!portfolioData?.portfolio_id || isDeleting) return;
    setIsDeleting(h.instrument_id);
    setDeleteError(null);
    try {
      const res = await fetch(`/api/v1/dashboard/liquidity/portfolio/${encodeURIComponent(portfolioData.portfolio_id)}/instrument/${encodeURIComponent(h.instrument_id)}/remove`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(typeof err.detail === 'string' ? err.detail : `Failed to remove stock (${res.status})`);
      }
      setPendingRemoval(null);
      await onPositionChange?.();
    } catch (err: any) {
      setDeleteError(err.message || 'Error removing position');
    } finally {
      setIsDeleting(null);
    }
  };

  const getBucketBadge = (bucket: string) => {
    switch (bucket) {
      case 'TIER_1_HIGH':
        return <span className="px-1.5 py-0.5 text-[10px] rounded bg-positive-soft text-positive border border-positive/20">TIER 1</span>;
      case 'TIER_2_MODERATE':
        return <span className="px-1.5 py-0.5 text-[10px] rounded bg-brand-soft text-brand border border-brand/20">TIER 2</span>;
      case 'TIER_3_LOW':
        return <span className="px-1.5 py-0.5 text-[10px] rounded bg-warning-soft text-warning border border-warning/20">TIER 3</span>;
      case 'TIER_4_ILLIQUID':
        return <span className="px-1.5 py-0.5 text-[10px] rounded bg-negative-soft text-negative border border-negative/20">TIER 4</span>;
      default:
        return <span className="px-1.5 py-0.5 text-[10px] rounded bg-subtle text-secondary">{bucket}</span>;
    }
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  const filteredAndSortedHoldings = useMemo(() => {
    if (!portfolioData || !portfolioData.holdings) return [];

    return portfolioData.holdings
      .filter((h: HoldingLiquiditySummary) => {
        // Market region filter
        if (marketFilter !== 'ALL') {
          const region = getHoldingMarketRegion(h);
          if (region !== marketFilter) return false;
        }

        // Search filter
        if (searchTerm.trim() !== '') {
          const term = searchTerm.toLowerCase();
          const matchSym = (h.symbol || '').toLowerCase().includes(term);
          const matchInst = (h.instrument_id || '').toLowerCase().includes(term);
          if (!matchSym && !matchInst) return false;
        }

        // Tier filter
        if (tierFilter !== 'ALL' && h.liquidity_bucket !== tierFilter) {
          return false;
        }

        // Direction filter
        if (directionFilter !== 'ALL' && h.position_direction !== directionFilter) {
          return false;
        }

        return true;
      })
      .sort((a: HoldingLiquiditySummary, b: HoldingLiquiditySummary) => {
        let valA: any = a[sortField];
        let valB: any = b[sortField];

        if (sortField === 'symbol') {
          valA = a.symbol || a.instrument_id;
          valB = b.symbol || b.instrument_id;
          return sortOrder === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
        }

        const numA = valA !== null && valA !== undefined ? Number(valA) : -999999;
        const numB = valB !== null && valB !== undefined ? Number(valB) : -999999;
        return sortOrder === 'asc' ? numA - numB : numB - numA;
      });
  }, [portfolioData, marketFilter, searchTerm, tierFilter, directionFilter, sortField, sortOrder]);

  if (!portfolioData) {
    return (
      <div className="bg-surface border border-line rounded-lg p-5 text-muted text-sm">
        No portfolio liquidity data loaded.
      </div>
    );
  }

  const renderSortIndicator = (field: SortField) => {
    if (sortField !== field) return null;
    return <span className="ml-1 text-[10px] text-brand">{sortOrder === 'asc' ? '▲' : '▼'}</span>;
  };

  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-lg flex flex-col gap-4">
      {/* KPI Overview Grid with improved definitions and methodology subtitles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-canvas p-3 rounded border border-line flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-secondary">Weighted Liquidity Score</span>
              <span className="text-[10px] text-brand font-sans">M09.03</span>
            </div>
            <div className="text-2xl font-bold text-brand font-sans mt-1">
              {Number(portfolioData.weighted_composite_score).toFixed(1)} <span className="text-xs font-normal text-muted">/ 100</span>
            </div>
          </div>
          <span className="text-[11px] text-muted font-sans mt-1">
            Value-weighted · {portfolioData.weight_basis || 'Weight basis unavailable'}
          </span>
        </div>

        <div className="bg-canvas p-3 rounded border border-line flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-secondary">Weighted Spread</span>
              <span className="text-[10px] text-positive font-sans">QUOTED</span>
            </div>
            <div className="text-2xl font-bold text-positive font-sans mt-1">
              {Number(portfolioData.weighted_spread_bps).toFixed(2)} <span className="text-xs font-normal text-muted">bps</span>
            </div>
          </div>
          <span className="text-[11px] text-muted font-sans mt-1">
            Value-weighted quoted spread
          </span>
        </div>

        <div className="bg-canvas p-3 rounded border border-line flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-secondary">Full Liquidation Cost</span>
              <span className="text-[10px] text-negative font-sans">{portfolioData.reporting_currency || 'Currency unavailable'}</span>
            </div>
            <div className="text-2xl font-bold text-negative font-sans mt-1">
              {portfolioData.costs_complete === false ? 'Unavailable / incomplete' : money(portfolioData.total_full_liquidation_cost_usd, portfolioData.reporting_currency)}
            </div>
          </div>
          <div className="flex flex-col text-[11px] text-muted font-sans mt-1">
            <span>{Number(portfolioData.portfolio_liquidation_cost_bps).toFixed(1)} bps of {portfolioData.weight_basis === 'Portfolio NAV' ? 'NAV' : 'absolute position value'} (Portfolio Agg.)</span>
            <span className="text-[10px] text-secondary">Participation model @ {(Number(portfolioData.participation_rate ?? .1)*100).toFixed(0)}% daily ADV</span>
          </div>
        </div>

        <div className="bg-canvas p-3 rounded border border-line flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-secondary">Maximum execution time</span>
              <span className="text-[10px] text-warning font-sans">{(Number(portfolioData.participation_rate ?? .1)*100).toFixed(0)}% ADV</span>
            </div>
            <div className="text-2xl font-bold text-warning font-sans mt-1">
              {portfolioData.costs_complete === false ? 'Unavailable' : duration(portfolioData.max_duration_minutes)}
            </div>
          </div>
          <span className="text-[11px] text-muted font-sans mt-1">
            Low Liq Capital: {Number(portfolioData.low_liquidity_capital_pct).toFixed(1)}% · {portfolioData.calendar_description || 'Session assumptions unavailable'}
          </span>
        </div>
      </div>

      <ModalSurface open={pendingRemoval !== null} onClose={() => { if (!isDeleting) setPendingRemoval(null); }} label="Remove local portfolio position">
        <div className="p-5 space-y-4">
          <h2 className="text-lg font-semibold">Remove {pendingRemoval?.symbol}?</h2>
          <p className="text-sm text-secondary">Remove this position from the selected local portfolio. Position history is retained. No broker order will be sent.</p>
          {deleteError && <p role="alert" className="text-sm text-negative">{deleteError}</p>}
          <div className="flex justify-end gap-3">
            <button type="button" disabled={!!isDeleting} onClick={() => setPendingRemoval(null)} className="rounded-lg border border-line px-4 py-2">Cancel</button>
            <button type="button" disabled={!!isDeleting} onClick={() => pendingRemoval && handleRemoveStock(pendingRemoval)} className="rounded-lg bg-negative text-white px-4 py-2">{isDeleting ? 'Removing…' : 'Remove local position'}</button>
          </div>
        </div>
      </ModalSurface>
      {/* Market Region Sections / Filter Tabs & Add Stock Action */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
        <div className="flex items-center gap-1.5 p-1 bg-canvas border border-line rounded-lg">
          <button
            type="button"
            onClick={() => setMarketFilter('ALL')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
              marketFilter === 'ALL'
                ? 'bg-brand text-white shadow-sm'
                : 'text-muted hover:text-secondary hover:bg-subtle/60'
            }`}
          >
            All Markets ({portfolioData.holdings.length})
          </button>
          <button
            type="button"
            onClick={() => setMarketFilter('INDIAN_MARKET')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md flex items-center gap-1.5 transition-all ${
              marketFilter === 'INDIAN_MARKET'
                ? 'bg-orange-600 text-white shadow-sm'
                : 'text-muted hover:text-secondary hover:bg-subtle/60'
            }`}
          >
            <span className="size-2 rounded-full bg-orange-400" />
            Indian Market (NSE/BSE) ({portfolioData.holdings.filter(h => getHoldingMarketRegion(h) === 'INDIAN_MARKET').length})
          </button>
          <button
            type="button"
            onClick={() => setMarketFilter('US_MARKET')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md flex items-center gap-1.5 transition-all ${
              marketFilter === 'US_MARKET'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-muted hover:text-secondary hover:bg-subtle/60'
            }`}
          >
            <span className="size-2 rounded-full bg-blue-400" />
            US Market (NYSE/NASDAQ) ({portfolioData.holdings.filter(h => getHoldingMarketRegion(h) === 'US_MARKET').length})
          </button>
          <button
            type="button"
            onClick={() => setMarketFilter('OTHER_GLOBAL')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md flex items-center gap-1.5 transition-all ${
              marketFilter === 'OTHER_GLOBAL'
                ? 'bg-emerald-600 text-white shadow-sm'
                : 'text-muted hover:text-secondary hover:bg-subtle/60'
            }`}
          >
            <span className="size-2 rounded-full bg-emerald-400" />
            Other Global ({portfolioData.holdings.filter(h => getHoldingMarketRegion(h) === 'OTHER_GLOBAL').length})
          </button>
        </div>

        {onOpenOrderModal && (
          <button
            type="button"
            onClick={onOpenOrderModal}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-brand hover:bg-brand-hover text-white text-xs font-bold rounded-lg shadow-sm transition-colors"
          >
            <Plus className="size-3.5 stroke-[2.5]" />
            <span>Add Stock / Trade Allocation</span>
          </button>
        )}
      </div>

      {deleteError && (
        <div className="bg-rose-500/10 border border-rose-500/20 text-negative text-xs p-2.5 rounded-lg">
          {deleteError}
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-canvas/60 p-2.5 rounded border border-line">
        <div className="flex flex-wrap items-center gap-3">
          {/* Search Input */}
          <div className="relative">
            <input
              type="text"
              placeholder="Search symbol..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="bg-surface border border-line-strong text-secondary text-xs rounded px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500 w-36 sm:w-44"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                className="absolute right-2 top-1.5 text-xs text-muted hover:text-secondary"
              >
                ✕
              </button>
            )}
          </div>

          {/* Tier Filter */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-muted">Tier:</span>
            <select
              value={tierFilter}
              onChange={(e) => setTierFilter(e.target.value as any)}
              className="bg-surface border border-line-strong text-secondary text-xs rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="ALL">All Tiers</option>
              <option value="TIER_1_HIGH">Tier 1 (High)</option>
              <option value="TIER_2_MODERATE">Tier 2 (Moderate)</option>
              <option value="TIER_3_LOW">Tier 3 (Low)</option>
              <option value="TIER_4_ILLIQUID">Tier 4 (Illiquid)</option>
            </select>
          </div>

          {/* Direction Filter */}
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-muted">Side:</span>
            <select
              value={directionFilter}
              onChange={(e) => setDirectionFilter(e.target.value as any)}
              className="bg-surface border border-line-strong text-secondary text-xs rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="ALL">All Sides</option>
              <option value="LONG">Long</option>
              <option value="SHORT">Short</option>
              <option value="FLAT">Flat</option>
            </select>
          </div>
        </div>

        <div className="text-xs text-muted font-sans">
          Showing <span className="text-secondary font-semibold">{filteredAndSortedHoldings.length}</span> of {portfolioData.holdings.length} positions
        </div>
      </div>

      {/* Holdings Table */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold text-secondary">Portfolio Holdings Liquidity Breakdown</span>
        <div className="overflow-x-auto min-w-full scrollbar-thin scrollbar-thumb-slate-700">
          <table className="w-full min-w-[760px] text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-line text-muted uppercase text-[11px]">
                <th onClick={() => handleSort('symbol')} className="py-2 px-3 cursor-pointer hover:text-secondary whitespace-nowrap">
                  Symbol {renderSortIndicator('symbol')}
                </th>
                <th onClick={() => handleSort('position_shares')} className="py-2 px-3 cursor-pointer hover:text-secondary whitespace-nowrap">
                  Position {renderSortIndicator('position_shares')}
                </th>
                <th onClick={() => handleSort('weight_pct')} className="py-2 px-3 cursor-pointer hover:text-secondary whitespace-nowrap">
                  Weight {renderSortIndicator('weight_pct')}
                </th>
                <th onClick={() => handleSort('spread_bps')} className="py-2 px-3 cursor-pointer hover:text-secondary whitespace-nowrap">
                  Spread (bps) {renderSortIndicator('spread_bps')}
                </th>
                <th onClick={() => handleSort('composite_score')} className="py-2 px-3 cursor-pointer hover:text-secondary whitespace-nowrap">
                  Score {renderSortIndicator('composite_score')}
                </th>
                <th className="py-2 px-3 whitespace-nowrap">Tier</th>
                <th className="py-2 px-3 whitespace-nowrap">Imbalance</th>
                <th onClick={() => handleSort('full_liquidation_cost_bps')} className="py-2 px-3 cursor-pointer hover:text-secondary whitespace-nowrap min-w-[110px]">
                  100% Liq Cost {renderSortIndicator('full_liquidation_cost_bps')}
                </th>
                <th onClick={() => handleSort('full_liquidation_days')} className="py-2 px-3 cursor-pointer hover:text-secondary whitespace-nowrap">
                  Trading time {renderSortIndicator('full_liquidation_days')}
                </th>
                <th className="py-2 px-3 text-center whitespace-nowrap">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-sans">
              {filteredAndSortedHoldings.map((h: HoldingLiquiditySummary) => {
                const isSelected = h.instrument_id === selectedInstrumentId;
                const region = getHoldingMarketRegion(h);
                const shares = Number(h.position_shares);
                const weight = Number(h.weight_pct);
                const spread = h.spread_bps !== null && h.spread_bps !== undefined ? Number(h.spread_bps) : null;
                const compScore = h.composite_score !== null && h.composite_score !== undefined ? Number(h.composite_score) : null;
                const depthImb = h.depth_imbalance !== null && h.depth_imbalance !== undefined ? Number(h.depth_imbalance) : null;
                const liqCost = h.full_liquidation_cost_bps !== null && h.full_liquidation_cost_bps !== undefined ? Number(h.full_liquidation_cost_bps) : null;
                const liqDays = h.full_liquidation_days !== null && h.full_liquidation_days !== undefined ? Number(h.full_liquidation_days) : null;

                return (
                  <tr
                    key={h.instrument_id}
                    onClick={() => onSelectInstrument(h.instrument_id)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-brand-soft/30 border-l-2 border-blue-500 font-semibold'
                        : 'hover:bg-subtle/40'
                    }`}
                  >
                    <td className="py-2.5 px-3 text-ink font-bold whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <button type="button" aria-label={`Inspect ${h.symbol} liquidity`} onClick={event => { event.stopPropagation(); onSelectInstrument(h.instrument_id); }} className="text-brand underline decoration-brand/30 underline-offset-4">
                          {h.symbol}
                        </button>
                        <span className={`text-[9px] px-1.5 py-0.2 rounded font-sans uppercase font-bold border ${
                          region === 'INDIAN_MARKET' 
                            ? 'bg-orange-500/10 text-orange-400 border-orange-500/20' 
                            : region === 'US_MARKET'
                            ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                            : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        }`}>
                          {region === 'INDIAN_MARKET' ? 'NSE/BSE' : region === 'US_MARKET' ? 'US' : 'GLOBAL'}
                        </span>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-secondary whitespace-nowrap">
                      <span className={h.position_direction === 'LONG' ? 'text-positive' : (h.position_direction === 'SHORT' ? 'text-negative' : 'text-muted')}>
                        {h.position_direction}
                      </span>{' '}
                      ({shares.toLocaleString()})
                    </td>
                    <td className="py-2.5 px-3 text-secondary whitespace-nowrap">{weight.toFixed(2)}%</td>
                    <td className="py-2.5 px-3 text-brand whitespace-nowrap">
                      {spread !== null ? `${spread.toFixed(2)}` : '—'}
                    </td>
                    <td className="py-2.5 px-3 text-secondary whitespace-nowrap">
                      {compScore !== null ? compScore.toFixed(1) : '—'}
                    </td>
                    <td className="py-2.5 px-3 whitespace-nowrap">{getBucketBadge(h.liquidity_bucket)}</td>
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      {depthImb !== null ? (
                        <span className={depthImb > 0 ? 'text-positive' : 'text-negative'}>
                          {(depthImb * 100).toFixed(1)}%
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-negative font-semibold whitespace-nowrap">
                      {liqCost !== null ? `${liqCost.toFixed(1)} bps` : '—'}
                    </td>
                    <td className="py-2.5 px-3 text-secondary whitespace-nowrap">
                      {h.full_liquidation_minutes != null ? duration(Number(h.full_liquidation_minutes)) : liqDays !== null ? `${liqDays.toFixed(2)} sessions` : '—'}
                    </td>
                    <td className="py-2.5 px-3 text-center whitespace-nowrap">
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); setDeleteError(null); setPendingRemoval(h); }}
                        disabled={isDeleting !== null}
                        aria-label={`Remove ${h.symbol} from local portfolio`}
                        title={`Remove ${h.symbol} from local portfolio`}
                        className="p-1 rounded text-muted hover:text-negative hover:bg-rose-500/10 transition-colors disabled:opacity-50"
                      >
                        {isDeleting === h.instrument_id ? (
                          <RefreshCw className="size-3.5 animate-spin text-negative" />
                        ) : (
                          <Trash2 className="size-3.5" />
                        )}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
