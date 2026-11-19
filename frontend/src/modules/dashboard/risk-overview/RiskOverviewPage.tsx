import React, { useState, useEffect } from 'react';
import { RiskOverviewResponse, RiskHistoryResponse } from '../../../types/dashboard';
import { VaRCard } from './components/VaRCard';
import { ExpectedShortfallCard } from './components/ExpectedShortfallCard';
import { VolatilityCard } from './components/VolatilityCard';
import { DrawdownCard } from './components/DrawdownCard';
import { VaRESComparison } from './components/VaRESComparison';
import { DrawdownChart } from './components/DrawdownChart';
import { RiskDataStatus } from './components/RiskDataStatus';

interface RiskOverviewPageProps {
  portfolioId: string;
}

export const RiskOverviewPage: React.FC<RiskOverviewPageProps> = ({ portfolioId }) => {
  const [data, setData] = useState<RiskOverviewResponse | null>(null);
  const [historyData, setHistoryData] = useState<RiskHistoryResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Configuration controls
  const [confidenceLevel, setConfidenceLevel] = useState<number>(0.99);
  const [horizonDays, setHorizonDays] = useState<number>(1);
  const [varMethodology, setVarMethodology] = useState<string>('HISTORICAL_SIMULATION');
  const [volatilityLookback, setVolatilityLookback] = useState<number>(60);
  const [drawdownPeriod, setDrawdownPeriod] = useState<string>('1_year');

  const fetchRiskOverview = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const query = new URLSearchParams({
        confidence_level: confidenceLevel.toString(),
        horizon_days: horizonDays.toString(),
        var_methodology: varMethodology,
        volatility_lookback: volatilityLookback.toString(),
        drawdown_period: drawdownPeriod,
      });

      const res = await fetch(`/api/v1/dashboard/portfolios/${portfolioId}/risk-overview?${query}`);
      if (!res.ok) {
        throw new Error(`Failed to fetch risk overview: ${res.statusText}`);
      }
      const json: RiskOverviewResponse = await res.json();
      setData(json);

      // Fetch underwater drawdown history
      const histRes = await fetch(`/api/v1/dashboard/portfolios/${portfolioId}/risk-overview/history?metric=DRAWDOWN`);
      if (histRes.ok) {
        const histJson: RiskHistoryResponse = await histRes.json();
        setHistoryData(histJson);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchRiskOverview();
  }, [portfolioId, confidenceLevel, horizonDays, varMethodology, volatilityLookback, drawdownPeriod]);

  if (isLoading && !data) {
    return (
      <div className="flex items-center justify-center p-12 text-muted">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mr-3"></div>
        <span>Retrieving authoritative risk metrics from M07 engine...</span>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="p-6 bg-negative-soft/40 border border-negative/20 rounded-lg text-negative">
        <h2 className="text-base font-semibold mb-1">Risk Overview Unavailable</h2>
        <p className="text-sm">{error}</p>
        <button
          onClick={fetchRiskOverview}
          className="mt-4 px-3 py-1.5 bg-negative-soft hover:bg-rose-700 text-white rounded text-xs font-medium"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Header & Global Filters */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-line">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-xl font-bold  text-ink">M13.02 — Risk Overview</h1>
            <span className="text-xs px-2 py-0.5 rounded bg-brand-soft border border-brand/20 text-brand font-sans">
              {data.portfolio_id}
            </span>
          </div>
          <p className="text-xs text-muted mt-1">
            Consolidated daily monitoring of VaR, Expected Shortfall, Volatility, and Drawdown.
          </p>
        </div>

        {/* Global Selectors */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Confidence Selector */}
          <div className="flex flex-col">
            <label className="text-[10px] text-muted uppercase font-semibold">Confidence</label>
            <select
              value={confidenceLevel}
              onChange={(e) => setConfidenceLevel(parseFloat(e.target.value))}
              className="bg-surface border border-line-strong text-secondary text-xs rounded px-2.5 py-1.5 focus:border-blue-500"
            >
              {data.available_confidence_levels.map((c) => (
                <option key={c} value={c}>
                  {(c * 100).toFixed(1)}%
                </option>
              ))}
            </select>
          </div>

          {/* Horizon Selector */}
          <div className="flex flex-col">
            <label className="text-[10px] text-muted uppercase font-semibold">Horizon</label>
            <select
              value={horizonDays}
              onChange={(e) => setHorizonDays(parseInt(e.target.value, 10))}
              className="bg-surface border border-line-strong text-secondary text-xs rounded px-2.5 py-1.5 focus:border-blue-500"
            >
              {data.available_horizons_days.map((h) => (
                <option key={h} value={h}>
                  {h} day{h > 1 ? 's' : ''}
                </option>
              ))}
            </select>
          </div>

          {/* VaR Methodology */}
          <div className="flex flex-col">
            <label className="text-[10px] text-muted uppercase font-semibold">VaR Model</label>
            <select
              value={varMethodology}
              onChange={(e) => setVarMethodology(e.target.value)}
              className="bg-surface border border-line-strong text-secondary text-xs rounded px-2.5 py-1.5 focus:border-blue-500"
            >
              {data.available_var_methodologies.map((m) => (
                <option key={m} value={m}>
                  {m.replace('_', ' ')}
                </option>
              ))}
            </select>
          </div>

          {/* Volatility Lookback */}
          <div className="flex flex-col">
            <label className="text-[10px] text-muted uppercase font-semibold">Vol Lookback</label>
            <select
              value={volatilityLookback}
              onChange={(e) => setVolatilityLookback(parseInt(e.target.value, 10))}
              className="bg-surface border border-line-strong text-secondary text-xs rounded px-2.5 py-1.5 focus:border-blue-500"
            >
              {data.available_volatility_lookbacks.map((lb) => (
                <option key={lb} value={lb}>
                  {lb}d
                </option>
              ))}
            </select>
          </div>

          {/* Drawdown Window */}
          <div className="flex flex-col">
            <label className="text-[10px] text-muted uppercase font-semibold">Drawdown Period</label>
            <select
              value={drawdownPeriod}
              onChange={(e) => setDrawdownPeriod(e.target.value)}
              className="bg-surface border border-line-strong text-secondary text-xs rounded px-2.5 py-1.5 focus:border-blue-500"
            >
              {data.available_drawdown_periods.map((p) => (
                <option key={p} value={p}>
                  {p.replace('_', ' ')}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={fetchRiskOverview}
            className="self-end px-3 py-1.5 bg-brand hover:bg-brand-hover text-white rounded text-xs font-medium transition"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Engine Status Banner */}
      <RiskDataStatus summary={data.quality_summary} asOf={data.as_of} />

      {/* Primary 4-KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <VaRCard data={data.var} />
        <ExpectedShortfallCard data={data.expected_shortfall} />
        <VolatilityCard data={data.volatility} />
        <DrawdownCard data={data.drawdown} />
      </div>

      {/* Section C: VaR vs Expected Shortfall Tail Analysis */}
      <VaRESComparison comparison={data.var_es_comparison} />

      {/* Section E: Drawdown Underwater Profile */}
      <DrawdownChart points={historyData?.underwater_points} baseCurrency={data.base_currency} />
    </div>
  );
};
