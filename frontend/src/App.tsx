import { useLiveRefresh, useLiveUpdates } from './hooks/useLiveRefresh';
import { AppShell, type DashboardView } from './components/AppShell';
import { PersonalProfile } from './components/profile/PersonalProfile';
import { PhysicalAssets } from './components/profile/PhysicalAssets';
import { ExecutivePortfolioLayout } from './components/ExecutivePortfolioLayout';
import { cn } from './utils/cn';
import { ModalSurface } from './components/ModalSurface';
import { UpstoxBrokerPanel } from './components/UpstoxBrokerPanel';
import React, { useState, useEffect, useRef } from 'react';
import {
  TrendingUp,
  Wallet,
  Layers,
  Activity,
  Search,
  Bell,
  Calendar,
  Share2,
  Plus,
  ChevronDown,
  ArrowUpRight,
  ArrowDownRight,
  ShieldCheck,
  FolderOpen,
  Command,
  SlidersHorizontal,
  Flame,
  FileSpreadsheet,
  X
} from 'lucide-react';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ExternalProvidersPage } from './modules/dashboard/ExternalProvidersPage';
import { PortfolioOverviewPage } from './modules/dashboard/portfolio-overview/PortfolioOverviewPage';
import { AlertsDashboardPage } from './modules/dashboard/alerts-dashboard/AlertsDashboardPage';
import { LiquidityDashboardPage } from './modules/dashboard/liquidity-dashboard/LiquidityDashboardPage';
import { StressTestingDashboardPage } from './modules/dashboard/stress-dashboard/StressTestingDashboardPage';
import { ExportModal } from './components/ExportModal';
import { OrderAllocationModal } from './components/OrderAllocationModal';

export const App: React.FC = () => {
  const { refreshAll } = useLiveUpdates();
  const [portfolioRevision, setPortfolioRevision] = useState(0);
  const positionChannel = useRef<BroadcastChannel | null>(null);
  const [activeTab, setActiveTab] = useState<DashboardView>('overview');
  const [timeRange, setTimeRange] = useState<'1D' | '1W' | '1M' | '3M' | '6M' | '1Y' | 'All'>('1Y');
  const [selectedPortfolio, setSelectedPortfolio] = useState<string>('PORT_API_RISK_484889');
  const [selectedTicker, setSelectedTicker] = useState<string | null>('AAPL');
  const [portfolioList, setPortfolioList] = useState<Array<{ portfolio_id: string; portfolio_name: string; base_currency?: string }>>([]);
  const [showEngineDetails, setShowEngineDetails] = useState<boolean>(false);
  const [overviewData, setOverviewData] = useState<any>(null);
  const [liquidityData, setLiquidityData] = useState<any>(null);
  const [liveMarketWatch, setLiveMarketWatch] = useState<Array<{ symbol: string; name: string; price: string; change: string; up: boolean }>>([]);
  const [recentTransactions, setRecentTransactions] = useState<Array<{ symbol: string; title: string; subtitle: string; amount: string; isNegative: boolean }>>([]);
  const [upcomingEvents, setUpcomingEvents] = useState<Array<{ title: string; date: string; tag: string; color: string }>>([]);


  // Date range dropdown & modals state
  const selectedDateRange = overviewData?.total_nav?.as_of ? `Valued ${new Date(overviewData.total_nav.as_of).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}` : 'Valuation date unavailable';
  const [isExportOpen, setIsExportOpen] = useState<boolean>(false);
  const [isOrderModalOpen, setIsOrderModalOpen] = useState<boolean>(false);

  // Command / Quick-Finder palette state
  const [isSearchOpen, setIsSearchOpen] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [liveSearchResults, setLiveSearchResults] = useState<Array<{ symbol: string; name: string; sector: string; exchange: string }>>([]);
  const [isSearchingLive, setIsSearchingLive] = useState<boolean>(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Debounced live market ticker search via yfinance
  useEffect(() => {
    if (!searchQuery.trim() || searchQuery.trim().length < 1) {
      setLiveSearchResults([]);
      setIsSearchingLive(false);
      return;
    }

    const timer = setTimeout(() => {
      setIsSearchingLive(true);
      fetch(`/api/v1/dashboard/liquidity/search-tickers?q=${encodeURIComponent(searchQuery.trim())}&limit=8`)
        .then((res) => (res.ok ? res.json() : []))
        .then((data) => {
          if (Array.isArray(data)) {
            setLiveSearchResults(data);
          }
        })
        .catch(() => setLiveSearchResults([]))
        .finally(() => setIsSearchingLive(false));
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Keyboard shortcut listener (Cmd+K / Ctrl+K / / key)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsSearchOpen((prev) => !prev);
      } else if (e.key === 'Escape' && isSearchOpen) {
        setIsSearchOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isSearchOpen]);

  useEffect(() => {
    if (isSearchOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
    } else {
      setSearchQuery('');
    }
  }, [isSearchOpen]);

  useEffect(() => {
    fetch('/api/v1/portfolios?limit=50')
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setPortfolioList(data);
          const hasRisk = data.some((p: any) => p.portfolio_id === 'PORT_API_RISK_484889');
          if (hasRisk) {
            setSelectedPortfolio('PORT_API_RISK_484889');
          } else {
            setSelectedPortfolio(data[0].portfolio_id);
          }
        }
      })
      .catch(() => { });
  }, []);

  useEffect(() => {
    setOverviewData(null); setLiquidityData(null); setRecentTransactions([]);
    if (typeof BroadcastChannel === 'undefined') return;
    const channel = new BroadcastChannel('finsight-position-changes');
    positionChannel.current = channel;
    channel.onmessage = event => {
      if (event.data === selectedPortfolio) setPortfolioRevision(n => n + 1);
    };
    return () => { positionChannel.current = null; channel.close(); };
  }, [selectedPortfolio]);

  useEffect(() => {
    if (!selectedPortfolio) return;
    const controller = new AbortController();
    // Fetch real position transactions from authoritative position ledger
    fetch(`/api/v1/positions/portfolios/${selectedPortfolio}`, { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : []))
      .then(async (positions) => {
        if (!Array.isArray(positions) || positions.length === 0) {
          setRecentTransactions([]);
          return;
        }
        const eventPromises = positions.slice(0, 8).map((p: any) =>
          fetch(`/api/v1/positions/${p.position_id}/events`, { signal: controller.signal })
            .then((res) => (res.ok ? res.json() : []))
            .catch(() => [])
        );
        const eventArrays = await Promise.all(eventPromises);
        const allEvents = eventArrays.flat();

        allEvents.sort((a, b) => {
          const tA = new Date(a.recorded_at || a.effective_timestamp || 0).getTime();
          const tB = new Date(b.recorded_at || b.effective_timestamp || 0).getTime();
          return tB - tA;
        });

        const formatted = allEvents.slice(0, 5).map((ev: any) => {
          const qty = Number(ev.signed_quantity_delta) || 0;
          const sym = ev.instrument_id || 'ASSET';
          const evType = (ev.event_type || 'TRADE').replace(/_/g, ' ');
          const dateStr = ev.recorded_at ? ev.recorded_at.slice(0, 10) : 'Recent';
          return {
            symbol: sym,
            title: `${sym} • ${evType}`,
            subtitle: `${Math.abs(qty).toLocaleString()} Shares • ${dateStr}`,
            amount: `${qty >= 0 ? '+' : ''}${qty.toLocaleString()} shs`,
            isNegative: qty < 0,
          };
        });
        if (!controller.signal.aborted) setRecentTransactions(formatted);
      })
      .catch(() => { if (!controller.signal.aborted) setRecentTransactions([]); });
    return () => controller.abort();
  }, [selectedPortfolio, portfolioRevision]);

  const overviewRefresh = useLiveRefresh(`overview:${selectedPortfolio}:${portfolioRevision}`, async signal => {
    if (!selectedPortfolio) return;
    const response = await fetch(`/api/v1/dashboard/portfolios/${encodeURIComponent(selectedPortfolio)}/overview`, { signal });
    if (!response.ok) throw new Error(`Portfolio valuation refresh failed (HTTP ${response.status}). Previous values are retained.`);
    const data = await response.json(); if (!signal.aborted) setOverviewData(data);
  });
  const holdingsRefresh = useLiveRefresh(`holdings:${selectedPortfolio}:${portfolioRevision}`, async signal => {
    if (!selectedPortfolio) return;
    const response = await fetch(`/api/v1/dashboard/liquidity/portfolio/${encodeURIComponent(selectedPortfolio)}`, { signal });
    if (!response.ok) throw new Error('Holdings refresh failed. Previous values are retained.');
    const data = await response.json(); if (!signal.aborted) setLiquidityData(data);
  }, 120000);
  const heldSymbols = [...new Set<string>((liquidityData?.portfolio_id === selectedPortfolio ? liquidityData.holdings : []).filter((h: any) => Number(h.position_shares) !== 0).map((h: any) => h.symbol))].sort().join(',');
  const marketRefresh = useLiveRefresh(`market-watch:${selectedPortfolio}:${heldSymbols}`, async signal => {
    if (!heldSymbols) { setLiveMarketWatch([]); return; }
    const response = await fetch(`/api/v1/dashboard/liquidity/market-watch?symbols=${encodeURIComponent(heldSymbols)}`, { signal });
    if (!response.ok) throw new Error('Market quote refresh failed. Previous quotes are retained.');
    const data = await response.json(); if (!Array.isArray(data)) throw new Error('Invalid market quote response.');
    if (!signal.aborted) setLiveMarketWatch(data);
  });

  // Fetch authoritative events (breaches, risk alerts) from history/events
  useEffect(() => {
    fetch('/api/v1/dashboard/history/events?page_size=6')
      .then((res) => (res.ok ? res.json() : { events: [] }))
      .then((data) => {
        if (Array.isArray(data.events) && data.events.length > 0) {
          const colors: Record<string, string> = {
            CRITICAL: 'text-negative bg-negative-soft/60 border-negative/20',
            HIGH: 'text-warning bg-warning-soft/60 border-warning/20',
            MEDIUM: 'text-brand bg-brand-soft/60 border-brand/20',
            LOW: 'text-muted bg-subtle border-line-strong/40',
          };
          const mapped = data.events.slice(0, 4).map((e: any) => ({
            title: e.event_title || 'Governance Event',
            date: e.occurrence_time ? e.occurrence_time.slice(0, 10) : 'Active',
            tag: (e.severity || e.event_category || 'RISK').toUpperCase(),
            color: colors[e.severity] || 'text-positive bg-positive-soft/60 border-positive/20',
          }));
          setUpcomingEvents(mapped);
        }
      })
      .catch(() => { });
  }, [selectedPortfolio]);


  const currentHoldings = liquidityData?.portfolio_id === selectedPortfolio ? liquidityData : null;
  const physicalAssets = <PhysicalAssets key={selectedPortfolio} portfolioId={selectedPortfolio}
    baseCurrency={currentHoldings?.reporting_currency || portfolioList.find(p => p.portfolio_id === selectedPortfolio)?.base_currency || 'USD'} />;
  const positionsChanged = (portfolioId = selectedPortfolio) => {
    if (portfolioId === selectedPortfolio) { setPortfolioRevision(n => n + 1); refreshAll(); }
    positionChannel.current?.postMessage(portfolioId);
  };
  return (
    <>
      <AppShell view={activeTab} onView={setActiveTab} portfolio={selectedPortfolio} onPortfolio={setSelectedPortfolio}
        portfolios={portfolioList} onSearch={() => setIsSearchOpen(true)}>
        {activeTab !== 'overview' && (
          <div className="min-w-0">
            <ErrorBoundary fallbackTitle="Module View Error">
              {activeTab === 'profile' && <PersonalProfile key={selectedPortfolio} portfolioId={selectedPortfolio}
                name={portfolioList.find(p => p.portfolio_id === selectedPortfolio)?.portfolio_name}
                data={currentHoldings} error={holdingsRefresh.error} revision={portfolioRevision}>{physicalAssets}</PersonalProfile>}
              {activeTab === 'alerts' && <AlertsDashboardPage portfolioId={selectedPortfolio} />}
              {activeTab === 'liquidity' && (
                <LiquidityDashboardPage
                  portfolioId={selectedPortfolio}
                  defaultInstrumentId={selectedTicker || undefined}
                  onOpenOrderModal={() => setIsOrderModalOpen(true)}
                  onPortfolioUpdated={data => { if (data.portfolio_id === selectedPortfolio) setLiquidityData(data); }}
                  revision={portfolioRevision}
                  onPositionsChanged={positionsChanged}
                />
              )}
              {activeTab === 'stress' && <StressTestingDashboardPage portfolioId={selectedPortfolio} />}
              {activeTab === 'providers' && <ExternalProvidersPage />}
            </ErrorBoundary>
          </div>
        )}

        {activeTab === 'overview' && (
          <>
            {/* Top Bar: Title & Actions */}
            <div className="workspace-hero flex flex-wrap items-center justify-between gap-4">
              <div>
                <h1 className="text-3xl font-semibold text-ink text-balance flex flex-wrap items-center gap-2.5">
                  Overview

                </h1>
                <p className="text-sm text-muted text-pretty mt-2">
                  A clear view of your portfolio, performance, and risk.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2.5">
                <button
                  type="button"
                  onClick={() => setShowEngineDetails(!showEngineDetails)}
                  className={`px-3 py-1.5 rounded-xl border text-xs font-semibold transition-colors ${showEngineDetails
                      ? 'bg-brand text-white border-brand'
                      : 'bg-surface border-line text-secondary hover:border-line-strong'
                    }`}
                >
                  {showEngineDetails ? 'Hide Deep Risk Metrics' : 'Detailed Risk Breakdown'}
                </button>

                <span className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs text-muted"><Calendar className="size-3.5" />{selectedDateRange}</span>

                {/* Export Button */}
                <button
                  type="button"
                  onClick={() => setIsExportOpen(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-surface border border-line text-xs font-medium text-secondary hover:border-line-strong hover:text-ink transition-colors"
                >
                  <Share2 className="size-3.5 text-muted" />
                  <span>Export</span>
                </button>

                {/* New Order / Allocation Button */}
                <button
                  type="button"
                  onClick={() => setIsOrderModalOpen(true)}
                  className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-brand text-xs font-semibold text-white hover:bg-brand-hover transition-colors"
                >
                  <Plus className="size-3.5 stroke-[3]" />
                  <span>New Order / Allocation</span>
                </button>
              </div>
            </div>

            {(overviewRefresh.error || marketRefresh.error || holdingsRefresh.error) && <p role="status" className="rounded-lg bg-warning-soft p-3 text-xs text-warning">{overviewRefresh.error || marketRefresh.error || holdingsRefresh.error} Data may be stale.</p>}
            <ExecutivePortfolioLayout overview={overviewData} holdings={liquidityData?.portfolio_id === selectedPortfolio ? liquidityData.holdings : []} quotes={liveMarketWatch}
              currentValuation={liquidityData?.portfolio_id === selectedPortfolio ? liquidityData : null} portfolioId={selectedPortfolio} holdingsPending={liquidityData === null} range={timeRange} onRange={setTimeRange}
              onInstrument={symbol => { setSelectedTicker(symbol); setActiveTab('liquidity'); }} />

            {physicalAssets}
            {/* Section 3: Recent Transactions | Top Holdings | Upcoming Events */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="bg-surface border border-line rounded-2xl p-6 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-bold text-ink">Recent Transactions</h3>
                    <button
                      type="button"
                      onClick={() => setIsOrderModalOpen(true)}
                      className="text-xs font-semibold text-positive hover:text-positive"
                    >
                      + Order
                    </button>
                  </div>

                  <div className="space-y-3">
                    {recentTransactions.length > 0 ? (
                      recentTransactions.map((tx, idx) => (
                        <div key={idx} className="flex items-center justify-between py-1.5 border-b border-line last:border-none">
                          <div>
                            <div className="text-xs font-semibold text-secondary">{tx.title}</div>
                            <div className="text-xs text-muted">{tx.subtitle}</div>
                          </div>
                          <span className={`text-xs font-bold font-sans tabular-nums ${tx.isNegative ? 'text-negative' : 'text-positive'}`}>
                            {tx.amount}
                          </span>
                        </div>
                      ))
                    ) : (
                      <div className="py-4 text-center text-xs text-muted italic">
                        No transactions recorded for this portfolio yet. Click '+ Order' to book a trade.
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <div className="bg-surface border border-line rounded-2xl p-6 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-bold text-ink">Risk & Governance Events</h3>
                    <button
                      type="button"
                      onClick={() => setActiveTab('alerts')}
                      className="text-xs font-semibold text-positive hover:text-positive"
                    >
                      Alerts Feed
                    </button>
                  </div>

                  <div className="space-y-3">
                    {upcomingEvents.length > 0 ? (
                      upcomingEvents.map((evt, idx) => (
                        <div key={idx} className="p-3 rounded-xl bg-canvas border border-line flex items-start gap-3">
                          <div className="p-2 rounded-lg bg-surface text-secondary">
                            <Calendar className="size-4 text-positive" />
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-semibold text-secondary">{evt.title}</span>
                              <span className={`text-xs font-bold px-1.5 py-0.5 rounded border ${evt.color}`}>
                                {evt.tag}
                              </span>
                            </div>
                            <span className="text-xs text-muted block mt-1">{evt.date}</span>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="py-4 text-center text-xs text-muted italic">
                        No active risk or limit breach events detected.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <UpstoxBrokerPanel mode="account" />

            {/* Section 4: Authoritative Risk Breakdown */}
            {showEngineDetails && (
              <div className="bg-surface border border-line rounded-2xl p-6 shadow-sm">
                <div className="flex items-center justify-between border-b border-line pb-4 mb-4">
                  <div>
                    <h3 className="text-base font-bold text-ink flex items-center gap-2">
                      <ShieldCheck className="size-4 text-positive" />
                      Authoritative Risk Engine — Deep Breakdown
                    </h3>
                    <p className="text-xs text-muted">
                      M05.03 Valuation, M06 Exposure Limits, and M07 Market Risk Metrics
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowEngineDetails(false)}
                    className="text-xs text-muted hover:text-secondary bg-canvas px-3 py-1 rounded-lg border border-line"
                  >
                    Close Breakdown
                  </button>
                </div>
                <PortfolioOverviewPage portfolioId={selectedPortfolio} />
              </div>
            )}
          </>
        )}
      </AppShell>

      {/* 3. Command / Quick-Finder Palette Modal */}
      {isSearchOpen && (
        <ModalSurface open={isSearchOpen} onClose={() => setIsSearchOpen(false)} label="Search portfolios and views">
          <div
            className="w-full min-w-0 bg-surface overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Search Header */}
            <div className="flex items-center gap-3 px-4 py-3.5 border-b border-line bg-canvas/50">
              <Search className="size-4 text-muted shrink-0" />
              <input
                ref={searchInputRef}
                aria-label="Search portfolios, views and tickers"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search portfolios, views, tickers (e.g. 'AAPL', 'stress', 'risk')..."
                className="w-full bg-transparent text-sm text-ink placeholder:text-muted focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setIsSearchOpen(false)}
                aria-label="Close search"
                className="p-1 rounded-md text-muted hover:text-secondary hover:bg-subtle"
              >
                <X className="size-4" />
              </button>
            </div>

            {/* Quick Suggestions & Filtered Results */}
            <div className="max-h-96 overflow-y-auto p-2 space-y-4">
              {/* Navigation Views */}
              <div>
                <div className="px-2.5 py-1 text-[11px] font-semibold text-muted uppercase ">
                  Dashboard Views
                </div>
                <div className="space-y-0.5 mt-1">
                  {[
                    { id: 'overview', label: 'Executive Dashboard', desc: 'Summary NAV, P&L, holdings and market events', icon: Activity },
                    { id: 'profile', label: 'Personal profile', desc: 'Company performance and physical assets', icon: Wallet },
                    { id: 'alerts', label: 'Risk Alerts & Breaches', desc: 'Active limit violations, warnings and utilization thresholds', icon: Flame },
                    { id: 'liquidity', label: 'Liquidity Analytics', desc: 'Holdings depth, liquidation cost, bid-ask spread', icon: SlidersHorizontal },
                    { id: 'stress', label: 'Stress Testing & Monte Carlo', desc: 'Historical stress shocks, tail quantiles, loss attribution', icon: Layers },
                    { id: 'providers', label: 'External Data Feeds', desc: 'Market data providers, latency and connection status', icon: FileSpreadsheet },
                  ]
                    .filter((item) =>
                      !searchQuery ||
                      item.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
                      item.desc.toLowerCase().includes(searchQuery.toLowerCase())
                    )
                    .map((item) => {
                      const Icon = item.icon;
                      return (
                        <button
                          key={item.id}
                          type="button"
                          onClick={() => {
                            setActiveTab(item.id as any);
                            setIsSearchOpen(false);
                          }}
                          className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-left hover:bg-subtle/70 transition-colors group"
                        >
                          <div className="p-1.5 rounded-lg bg-subtle text-muted group-hover:text-positive group-hover:bg-brand-hover/10 transition-colors">
                            <Icon className="size-4" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-xs font-medium text-secondary group-hover:text-ink">
                              {item.label}
                            </div>
                            <div className="text-[11px] text-muted truncate">
                              {item.desc}
                            </div>
                          </div>
                          <kbd className="text-[10px] text-muted font-sans">Jump</kbd>
                        </button>
                      );
                    })}
                </div>
              </div>

              {/* Portfolios List */}
              {portfolioList.length > 0 && (
                <div>
                  <div className="px-2.5 py-1 text-[11px] font-semibold text-muted uppercase ">
                    Portfolios & Funds
                  </div>
                  <div className="space-y-0.5 mt-1">
                    {portfolioList
                      .filter((p) =>
                        !searchQuery ||
                        p.portfolio_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                        p.portfolio_id.toLowerCase().includes(searchQuery.toLowerCase())
                      )
                      .slice(0, 5)
                      .map((p) => (
                        <button
                          key={p.portfolio_id}
                          type="button"
                          onClick={() => {
                            setSelectedPortfolio(p.portfolio_id);
                            setIsSearchOpen(false);
                          }}
                          className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-left transition-colors ${selectedPortfolio === p.portfolio_id
                              ? 'bg-subtle/90 text-ink'
                              : 'hover:bg-subtle/50 text-secondary'
                            }`}
                        >
                          <div className="flex items-center gap-2.5">
                            <FolderOpen className="size-3.5 text-muted" />
                            <span className="text-xs font-medium">{p.portfolio_name}</span>
                          </div>
                          <span className="text-[10px] font-sans text-muted">{p.portfolio_id}</span>
                        </button>
                      ))}
                  </div>
                </div>
              )}

              {/* Live Market Stocks & Tickers (via yfinance) */}
              <div>
                <div className="flex items-center justify-between px-2.5 py-1 text-[11px] font-semibold text-muted uppercase ">
                  <span>Global Equities & Tickers</span>
                  {isSearchingLive && (
                    <span className="text-[10px] text-positive font-sans ">Searching live market...</span>
                  )}
                </div>
                <div className="space-y-0.5 mt-1">
                  {/* If user typed a query, display live market search results */}
                  {searchQuery.trim().length > 0 ? (
                    liveSearchResults.length > 0 ? (
                      liveSearchResults.map((t) => (
                        <button
                          key={t.symbol}
                          type="button"
                          onClick={() => {
                            setSelectedTicker(t.symbol);
                            setActiveTab('liquidity');
                            setIsSearchOpen(false);
                          }}
                          className="w-full flex items-center justify-between px-3 py-2 rounded-xl text-left hover:bg-subtle/70 transition-colors group"
                        >
                          <div className="flex items-center gap-2.5">
                            <span className="text-xs font-bold font-sans text-positive">{t.symbol}</span>
                            <span className="text-xs text-secondary truncate max-w-[260px]">{t.name}</span>
                          </div>
                          <div className="flex items-center gap-2 text-[10px] text-muted font-sans">
                            <span>{t.sector}</span>
                            <span className="px-1.5 py-0.5 rounded bg-subtle text-muted border border-line-strong/50">{t.exchange}</span>
                          </div>
                        </button>
                      ))
                    ) : (
                      !isSearchingLive && (
                        <div className="px-3 py-2 text-xs text-muted italic">
                          No matching live tickers found for "{searchQuery}".
                        </div>
                      )
                    )
                  ) : (
                    /* Default popular benchmark assets when search box is empty */
                    [
                      { symbol: 'AAPL', name: 'Apple Inc.', sector: 'Information Technology' },
                      { symbol: 'MSFT', name: 'Microsoft Corp.', sector: 'Software & Cloud' },
                      { symbol: 'AMZN', name: 'Amazon.com', sector: 'Consumer Discretionary' },
                      { symbol: 'NVDA', name: 'NVIDIA Corporation', sector: 'Semiconductors' },
                      { symbol: 'VOO', name: 'Vanguard S&P 500 ETF', sector: 'Broad Index ETF' },
                      { symbol: 'TSLA', name: 'Tesla, Inc.', sector: 'Automotive / Energy' },
                      { symbol: 'GOOGL', name: 'Alphabet Inc.', sector: 'Communication Services' },
                    ].map((t) => (
                      <button
                        key={t.symbol}
                        type="button"
                        onClick={() => {
                          setSelectedTicker(t.symbol);
                          setActiveTab('liquidity');
                          setIsSearchOpen(false);
                        }}
                        className="w-full flex items-center justify-between px-3 py-2 rounded-xl text-left hover:bg-subtle/70 transition-colors group"
                      >
                        <div className="flex items-center gap-2.5">
                          <span className="text-xs font-bold font-sans text-secondary group-hover:text-positive">{t.symbol}</span>
                          <span className="text-xs text-muted">{t.name}</span>
                        </div>
                        <span className="text-[10px] text-muted">{t.sector}</span>
                      </button>
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* Footer tips */}
            <div className="px-4 py-2 border-t border-line bg-canvas/60 flex items-center justify-between text-[11px] text-muted">
              <span>Press <kbd className="px-1 py-0.5 bg-subtle rounded font-sans text-muted">Esc</kbd> to close</span>
              <span>Navigate with click or search query</span>
            </div>
          </div>
        </ModalSurface>
      )}

      {/* Export Institutional Dataset Modal */}
      <ExportModal
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        selectedPortfolio={selectedPortfolio}
        portfolioList={portfolioList}
        dateRangeLabel={selectedDateRange}
      />

      {/* New Order / Allocation & Pre-Trade Risk Modal */}
      <OrderAllocationModal
        isOpen={isOrderModalOpen}
        onClose={() => setIsOrderModalOpen(false)}
        selectedPortfolio={selectedPortfolio}
        portfolioList={portfolioList}
        onOrderSuccess={positionsChanged}
      />
    </>
  );
};
