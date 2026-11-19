import { UpstoxBrokerPanel } from '../../../components/UpstoxBrokerPanel';
import React, { useState, useEffect } from 'react';
import { FolderOpen, Layers, BarChart3, RefreshCw, SlidersHorizontal, Activity } from 'lucide-react';
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
import { PortfolioVisualizerConfigPanel } from './components/PortfolioVisualizerConfigPanel';
import { SimulationRunComparison, CompletedSimulation } from './components/SimulationRunComparison';

interface StressTestingDashboardPageProps {
  portfolioId?: string;
}

export const StressTestingDashboardPage: React.FC<StressTestingDashboardPageProps> = ({ portfolioId }) => {
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>(portfolioId || '');
  const [availablePortfolios, setAvailablePortfolios] = useState<Array<{ portfolio_id: string; portfolio_name: string }>>([]);
  const [scenarios, setScenarios] = useState<ScenarioMetadataItem[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);
  const [selectedCalculationId, setSelectedCalculationId] = useState<string | null>(null);

  useEffect(() => {
    if (portfolioId) {
      setSelectedPortfolioId(portfolioId);
    }
  }, [portfolioId]);

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
              setSelectedPortfolioId(portfolioId || list[0].portfolio_id);
            }
          } else if (!selectedPortfolioId) {
            setSelectedPortfolioId(portfolioId || 'PORT_DEFAULT');
          }
        }
      } catch (err) {
        console.error('Failed to load portfolio list for stress dashboard:', err);
        if (!selectedPortfolioId) {
          setSelectedPortfolioId(portfolioId || 'PORT_DEFAULT');
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
  const [completedSimulations, setCompletedSimulations] = useState<Array<CompletedSimulation & { portfolioId: string }>>([]);
  const [showRunComparison, setShowRunComparison] = useState(false);
  const portfolioRuns = completedSimulations.filter(run => run.portfolioId === selectedPortfolioId);
  useEffect(() => { setShowRunComparison(false); }, [selectedPortfolioId]);
  useEffect(() => {
    if (showRunComparison) {
      const heading = document.getElementById('simulation-comparison-heading');
      heading?.focus({ preventScroll: true });
      heading?.scrollIntoView({ block: 'start' });
    }
  }, [showRunComparison]);
  const [comparison, setComparison] = useState<ScenarioComparisonResponse | null>(null);
  const [attribution, setAttribution] = useState<StressAttributionResponse | null>(null);

  // Preferences & Annotations
  const [annotations, setAnnotations] = useState<StressAnnotationResponse[]>([]);
  const [newAnnotationNote, setNewAnnotationNote] = useState<string>('');
  const [annotationTitle, setAnnotationTitle] = useState<string>('');

  // Loading states
  const [loadingScenarios, setLoadingScenarios] = useState<boolean>(false);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [isSimulatingPV, setIsSimulatingPV] = useState<boolean>(false);
  const [showPvConfig, setShowPvConfig] = useState<boolean>(true);
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
    // Collect up to 5 calculation IDs or fallback to scenario IDs
    const calcIds = scenarios
      .map((s) => s.latest_calculation_id || s.scenario_id)
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

  // Run Portfolio Visualizer simulation
  const handleRunVisualizerSimulation = async (config: any) => {
    setIsSimulatingPV(true);
    setErrorMsg(null);
    try {
      const res = await fetch('/api/v1/dashboard/stress/simulation/run-visualizer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (res.ok) {
        const data: MonteCarloDistributionResponse = await res.json();
        setMcDistribution(data);
        setCompletedSimulations(previous => [
          ...previous.filter(run => run.portfolioId !== selectedPortfolioId),
          ...previous.filter(run => run.portfolioId === selectedPortfolioId).slice(-1),
          { result: data, config, completedAt: new Date().toISOString(), portfolioId: selectedPortfolioId },
        ]);
        setShowRunComparison(false);
        setActiveTab('DISTRIBUTION');
      } else {
        const errText = await res.text();
        setErrorMsg(`Simulation failed: ${errText || res.statusText}`);
      }
    } catch (err: any) {
      console.error('Failed to run Portfolio Visualizer simulation', err);
      setErrorMsg('Failed to run Portfolio Visualizer simulation. Please try again.');
    } finally {
      setIsSimulatingPV(false);
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
    <div className="min-w-0 text-ink space-y-7">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-line">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-semibold text-ink ">
              Stress Testing
            </h1>
          </div>
          <p className="text-xs text-muted mt-1">
            Explore scenarios, compare outcomes, and understand your downside risk.
          </p>
        </div>

        {/* Global Action Bar */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Active Portfolio Badge (Synced with Header) */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface border border-line text-xs">
            <FolderOpen className="size-3.5 text-muted" />
            <span className="text-muted">Portfolio:</span>
            <span className="font-medium text-secondary">
              {availablePortfolios.find((p) => p.portfolio_id === selectedPortfolioId)?.portfolio_name || selectedPortfolioId}
            </span>
          </div>

          <button
            type="button"
            onClick={handleRunComparison}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-surface hover:bg-subtle border border-line hover:border-line-strong text-secondary transition-colors"
          >
            <BarChart3 className="size-3.5 text-positive" />
            <span>Compare Top Scenarios</span>
          </button>
        </div>
      </div>

      {/* Scenario Library Carousel / Grid */}
      <div className="bg-surface border border-line rounded-lg p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold uppercase  text-secondary">
              Scenario Library
            </h2>
            <span className="text-xs text-muted font-sans">({scenarios.length} active)</span>
          </div>

          {/* Filter Pills */}
          <div className="flex gap-1.5 overflow-x-auto text-xs">
            {['ALL', 'HISTORICAL', 'MONTE_CARLO', 'CRASH', 'SECTOR'].map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-2.5 py-1 rounded text-xs transition ${
                  selectedCategory === cat
                    ? 'bg-hover text-ink font-semibold'
                    : 'bg-canvas text-muted hover:text-secondary'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Scenario Cards */}
        {loadingScenarios ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 ">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-20 bg-subtle rounded" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
            {scenarios.map((scen) => {
              const isSelected = scen.scenario_id === selectedScenarioId;
              return (
                <button type="button" aria-pressed={isSelected}
                  key={scen.scenario_id}
                  onClick={() => handleSelectScenario(scen)}
                  className={`text-left p-4 rounded-xl border cursor-pointer transition-opacity ${
                    isSelected
                      ? 'bg-brand-soft/40 border-brand/20 ring-1 ring-blue-500'
                      : 'bg-canvas/60 border-line hover:border-line-strong'
                  }`}
                >
                  <span className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-subtle text-secondary">
                      {scen.category}
                    </span>
                    <span className="text-[10px] text-muted font-sans">
                      v{scen.version}
                    </span>
                  </span>
                  <span className="block font-semibold text-xs text-ink truncate">
                    {scen.scenario_name}
                  </span>
                  <span className="block text-xs text-muted truncate mt-1">
                    {scen.description || scen.affected_markets || 'Global financial stress'}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Navigation Tabs */}
      <div className="flex max-w-full gap-5 overflow-x-auto border-b border-line text-sm">
        <button
          onClick={() => setActiveTab('RESULTS')}
          className={`pb-3 font-semibold transition border-b-2 ${
            activeTab === 'RESULTS'
              ? 'border-blue-500 text-brand'
              : 'border-transparent text-muted hover:text-secondary'
          }`}
        >
          Scenario Stressed Results
        </button>

        <button
          onClick={() => setActiveTab('DISTRIBUTION')}
          className={`pb-3 font-semibold transition border-b-2 flex items-center gap-1.5 ${
            activeTab === 'DISTRIBUTION'
              ? 'border-blue-500 text-brand'
              : 'border-transparent text-muted hover:text-secondary'
          }`}
        >
          <Activity className="size-4" />
          Monte Carlo Simulation (Portfolio Visualizer)
        </button>

        <button
          onClick={() => setActiveTab('ATTRIBUTION')}
          className={`pb-3 font-semibold transition border-b-2 ${
            activeTab === 'ATTRIBUTION'
              ? 'border-blue-500 text-brand'
              : 'border-transparent text-muted hover:text-secondary'
          }`}
        >
          Loss Attribution & Reconciliation
        </button>

        {comparison && (
          <button
            onClick={() => setActiveTab('COMPARISON')}
            className={`pb-3 font-semibold transition border-b-2 ${
              activeTab === 'COMPARISON'
                ? 'border-blue-500 text-brand'
                : 'border-transparent text-muted hover:text-secondary'
            }`}
          >
            Scenario Comparison
          </button>
        )}
      </div>

      {errorMsg && (
        <div className="bg-negative-soft/30 border border-negative/20 p-4 rounded-lg text-negative text-xs">
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
        <div className="space-y-6">
          {/* Portfolio Visualizer Configuration Form Collapsible */}
          <div className="bg-surface border border-line rounded-lg overflow-hidden">
            <div
              className="px-6 py-4 flex items-center justify-between cursor-pointer bg-surface hover:bg-subtle border-b border-line transition"
              onClick={() => setShowPvConfig(!showPvConfig)}
            >
              <div className="flex flex-wrap items-center gap-2.5">
                <SlidersHorizontal className="size-4 text-brand" />
                <span className="font-semibold text-sm text-ink">
                  Simulation Model Configuration (Portfolio Visualizer Mode)
                </span>
                <span className="text-[11px] bg-brand/10 text-brand px-2 py-0.5 rounded border border-blue-500/20">
                  Interactive Asset Allocation & Cashflow Engine
                </span>
              </div>
              <span className="text-xs text-muted font-sans">
                {showPvConfig ? 'Hide Settings ▲' : 'Show Settings ▼'}
              </span>
            </div>

            {showPvConfig && (
              <div className="p-4 sm:p-6 bg-canvas/40">
                <PortfolioVisualizerConfigPanel
                  onRunSimulation={handleRunVisualizerSimulation}
                  onCompareResults={() => setShowRunComparison(true)}
                  canCompareResults={portfolioRuns.length === 2}
                  isRunning={isSimulatingPV}
                />
              </div>
            )}
          </div>

          {showRunComparison && <SimulationRunComparison runs={portfolioRuns} onClose={() => setShowRunComparison(false)} />}
          <MonteCarloDistributionPanel
            distribution={mcDistribution}
            loading={loadingDetail || isSimulatingPV}
          />
        </div>
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
      <div className="bg-surface border border-line rounded-lg p-6 space-y-4">
        <h3 className="text-sm font-semibold uppercase  text-secondary">
          Risk Notes & Governance Sign-Offs
        </h3>

        {/* Existing Annotations List */}
        <div className="space-y-2">
          {annotations.length === 0 ? (
            <div className="text-xs text-muted">No notes recorded for this scenario.</div>
          ) : (
            annotations.map((a) => (
              <div
                key={a.id}
                className="bg-canvas/60 p-3 rounded border border-line/80 text-xs flex justify-between items-start"
              >
                <div>
                  <div className="font-semibold text-ink flex items-center gap-2">
                    <span>{a.title}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-negative-soft text-negative border border-negative/20">
                      {a.severity}
                    </span>
                  </div>
                  <div className="text-secondary mt-1">{a.notes}</div>
                </div>
                <div className="text-[10px] text-muted font-sans">
                  {new Date(a.created_at).toLocaleDateString()}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Add Annotation Form */}
        <div className="pt-3 border-t border-line/80 flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            aria-label="Sign-off title" placeholder="Sign-off title or alert topic..."
            value={annotationTitle}
            onChange={(e) => setAnnotationTitle(e.target.value)}
            className="min-w-0 flex-1 bg-canvas border border-line rounded px-3 py-1.5 text-xs text-secondary focus:outline-none focus:border-blue-500"
          />
          <input
            type="text"
            aria-label="Analytical rationale" placeholder="Analytical rationale, mitigation notes..."
            value={newAnnotationNote}
            onChange={(e) => setNewAnnotationNote(e.target.value)}
            className="min-w-0 min-w-0 flex-1 bg-canvas border border-line rounded px-3 py-1.5 text-xs text-secondary focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={handleAddAnnotation}
            className="px-4 py-1.5 text-xs font-semibold bg-subtle hover:bg-hover text-secondary rounded border border-line-strong transition"
          >
            Record Sign-Off
          </button>
        </div>
      </div>
      <UpstoxBrokerPanel mode="stress" />
    </div>
  );
};
