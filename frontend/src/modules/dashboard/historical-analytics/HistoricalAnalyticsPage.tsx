import React, { useState, useEffect, useCallback } from 'react';
import {
  HistoricalMode,
  HistoricalPortfolioValueResponse,
  HistoricalRiskTrendResponse,
  EventOverlayItem,
  PointInTimeStateResponse,
} from '../../../types/dashboard';
import { HistoricalAnalyticsToolbar } from './components/HistoricalAnalyticsToolbar';
import { HistoricalPortfolioValueChart } from './components/HistoricalPortfolioValueChart';
import { HistoricalRiskTrends } from './components/HistoricalRiskTrends';
import { HistoricalEventOverlay } from './components/HistoricalEventOverlay';
import { HistoricalStateInspector } from './components/HistoricalStateInspector';

export const HistoricalAnalyticsPage: React.FC = () => {
  const [portfolioId, setPortfolioId] = useState<string>('PORT-HIST-01');
  const [lookbackDays, setLookbackDays] = useState<number>(90);
  const [frequency, setFrequency] = useState<string>('DAILY');
  const [historicalMode, setHistoricalMode] = useState<HistoricalMode>('AS_KNOWN_AT_TIME');
  const [showEvents, setShowEvents] = useState<boolean>(true);
  const [selectedRiskMetric, setSelectedRiskMetric] = useState<string>('VAR');
  const [selectedEventCategory, setSelectedEventCategory] = useState<string>('ALL');

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [portfolioValues, setPortfolioValues] = useState<HistoricalPortfolioValueResponse | null>(null);
  const [riskTrends, setRiskTrends] = useState<HistoricalRiskTrendResponse | null>(null);
  const [events, setEvents] = useState<EventOverlayItem[]>([]);
  const [selectedState, setSelectedState] = useState<PointInTimeStateResponse | null>(null);

  // Load Main Historical Data
  const loadHistoricalData = useCallback(async () => {
    setIsLoading(true);
    try {
      const now = new Date();
      const startDate = new Date();
      startDate.setDate(now.getDate() - lookbackDays);

      const startIso = startDate.toISOString();
      const endIso = now.toISOString();

      // 1. Fetch NAV & Values
      const navRes = await fetch(
        `/api/v1/dashboard/history/portfolio-values?portfolio_id=${portfolioId}&frequency=${frequency}&historical_mode=${historicalMode}&start_time=${startIso}&end_time=${endIso}`
      );
      if (navRes.ok) {
        const json = await navRes.json();
        setPortfolioValues(json);
      }

      // 2. Fetch Risk Trends
      const riskRes = await fetch(
        `/api/v1/dashboard/history/risk-trends?portfolio_id=${portfolioId}&metric=${selectedRiskMetric}&frequency=${frequency}&historical_mode=${historicalMode}&start_time=${startIso}&end_time=${endIso}`
      );
      if (riskRes.ok) {
        const json = await riskRes.json();
        setRiskTrends(json);
      }

      // 3. Fetch Event Overlays
      if (showEvents) {
        const eventRes = await fetch(
          `/api/v1/dashboard/history/events?portfolio_id=${portfolioId}&start_time=${startIso}&end_time=${endIso}`
        );
        if (eventRes.ok) {
          const json = await eventRes.json();
          setEvents(json.events || []);
        }
      } else {
        setEvents([]);
      }
    } catch (err) {
      console.error('Failed to load historical analytics data', err);
    } finally {
      setIsLoading(false);
    }
  }, [portfolioId, lookbackDays, frequency, historicalMode, selectedRiskMetric, showEvents]);

  useEffect(() => {
    loadHistoricalData();
  }, [loadHistoricalData]);

  // Inspect Point-In-Time State
  const handleSelectTimestamp = async (timestamp: string) => {
    try {
      const res = await fetch(
        `/api/v1/dashboard/history/point-in-time?portfolio_id=${portfolioId}&effective_at=${timestamp}&historical_mode=${historicalMode}`
      );
      if (res.ok) {
        const json = await res.json();
        setSelectedState(json);
      }
    } catch (err) {
      console.error('Failed to reconstruct point-in-time state', err);
    }
  };

  return (
    <div className="p-6 bg-slate-950 min-h-screen text-slate-100 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-50 flex items-center gap-2">
            Historical Analytics & Audit Workspace
            <span className="text-xs px-2.5 py-1 bg-indigo-950 text-indigo-300 border border-indigo-800 rounded font-semibold">
              M13.09
            </span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Bitemporal point-in-time investigation, authoritative snapshot reconstruction, and version comparison
          </p>
        </div>
      </div>

      {/* Global Toolbar */}
      <HistoricalAnalyticsToolbar
        portfolioId={portfolioId}
        onPortfolioChange={setPortfolioId}
        lookbackDays={lookbackDays}
        onLookbackChange={setLookbackDays}
        frequency={frequency}
        onFrequencyChange={setFrequency}
        historicalMode={historicalMode}
        onHistoricalModeChange={setHistoricalMode}
        showEvents={showEvents}
        onToggleEvents={setShowEvents}
        onRefresh={loadHistoricalData}
        isLoading={isLoading}
      />

      {/* Point-in-Time State Inspector Drawer / Panel */}
      {selectedState && (
        <HistoricalStateInspector
          state={selectedState}
          onClose={() => setSelectedState(null)}
        />
      )}

      {/* NAV Chart */}
      <HistoricalPortfolioValueChart
        data={portfolioValues}
        onSelectTimestamp={handleSelectTimestamp}
      />

      {/* Risk Evolution & Event Overlays Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <HistoricalRiskTrends
          data={riskTrends}
          selectedMetric={selectedRiskMetric}
          onMetricChange={setSelectedRiskMetric}
          onSelectTimestamp={handleSelectTimestamp}
        />

        {showEvents && (
          <HistoricalEventOverlay
            events={events}
            selectedCategory={selectedEventCategory}
            onSelectCategory={setSelectedEventCategory}
            onSelectEvent={(evt) => handleSelectTimestamp(evt.occurrence_time)}
          />
        )}
      </div>
    </div>
  );
};

export default HistoricalAnalyticsPage;
