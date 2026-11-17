import React, { useState, useEffect } from 'react';
import {
  ScenarioMetadataItem,
  ScenarioDetailResultResponse,
  MonteCarloDistributionResponse,
  ScenarioComparisonResponse,
  StressAttributionResponse,
  StressPreferenceResponse,
  StressSavedViewResponse,
  StressAnnotationResponse,
} from '../../../types/dashboard';
import { ScenarioResultsPanel } from './components/ScenarioResultsPanel';
import { MonteCarloDistributionPanel } from './components/MonteCarloDistributionPanel';
import { ScenarioComparisonPanel } from './components/ScenarioComparisonPanel';
import { StressAttributionPanel } from './components/StressAttributionPanel';

export const StressTestingDashboardPage: React.FC = () => {
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>('');
  const [availablePortfolios, setAvailablePortfolios] = useState<Array<{ portfolio_id: string; portfolio_name: string }>>([]);
  const [scenarios, setScenarios] = useState<ScenarioMetadataItem[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);
  const [selectedCalculationId, setSelectedCalculationId] = useState<string | null>(null);

  // Fetch available portfolios dynamically
  useEffect(() => {
    const fetchPortfolios = async () => {
      try {
        const res = await fetch('/api/v1/portfolios?limit=50');
        if (res.ok) {
          const list = await res.json();
          if (Array.isArray(list) && list.length > 0) {
            setAvailablePortfolios(list);
            if (!selectedPortfolioId) {
              setSelectedPortfolioId(list[0].portfolio_id);
            }
          } else if (!selectedPortfolioId) {
            setSelectedPortfolioId('PORT_DEFAULT');
          }
        }
      } catch (err) {
        console.error('Failed to load portfolio list for stress dashboard:', err);
        if (!selectedPortfolioId) {
          setSelectedPortfolioId('PORT_DEFAULT');
        }
      }
    };
    fetchPortfolios();
  }, []);

  // Active Tab View
  const [activeTab, setActiveTab] = useState<'RESULTS' | 'DISTRIBUTION' | 'COMPARISON' | 'ATTRIBUTION'>(
    'RESULTS'
  );

  // Data states
  const [scenarioResult, setScenarioResult] = useState<ScenarioDetailResultResponse | null>(null);
  const [mcDistribution, setMcDistribution] = useState<MonteCarloDistributionResponse | null>(null);
  const [comparison, setComparison] = useState<ScenarioComparisonResponse | null>(null);
  const [attribution, setAttribution] = useState<StressAttributionResponse | null>(null);

  // Preferences & Annotations
  const [annotations, setAnnotations] = useState<StressAnnotationResponse[]>([]);
  const [newAnnotationNote, setNewAnnotationNote] = useState<string>('');
  const [annotationTitle, setAnnotationTitle] = useState<string>('');

  // Loading states
  const [loadingScenarios, setLoadingScenarios] = useState<boolean>(false);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // 1. Fetch scenario library
  useEffect(() => {
    fetchScenarios();
  }, [selectedPortfolioId, selectedCategory]);

  const fetchScenarios = async () => {
    setLoadingScenarios(true);
    try {
      const catParam = selectedCategory !== 'ALL' ? `&category=${selectedCategory}` : '';
      const res = await fetch(
        `/api/v1/dashboard/stress/scenarios?portfolio_id=${selectedPortfolioId}${catParam}`
      );
      if (res.ok) {
        const data: ScenarioMetadataItem[] = await res.json();
        setScenarios(data);
        if (data.length > 0 && !selectedScenarioId) {
          handleSelectScenario(data[0]);
        }
      }
    } catch (err) {
      console.error('Failed to load scenarios', err);
    } finally {
      setLoadingScenarios(false);
    }
  };

  const handleSelectScenario = async (scen: ScenarioMetadataItem) => {
    setSelectedScenarioId(scen.scenario_id);
    const calcId = scen.latest_calculation_id || scen.scenario_id;
    setSelectedCalculationId(calcId);

    setLoadingDetail(true);
    setErrorMsg(null);

    try {
      // 1. Fetch Scenario Result
      const resPromise = fetch(`/api/v1/dashboard/stress/results/${calcId}`);
      // 2. Fetch Loss Attribution
      const attrPromise = fetch(`/api/v1/dashboard/stress/attribution/${calcId}`);
      // 3. Fetch Monte Carlo if category is MONTE_CARLO
      const mcPromise =
        scen.category === 'MONTE_CARLO'
          ? fetch(`/api/v1/dashboard/stress/results/${calcId}/distribution`)
          : Promise.resolve(null);
      // 4. Fetch Annotations
      const annoPromise = fetch(`/api/v1/dashboard/stress/annotations?scenario_id=${scen.scenario_id}`);

      const [resResp, attrResp, mcResp, annoResp] = await Promise.all([
        resPromise,
        attrPromise,
        mcPromise,
        annoPromise,
      ]);

      if (resResp && resResp.ok) {
        const resData: ScenarioDetailResultResponse = await resResp.json();
        setScenarioResult(resData);
      }

      if (attrResp && attrResp.ok) {
        const attrData: StressAttributionResponse = await attrResp.json();
        setAttribution(attrData);
      }

      if (mcResp && mcResp.ok) {
        const mcData: MonteCarloDistributionResponse = await mcResp.json();
        setMcDistribution(mcData);
      } else if (scen.category !== 'MONTE_CARLO') {
        setMcDistribution(null);
      }

      if (annoResp && annoResp.ok) {
        const annoData: StressAnnotationResponse[] = await annoResp.json();
        setAnnotations(annoData);
      }
    } catch (err: any) {
      console.error('Error fetching scenario details', err);
      setErrorMsg('Failed to fetch authoritative scenario details from backend.');
    } finally {
      setLoadingDetail(false);
    }
  };

  // Run multi-scenario comparison
  const handleRunComparison = async () => {
    const calcIds = scenarios
      .map((s) => s.latest_calculation_id)
      .filter((id): id is string => Boolean(id))
      .slice(0, 5);

    if (calcIds.length === 0) return;

    setLoadingDetail(true);
    try {
      const res = await fetch(`/api/v1/dashboard/stress/compare?portfolio_id=${encodeURIComponent(selectedPortfolioId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          calculation_ids: calcIds,
        }),
      });
      if (res.ok) {
        const compData: ScenarioComparisonResponse = await res.json();
        setComparison(compData);
        setActiveTab('COMPARISON');
      }
    } catch (err) {
      console.error('Error comparing scenarios', err);
    } finally {
      setLoadingDetail(false);
    }
  };

  // Submit new annotation
  const handleAddAnnotation = async () => {
    if (!selectedScenarioId || !annotationTitle || !newAnnotationNote) return;

    try {
      const res = await fetch('/api/v1/dashboard/stress/annotations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          portfolio_id: selectedPortfolioId,
          scenario_id: selectedScenarioId,
          calculation_id: selectedCalculationId,
          annotation_type: 'INVESTIGATION',
          severity: 'HIGH',
          title: annotationTitle,
          notes: newAnnotationNote,
          metrics_snapshot: scenarioResult ? { stressed_pnl: scenarioResult.summary.stressed_pnl } : {},
        }),
      });
      if (res.ok) {
        const created: StressAnnotationResponse = await res.json();
        setAnnotations([created, ...annotations]);
        setAnnotationTitle('');
        setNewAnnotationNote('');
      }
    } catch (err) {
      console.error('Failed to create annotation', err);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Stress Testing Dashboard
            </h1>
            <span className="px-2.5 py-0.5 text-xs font-semibold rounded bg-rose-950/80 text-rose-300 border border-rose-800/80">
              M13.07 Production
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Authoritative scenario evaluation, loss distributions, cross-model comparison, and risk decomposition.
          </p>
        </div>

        {/* Global Action Bar */}
        <div className="flex items-center gap-3">
          {availablePortfolios.length > 0 && (
            <select
              value={selectedPortfolioId}
              onChange={(e) => setSelectedPortfolioId(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded px-3 py-2 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono"
            >
              {availablePortfolios.map((p) => (
                <option key={p.portfolio_id} value={p.portfolio_id}>
                  {p.portfolio_name ? `${p.portfolio_id} (${p.portfolio_name})` : p.portfolio_id}
                </option>
              ))}
            </select>
          )}
          <button
            onClick={handleRunComparison}
            className="px-3.5 py-2 text-xs font-semibold rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition shadow-sm"
          >
            Compare Top Scenarios
          </button>
        </div>
      </div>

      {/* Scenario Library Carousel / Grid */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
              Scenario Library
            </h2>
            <span className="text-xs text-slate-500 font-mono">({scenarios.length} active)</span>
          </div>

          {/* Filter Pills */}
          <div className="flex gap-1.5 overflow-x-auto text-xs">
            {['ALL', 'HISTORICAL', 'MONTE_CARLO', 'CRASH', 'SECTOR'].map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-2.5 py-1 rounded text-xs transition ${
                  selectedCategory === cat
                    ? 'bg-slate-700 text-white font-semibold'
                    : 'bg-slate-950 text-slate-400 hover:text-slate-200'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Scenario Cards */}
        {loadingScenarios ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 animate-pulse">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-20 bg-slate-800 rounded" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
            {scenarios.map((scen) => {
              const isSelected = scen.scenario_id === selectedScenarioId;
              return (
                <div
                  key={scen.scenario_id}
                  onClick={() => handleSelectScenario(scen)}
                  className={`p-3.5 rounded-lg border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-blue-950/40 border-blue-600 ring-1 ring-blue-500'
                      : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                      {scen.category}
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      v{scen.version}
                    </span>
                  </div>
                  <div className="font-semibold text-xs text-white truncate">
                    {scen.scenario_name}
                  </div>
                  <div className="text-[11px] text-slate-400 truncate mt-0.5">
                    {scen.description || scen.affected_markets || 'Global financial stress'}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-800 space-x-6 text-sm">
        <button
          onClick={() => setActiveTab('RESULTS')}
          className={`pb-3 font-semibold transition border-b-2 ${
            activeTab === 'RESULTS'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Scenario Stressed Results
        </button>

        {mcDistribution && (
          <button
            onClick={() => setActiveTab('DISTRIBUTION')}
            className={`pb-3 font-semibold transition border-b-2 ${
              activeTab === 'DISTRIBUTION'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Monte Carlo Distribution & Quantiles
          </button>
        )}

        <button
          onClick={() => setActiveTab('ATTRIBUTION')}
          className={`pb-3 font-semibold transition border-b-2 ${
            activeTab === 'ATTRIBUTION'
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Loss Attribution & Reconciliation
        </button>

        {comparison && (
          <button
            onClick={() => setActiveTab('COMPARISON')}
            className={`pb-3 font-semibold transition border-b-2 ${
              activeTab === 'COMPARISON'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Scenario Comparison
          </button>
        )}
      </div>

      {errorMsg && (
        <div className="bg-rose-950/30 border border-rose-800 p-4 rounded-lg text-rose-300 text-xs">
          {errorMsg}
        </div>
      )}

      {/* Active Panel View */}
      {activeTab === 'RESULTS' && (
        <ScenarioResultsPanel
          data={scenarioResult}
          loading={loadingDetail}
          onRefresh={() => {
            const currentScen = scenarios.find((s) => s.scenario_id === selectedScenarioId);
            if (currentScen) handleSelectScenario(currentScen);
          }}
        />
      )}

      {activeTab === 'DISTRIBUTION' && (
        <MonteCarloDistributionPanel
          distribution={mcDistribution}
          loading={loadingDetail}
        />
      )}

      {activeTab === 'ATTRIBUTION' && (
        <StressAttributionPanel
          attribution={attribution}
          loading={loadingDetail}
        />
      )}

      {activeTab === 'COMPARISON' && (
        <ScenarioComparisonPanel
          comparison={comparison}
          loading={loadingDetail}
          onSelectScenario={(calcId) => {
            const match = scenarios.find((s) => s.latest_calculation_id === calcId);
            if (match) {
              handleSelectScenario(match);
              setActiveTab('RESULTS');
            }
          }}
        />
      )}

      {/* Annotations & Audit Sign-Off Section */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 space-y-4">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
          Risk Notes & Governance Sign-Offs
        </h3>

        {/* Existing Annotations List */}
        <div className="space-y-2">
          {annotations.length === 0 ? (
            <div className="text-xs text-slate-500">No notes recorded for this scenario.</div>
          ) : (
            annotations.map((a) => (
              <div
                key={a.id}
                className="bg-slate-950/60 p-3 rounded border border-slate-800/80 text-xs flex justify-between items-start"
              >
                <div>
                  <div className="font-semibold text-white flex items-center gap-2">
                    <span>{a.title}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800/60">
                      {a.severity}
                    </span>
                  </div>
                  <div className="text-slate-300 mt-1">{a.notes}</div>
                </div>
                <div className="text-[10px] text-slate-500 font-mono">
                  {new Date(a.created_at).toLocaleDateString()}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Add Annotation Form */}
        <div className="pt-3 border-t border-slate-800/80 flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            placeholder="Sign-off title or alert topic..."
            value={annotationTitle}
            onChange={(e) => setAnnotationTitle(e.target.value)}
            className="flex-1 bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
          />
          <input
            type="text"
            placeholder="Analytical rationale, mitigation notes..."
            value={newAnnotationNote}
            onChange={(e) => setNewAnnotationNote(e.target.value)}
            className="flex-2 bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={handleAddAnnotation}
            className="px-4 py-1.5 text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700 transition"
          >
            Record Sign-Off
          </button>
        </div>
      </div>
    </div>
  );
};
