import { UpstoxBrokerPanel } from '../../../components/UpstoxBrokerPanel';
import React, { useState, useEffect } from 'react';
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
import { SpreadPanel } from './SpreadPanel';
import { OrderBookDepthPanel } from './OrderBookDepthPanel';
import { LiquidityScorePanel } from './LiquidityScorePanel';
import { LiquidationPanel } from './LiquidationPanel';
import { PortfolioLiquidityTable } from './PortfolioLiquidityTable';

interface LiquidityDashboardPageProps {
  portfolioId?: string;
  defaultInstrumentId?: string;
}

export const LiquidityDashboardPage: React.FC<LiquidityDashboardPageProps> = ({
  portfolioId,
  defaultInstrumentId,
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

  // User controls
  const [spreadUnit, setSpreadUnit] = useState<'BPS' | 'RELATIVE' | 'ABSOLUTE'>('BPS');
  const [lookbackDays, setLookbackDays] = useState<number>(30);
  const [depthLevels, setDepthLevels] = useState<number>(5);
  const [participationRate, setParticipationRate] = useState<number>(0.10);
  const [loading, setLoading] = useState<boolean>(true);
  const [loadingMicrostructure, setLoadingMicrostructure] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Ref to track microstructure section for scrolling into view
  const microstructureRef = React.useRef<HTMLDivElement>(null);

  // Fetch portfolio summary
  const fetchPortfolioLiquidity = async () => {
    const targetId = currentPortfolioId || portfolioId;
    if (!targetId) return;
    try {
      setLoading(true);
      setError(null);
      const resp = await axios.get<PortfolioLiquidityDashboardResponse>(
        `/api/v1/dashboard/liquidity/portfolio/${targetId}`
      );
      setPortfolioData(resp.data);
      // Prioritize defaultInstrumentId or currently selected instrument
      if (defaultInstrumentId) {
        setSelectedInstrumentId(defaultInstrumentId);
      } else if (selectedInstrumentId) {
        // Keep current selected ticker even if it's external / searched
      } else if (resp.data.holdings && resp.data.holdings.length > 0) {
        setSelectedInstrumentId(resp.data.holdings[0].instrument_id);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Failed to load portfolio liquidity overview.');
    } finally {
      setLoading(false);
    }
  };

  // Fetch instrument specific microstructure
  const fetchInstrumentMicrostructure = async (instId: string) => {
    try {
      setLoadingMicrostructure(true);
      // Reset current instrument states so stale metrics from previously loaded stocks do not persist on errors
      setSpreadDetail(null);
      const portParam = currentPortfolioId ? `portfolio_id=${encodeURIComponent(currentPortfolioId)}&` : '';

      const [quoteRes, spreadRes, depthRes, scoreRes, liqRes] = await Promise.allSettled([
        axios.get<CurrentQuoteItem>(`/api/v1/dashboard/liquidity/instrument/${encodeURIComponent(instId)}/quote`),
        axios.get<InstrumentSpreadDetail>(`/api/v1/dashboard/liquidity/instrument/${encodeURIComponent(instId)}/spread?lookback_days=${lookbackDays}`),
        axios.get<OrderBookDepthLadder>(`/api/v1/dashboard/liquidity/instrument/${encodeURIComponent(instId)}/depth?levels=${depthLevels}`),
        axios.get<InstrumentLiquidityScore>(`/api/v1/dashboard/liquidity/instrument/${encodeURIComponent(instId)}/score`),
        axios.get<InstrumentLiquidationProfile>(
          `/api/v1/dashboard/liquidity/instrument/${encodeURIComponent(instId)}/liquidation?${portParam}participation_rate=${participationRate}`
        ),
      ]);

      if (quoteRes.status === 'fulfilled') {
        setQuote(quoteRes.value.data);
      } else {
        console.warn('Quote fetch failed:', quoteRes.reason);
      }

      if (spreadRes.status === 'fulfilled') {
        setSpreadDetail(spreadRes.value.data);
      } else {
        console.warn('Spread fetch failed:', spreadRes.reason);
        setSpreadDetail(null);
      }

      if (depthRes.status === 'fulfilled') {
        setDepthLadder(depthRes.value.data);
      } else {
        console.warn('Depth fetch failed:', depthRes.reason);
      }

      if (scoreRes.status === 'fulfilled') {
        setLiquidityScore(scoreRes.value.data);
      } else {
        console.warn('Score fetch failed:', scoreRes.reason);
      }

      if (liqRes.status === 'fulfilled') {
        setLiquidationProfile(liqRes.value.data);
      } else {
        console.warn('Liquidation fetch failed:', liqRes.reason);
      }

      // Auto-scroll down to the microstructure panel when an instrument is chosen
      setTimeout(() => {
        microstructureRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } catch (err: any) {
      console.error('Error loading instrument details:', err);
    } finally {
      setLoadingMicrostructure(false);
    }
  };

  useEffect(() => {
    if (currentPortfolioId || portfolioId) {
      fetchPortfolioLiquidity();
    }
  }, [currentPortfolioId, portfolioId]);

  useEffect(() => {
    if (selectedInstrumentId) {
      fetchInstrumentMicrostructure(selectedInstrumentId);
    }
  }, [selectedInstrumentId, lookbackDays, depthLevels, participationRate]);

  return (
    <div className="flex min-w-0 flex-col gap-7 text-ink">
      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-4">
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

      {/* Portfolio Holdings Summary Table */}
      <PortfolioLiquidityTable
        portfolioData={portfolioData}
        selectedInstrumentId={selectedInstrumentId}
        onSelectInstrument={(id) => setSelectedInstrumentId(id)}
      />

      {/* Selected Instrument Microstructure Explorer */}
      {selectedInstrumentId && (
        <div ref={microstructureRef} className="flex flex-col gap-5 border-t border-line pt-5 scroll-mt-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-secondary flex items-center gap-2">
              Holding Microstructure:{' '}
              <span className="text-brand font-sans">
                {quote?.symbol || selectedInstrumentId}
              </span>
              {loadingMicrostructure && (
                <RefreshCw className="size-4 text-brand animate-spin" />
              )}
            </h2>
            <span className="text-xs text-muted font-sans">ID: {selectedInstrumentId}</span>
          </div>

          {/* 2x2 Microstructure Panels Grid */}
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
                quote={quote}
                spreadDetail={spreadDetail}
                spreadUnit={spreadUnit}
                onUnitChange={setSpreadUnit}
                lookbackDays={lookbackDays}
                onLookbackChange={setLookbackDays}
              />

              <OrderBookDepthPanel
                ladder={depthLadder}
                levelsCount={depthLevels}
                onLevelsCountChange={setDepthLevels}
              />

              <LiquidityScorePanel score={liquidityScore} />

              <LiquidationPanel
                liquidationProfile={liquidationProfile}
                participationRate={participationRate}
                onParticipationRateChange={setParticipationRate}
              />
            </div>
          </div>
        </div>
      )}
      <UpstoxBrokerPanel mode="liquidity" />
    </div>
  );
};
export default LiquidityDashboardPage;
