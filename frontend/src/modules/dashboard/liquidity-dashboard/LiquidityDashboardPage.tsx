import React, { useState, useEffect } from 'react';
import axios from 'axios';
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

  // Fetch available portfolios dynamically
  useEffect(() => {
    const fetchPortfolios = async () => {
      try {
        const resp = await axios.get<Array<{ portfolio_id: string; portfolio_name: string }>>('/api/v1/portfolios?limit=50');
        if (Array.isArray(resp.data) && resp.data.length > 0) {
          setAvailablePortfolios(resp.data);
          if (!currentPortfolioId) {
            setCurrentPortfolioId(resp.data[0].portfolio_id);
          }
        } else if (!currentPortfolioId) {
          setCurrentPortfolioId('PORT_DEFAULT');
        }
      } catch (e) {
        console.error('Failed to load portfolio dropdown list:', e);
        if (!currentPortfolioId) {
          setCurrentPortfolioId('PORT_DEFAULT');
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
  const [error, setError] = useState<string | null>(null);

  // Fetch portfolio summary
  const fetchPortfolioLiquidity = async () => {
    try {
      setLoading(true);
      setError(null);
      const resp = await axios.get<PortfolioLiquidityDashboardResponse>(
        `/api/v1/dashboard/liquidity/portfolio/${currentPortfolioId}`
      );
      setPortfolioData(resp.data);
      if (!selectedInstrumentId && resp.data.holdings.length > 0) {
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
      const [quoteRes, spreadRes, depthRes, scoreRes, liqRes] = await Promise.all([
        axios.get<CurrentQuoteItem>(`/api/v1/dashboard/liquidity/instrument/${instId}/quote`),
        axios.get<InstrumentSpreadDetail>(`/api/v1/dashboard/liquidity/instrument/${instId}/spread?lookback_days=${lookbackDays}`),
        axios.get<OrderBookDepthLadder>(`/api/v1/dashboard/liquidity/instrument/${instId}/depth?levels=${depthLevels}`),
        axios.get<InstrumentLiquidityScore>(`/api/v1/dashboard/liquidity/instrument/${instId}/score`),
        axios.get<InstrumentLiquidationProfile>(
          `/api/v1/dashboard/liquidity/instrument/${instId}/liquidation?portfolio_id=${currentPortfolioId}&participation_rate=${participationRate}`
        ),
      ]);

      setQuote(quoteRes.data);
      setSpreadDetail(spreadRes.data);
      setDepthLadder(depthRes.data);
      setLiquidityScore(scoreRes.data);
      setLiquidationProfile(liqRes.data);
    } catch (err: any) {
      console.error('Error loading instrument details:', err);
    }
  };

  useEffect(() => {
    fetchPortfolioLiquidity();
  }, [currentPortfolioId]);

  useEffect(() => {
    if (selectedInstrumentId) {
      fetchInstrumentMicrostructure(selectedInstrumentId);
    }
  }, [selectedInstrumentId, lookbackDays, depthLevels, participationRate]);

  return (
    <div className="flex flex-col gap-6 p-6 bg-slate-950 text-slate-100 min-h-screen">
      {/* Top Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">M13.06 — Liquidity Dashboard</h1>
          <p className="text-xs text-slate-400 mt-1">
            Institutional order-book depth, bid-ask spread analytics, composite liquidity scoring, and multi-scenario liquidation modeling.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {availablePortfolios.length > 0 ? (
            <select
              value={currentPortfolioId}
              onChange={(e) => setCurrentPortfolioId(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono"
            >
              {availablePortfolios.map((p) => (
                <option key={p.portfolio_id} value={p.portfolio_id}>
                  {p.portfolio_name ? `${p.portfolio_id} (${p.portfolio_name})` : p.portfolio_id}
                </option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              value={currentPortfolioId}
              onChange={(e) => setCurrentPortfolioId(e.target.value)}
              placeholder="Portfolio ID"
              className="bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono"
            />
          )}
          <button
            onClick={fetchPortfolioLiquidity}
            className="bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs px-4 py-1.5 rounded transition-colors shadow-sm"
          >
            Refresh Data
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-rose-950/80 border border-rose-800 text-rose-300 p-3 rounded text-xs">
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
        <div className="flex flex-col gap-5 border-t border-slate-800 pt-5">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-200">
              Holding Microstructure:{' '}
              <span className="text-cyan-400 font-mono">
                {quote?.symbol || selectedInstrumentId}
              </span>
            </h2>
            <span className="text-xs text-slate-500 font-mono">ID: {selectedInstrumentId}</span>
          </div>

          {/* 2x2 Microstructure Panels Grid */}
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
      )}
    </div>
  );
};
export default LiquidityDashboardPage;
