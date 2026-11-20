import { UpstoxBrokerPanel } from '../../../components/UpstoxBrokerPanel';
import React, { useState, useEffect, useRef } from 'react';
import { DepthPoint, MarketContext, mergeDepthPoints, simulated } from '../../../utils/liquidityAnalytics';
import { LiquidityDistribution, DepthHistoryChart, MarketDataStatus } from './LiquidityInsights';
import axios from 'axios';
import { RefreshCw, FolderOpen, Layers } from 'lucide-react';
import {
  PortfolioLiquidityDashboardResponse,
  CurrentQuoteItem,
  InstrumentSpreadDetail,
  OrderBookDepthLadder,
  InstrumentLiquidityScore,
  InstrumentLiquidationProfile,
} from '../../../types/dashboard';
import { useMarketDataStream } from '../../../hooks/useMarketDataStream';
import { SpreadPanel } from './SpreadPanel';
import { OrderBookDepthPanel } from './OrderBookDepthPanel';
import { LiquidityScorePanel } from './LiquidityScorePanel';
import { LiquidationPanel } from './LiquidationPanel';
import { PortfolioLiquidityTable } from './PortfolioLiquidityTable';

interface LiquidityDashboardPageProps {
  portfolioId?: string;
  defaultInstrumentId?: string;
  onOpenOrderModal?: () => void;
  revision?: number;
  onPositionsChanged?: () => void;
  onPortfolioUpdated?: (data: PortfolioLiquidityDashboardResponse) => void;
}

export const LiquidityDashboardPage: React.FC<LiquidityDashboardPageProps> = ({
  portfolioId,
  defaultInstrumentId,
  onOpenOrderModal,
  onPortfolioUpdated,
  revision = 0,
  onPositionsChanged,
}) => {
  const [currentPortfolioId, setCurrentPortfolioId] = useState<string>(portfolioId || '');
  const [availablePortfolios, setAvailablePortfolios] = useState<Array<{ portfolio_id: string; portfolio_name: string }>>([]);
  const [selectedInstrumentId, setSelectedInstrumentId] = useState<string | null>(defaultInstrumentId || null);

  useEffect(() => {
    if (defaultInstrumentId) {
      setSelectedInstrumentId(defaultInstrumentId);
    }
  }, [defaultInstrumentId]);

  // Fetch available portfolios dynamically
  useEffect(() => {
    if (portfolioId) {
      setCurrentPortfolioId(portfolioId);
    }
  }, [portfolioId]);

  useEffect(() => {
    const fetchPortfolios = async () => {
      try {
        const resp = await axios.get<Array<{ portfolio_id: string; portfolio_name: string }>>('/api/v1/portfolios?limit=50');
        if (Array.isArray(resp.data) && resp.data.length > 0) {
          setAvailablePortfolios(resp.data);
          if (!currentPortfolioId) {
            setCurrentPortfolioId(portfolioId || resp.data[0].portfolio_id);
          }
        } else if (!currentPortfolioId) {
          setCurrentPortfolioId(portfolioId || 'PORT_DEFAULT');
        }
      } catch (e) {
        console.error('Failed to load portfolio dropdown list:', e);
        if (!currentPortfolioId) {
          setCurrentPortfolioId(portfolioId || 'PORT_DEFAULT');
        }
      }
    };
    fetchPortfolios();
  }, []);
  
  // Dashboard state
  const [portfolioData, setPortfolioData] = useState<PortfolioLiquidityDashboardResponse | null>(null);
  const [quote, setQuote] = useState<CurrentQuoteItem | null>(null);
  const [spreadDetail, setSpreadDetail] = useState<InstrumentSpreadDetail | null>(null);
  const [depthLadder, setDepthLadder] = useState<OrderBookDepthLadder | null>(null);
  const [liquidityScore, setLiquidityScore] = useState<InstrumentLiquidityScore | null>(null);
  const [liquidationProfile, setLiquidationProfile] = useState<InstrumentLiquidationProfile | null>(null);

  const [marketContext, setMarketContext] = useState<MarketContext | null>(null);
  const [depthHistory, setDepthHistory] = useState<{ scope: string; points: DepthPoint[] }>({ scope: '', points: [] });
  const portfolioRequest = useRef<AbortController | null>(null);
  const instrumentRequest = useRef<AbortController | null>(null);

  // User controls
  const [spreadUnit, setSpreadUnit] = useState<'BPS' | 'RELATIVE' | 'ABSOLUTE'>('BPS');
  const [lookbackDays, setLookbackDays] = useState<number>(30);
  const [positionRevision, setPositionRevision] = useState(0);
  const [depthLevels, setDepthLevels] = useState<number>(5);
  const [participationRate, setParticipationRate] = useState<number>(0.10);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingMicrostructure, setLoadingMicrostructure] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Ref to track microstructure section for scrolling into view
  const microstructureRef = React.useRef<HTMLDivElement>(null);

  // Live WebSocket market data streaming hook
  const {
    isConnected: isWsConnected,
    streamingQuote,
    streamingDepth,
  } = useMarketDataStream({
    instrumentId: selectedInstrumentId,
    symbol: quote?.symbol,
    levelsCount: depthLevels,
    enabled: !!selectedInstrumentId,
  });

  // Effective live or snapshot data
  const selectedQuote = quote?.instrument_id === selectedInstrumentId ? quote : null;
  const streamQuoteMatches = streamingQuote && (streamingQuote.instrument_id === selectedInstrumentId || streamingQuote.symbol === selectedQuote?.symbol);
  const streamDepthMatches = streamingDepth && (streamingDepth.instrument_id === selectedInstrumentId || streamingDepth.symbol === selectedQuote?.symbol);
  const effectiveQuote = streamQuoteMatches && !simulated(streamingQuote) ? streamingQuote : selectedQuote;
  const effectiveDepthLadder = streamDepthMatches && !simulated(streamingDepth) ? streamingDepth : depthLadder?.instrument_id === selectedInstrumentId ? depthLadder : null;
  const isProviderStreaming = !!(streamDepthMatches && !simulated(streamingDepth));
  const historyScope = `${currentPortfolioId}:${selectedInstrumentId}:${depthLevels}`;
  const isHolding = portfolioData?.holdings.some(h => h.instrument_id === selectedInstrumentId || h.symbol === effectiveQuote?.symbol);

  useEffect(() => {
    const ladder = effectiveDepthLadder;
    const stamp = ladder?.source_timestamp || ladder?.snapshot_timestamp;
    if (!ladder || !stamp || !ladder.bids.length || !ladder.asks.length) return;
    const bidNotional = ladder.bids.slice(0, depthLevels).reduce((sum, l) => sum + Number(l.notional), 0);
    const askNotional = ladder.asks.slice(0, depthLevels).reduce((sum, l) => sum + Number(l.notional), 0);
    const point = { timestamp: stamp, bid: bidNotional, ask: askNotional };
    setDepthHistory(old => ({ scope: historyScope, points: mergeDepthPoints(old.scope === historyScope ? old.points : [], [point]) }));
  }, [effectiveDepthLadder, historyScope, depthLevels]);

  const inspectInstrument = (id: string) => {
    setSelectedInstrumentId(id);
    requestAnimationFrame(() => {
      const heading = document.getElementById('microstructure-heading');
      heading?.focus({ preventScroll: true });
      heading?.scrollIntoView({ block: 'start' });
    });
  };

  // Bounded, abortable requests prevent previous instrument responses overwriting selection.
  const fetchPortfolioLiquidity = async () => {
    const targetId = currentPortfolioId || portfolioId;
    if (!targetId) return;
    portfolioRequest.current?.abort();
    const controller = new AbortController();
    portfolioRequest.current = controller;
    setLoading(true); setError(null);
    try {
      const response = await axios.get<PortfolioLiquidityDashboardResponse>(`/api/v1/dashboard/liquidity/portfolio/${encodeURIComponent(targetId)}`, { signal: controller.signal, timeout: 30000, params: { participation_rate: participationRate } });
      if (controller.signal.aborted) return;
      setPortfolioData(response.data);
      onPortfolioUpdated?.(response.data);
      if (!selectedInstrumentId && response.data.holdings.length) setSelectedInstrumentId(response.data.holdings[0].instrument_id);
    } catch (err: any) {
      if (!controller.signal.aborted) setError(err?.response?.data?.detail || 'Portfolio liquidity could not be refreshed. Retry when the provider is available.');
    } finally { if (!controller.signal.aborted) setLoading(false); }
  };

  useEffect(() => {
    setPortfolioData(null);
    fetchPortfolioLiquidity();
    return () => portfolioRequest.current?.abort();
  }, [currentPortfolioId, portfolioId, participationRate, revision]);

  useEffect(() => {
    if (!selectedInstrumentId) return;
    instrumentRequest.current?.abort();
    const controller = new AbortController(); instrumentRequest.current = controller;
    setQuote(null); setSpreadDetail(null); setDepthLadder(null); setLiquidityScore(null); setLiquidationProfile(null); setMarketContext(null);
    setDepthHistory({ scope: historyScope, points: [] });
    setLoadingMicrostructure(true);
    const root = `/api/v1/dashboard/liquidity/instrument/${encodeURIComponent(selectedInstrumentId)}`;
    const options = { signal: controller.signal, timeout: 25000 };
    const apply = <T,>(setter: (value: T) => void) => (response: { data: T }) => { if (!controller.signal.aborted) setter(response.data); };
    const requests = [
      axios.get<CurrentQuoteItem>(`${root}/quote`, options).then(apply(setQuote)),
      axios.get<InstrumentSpreadDetail>(`${root}/spread?lookback_days=${lookbackDays}`, options).then(apply(setSpreadDetail)),
      axios.get<OrderBookDepthLadder>(`${root}/depth?levels=${depthLevels}`, options).then(apply(setDepthLadder)),
      axios.get<InstrumentLiquidityScore>(`${root}/score`, options).then(apply(setLiquidityScore)),
      axios.get<InstrumentLiquidationProfile>(`${root}/liquidation`, { ...options, params: { portfolio_id: currentPortfolioId || undefined, participation_rate: participationRate } }).then(apply(setLiquidationProfile)),
      axios.get<MarketContext>(`${root}/market-context`, options).then(apply(setMarketContext)),
      axios.get<{ points: DepthPoint[] }>(`${root}/depth-history?levels=${depthLevels}`, options).then(response => { if (!controller.signal.aborted) setDepthHistory(old => ({ scope: historyScope, points: mergeDepthPoints(old.scope === historyScope ? old.points : [], response.data.points) })); }),
    ];
    Promise.allSettled(requests).then(results => {
      if (!controller.signal.aborted) {
        setLoadingMicrostructure(false);
        if (results.some(r => r.status === 'rejected')) setError('Some instrument data is unavailable. Completed panels remain visible; missing data is not estimated silently.');
      }
    });
    const refreshContext = setInterval(() => { axios.get<MarketContext>(`${root}/market-context`, options).then(apply(setMarketContext)).catch(() => {}); }, 60000);
    return () => { controller.abort(); clearInterval(refreshContext); };
  }, [selectedInstrumentId, currentPortfolioId, lookbackDays, depthLevels, participationRate, positionRevision, revision]);

  return (
    <div className="flex min-w-0 flex-col gap-7 text-ink">
      {/* Top Banner */}
      <div className="workspace-hero flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-semibold text-ink ">Liquidity Analytics</h1>
          </div>
          <p className="text-xs text-muted mt-1">
            Understand market depth, trading costs, and the liquidity of your holdings.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Active Portfolio Badge (Synced with Header) */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface border border-line text-xs">
            <FolderOpen className="size-3.5 text-muted" />
            <span className="text-muted">Portfolio:</span>
            <span className="font-medium text-secondary">
              {availablePortfolios.find((p) => p.portfolio_id === currentPortfolioId)?.portfolio_name || currentPortfolioId}
            </span>
          </div>

          {/* Refresh Button */}
          <button
            type="button"
            onClick={fetchPortfolioLiquidity}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface hover:bg-subtle border border-line hover:border-line-strong text-xs font-medium text-secondary hover:text-ink transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`size-3.5 ${loading ? 'animate-spin text-positive' : 'text-muted'}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-negative-soft/80 border border-negative/20 text-negative p-3 rounded text-xs">
          {error}
        </div>
      )}

      <LiquidityDistribution data={portfolioData} />
      {/* Portfolio Holdings Summary Table */}
      <PortfolioLiquidityTable
        portfolioData={portfolioData}
        selectedInstrumentId={selectedInstrumentId}
        onSelectInstrument={inspectInstrument}
        onOpenOrderModal={onOpenOrderModal}
        onPositionChange={() => { setPositionRevision(n => n + 1); if (onPositionsChanged) onPositionsChanged(); else void fetchPortfolioLiquidity(); }}
      />

      {/* Selected Instrument Microstructure Explorer */}
      {selectedInstrumentId && (
        <div ref={microstructureRef} className="flex flex-col gap-5 border-t border-line pt-5 scroll-mt-6">
          <div className="flex items-center justify-between">
            <h2 id="microstructure-heading" tabIndex={-1} className="text-lg font-bold text-secondary flex flex-wrap items-center gap-2">
              Instrument Microstructure:{' '}
              <span className="text-brand font-sans">
                {effectiveQuote?.symbol || selectedInstrumentId}
              </span>
              {loadingMicrostructure && (
                <RefreshCw className="size-4 text-brand animate-spin" />
              )}
            </h2>
            <span className="text-xs text-muted">{portfolioData ? isHolding ? 'Portfolio holding' : 'External instrument · not held in this portfolio' : 'Portfolio membership not yet verified'}</span>
          </div>

          <MarketDataStatus quote={effectiveQuote} ladder={effectiveDepthLadder} connected={isWsConnected} streaming={isProviderStreaming} context={marketContext} />
          <DepthHistoryChart points={depthHistory.scope === historyScope ? depthHistory.points : []} levels={depthLevels} currency={effectiveDepthLadder?.currency || effectiveQuote?.currency || 'USD'} />
          {/* Microstructure Panels */}
          <div className="relative">
            {loadingMicrostructure && !quote && (
              <div className="absolute inset-0 bg-canvas/70 z-10 flex items-center justify-center rounded-xl  min-h-[300px]">
                <div className="flex flex-col items-center gap-2 text-brand">
                  <RefreshCw className="size-6 animate-spin" />
                  <span className="text-xs font-sans">Loading {selectedInstrumentId} microstructure...</span>
                </div>
              </div>
            )}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <SpreadPanel
                quote={effectiveQuote}
                spreadDetail={spreadDetail}
                spreadUnit={spreadUnit}
                onUnitChange={setSpreadUnit}
                lookbackDays={lookbackDays}
                onLookbackChange={setLookbackDays}
              />

              <OrderBookDepthPanel
                ladder={effectiveDepthLadder}
                levelsCount={depthLevels}
                onLevelsCountChange={setDepthLevels}
                isStreaming={isWsConnected && isProviderStreaming}
                marketContext={marketContext}
              />

              <LiquidityScorePanel score={liquidityScore} currency={effectiveQuote?.currency} />

              <div className="lg:col-span-2 min-w-0"><LiquidationPanel
                portfolioData={portfolioData}
                liquidationProfile={liquidationProfile}
                participationRate={participationRate}
                onParticipationRateChange={setParticipationRate}
              /></div>
            </div>
          </div>
        </div>
      )}
      <UpstoxBrokerPanel mode="liquidity" />
    </div>
  );
};
export default LiquidityDashboardPage;
