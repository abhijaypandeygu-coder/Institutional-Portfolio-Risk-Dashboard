import React, { useState } from 'react';
import { Play, RotateCcw, Plus, Trash2, HelpCircle, Save, GitCompare, RefreshCw, Layers } from 'lucide-react';

interface AssetAllocationRow {
  id: string;
  name: string;
  pct: number;
}

interface PortfolioVisualizerConfigPanelProps {
  onRunSimulation: (config: any) => void;
  onCompareResults: () => void;
  canCompareResults: boolean;
  isRunning?: boolean;
}

export const PortfolioVisualizerConfigPanel: React.FC<PortfolioVisualizerConfigPanelProps> = ({
  onRunSimulation,
  onCompareResults,
  canCompareResults,
  isRunning = false,
}) => {
  // Mode switcher: Institutional Portfolio Risk vs Multi-Asset Wealth Projection
  const [configMode, setConfigMode] = useState<'INSTITUTIONAL' | 'WEALTH_PROJECTION'>('INSTITUTIONAL');

  // Institutional Portfolio Inputs
  const [portfolioSelector, setPortfolioSelector] = useState('Global Equity Long/Short');
  const [portfolioValuationSource, setPortfolioValuationSource] = useState('Derived from M05 Valuation');
  const [positionSelection, setPositionSelection] = useState('All Holdings');
  const [benchmark, setBenchmark] = useState('SPY');
  const [currencyTimestamp, setCurrencyTimestamp] = useState('USD · Live Ingestion');

  // Simulation Parameters
  const [simulationModel, setSimulationModel] = useState('Student-t (Heavy Tail)');
  const [holdingPeriodDays, setHoldingPeriodDays] = useState<number>(1);
  const [numSimulations, setNumSimulations] = useState<number>(2000);
  const [lookbackPeriod, setLookbackPeriod] = useState<string>('252 Trading Days (1 Year)');
  const [returnFrequency, setReturnFrequency] = useState<string>('Daily');
  const [randomSeed, setRandomSeed] = useState<number>(42);
  const [confidenceLevel, setConfidenceLevel] = useState<number>(95);

  // Risk Assumptions
  const [volatilityAssumption, setVolatilityAssumption] = useState('Realized Historical Volatility');
  const [correlationAssumption, setCorrelationAssumption] = useState('Empirical Higham-Repaired Correlation');
  const [factorShockAssumption, setFactorShockAssumption] = useState('None (Full Covariance)');
  const [liquidityShockAssumption, setLiquidityShockAssumption] = useState('Standard Execution Haircut');
  const [transactionCostBps, setTransactionCostBps] = useState<number>(5.0);
  const [marketRegime, setMarketRegime] = useState('Current Regime');

  // Multi-Asset Wealth Projection Controls
  const [initialAmount, setInitialAmount] = useState<number>(1000000);
  const [cashflows, setCashflows] = useState('Withdraw fixed amount periodically');
  const [withdrawalAmount, setWithdrawalAmount] = useState<number>(45000);
  const [inflationAdjusted, setInflationAdjusted] = useState('Yes');
  const [withdrawalFrequency, setWithdrawalFrequency] = useState('Annually');
  const [simulationPeriodYears, setSimulationPeriodYears] = useState<number>(30);
  const [taxTreatment, setTaxTreatment] = useState('Pre-tax Returns');
  const [wealthSimModel, setWealthSimModel] = useState('Historical Returns');
  const [bootstrapModel, setBootstrapModel] = useState('Single Year');
  const [sequenceOfReturns, setSequenceOfReturns] = useState('No Adjustments');
  const [rebalancing, setRebalancing] = useState('Rebalance annually');

  // Real Multi-Market Holdings (Equities across Indian & US Markets) for Institutional Mode
  const institutionalAssets: AssetAllocationRow[] = [
    { id: '1', name: 'RELIANCE.NS (Reliance Industries - NSE)', pct: 25 },
    { id: '2', name: 'TCS.NS (Tata Consultancy Services - NSE)', pct: 20 },
    { id: '3', name: 'HDFCBANK.NS (HDFC Bank - NSE)', pct: 15 },
    { id: '4', name: 'AAPL (Apple Inc. - NASDAQ)', pct: 20 },
    { id: '5', name: 'NVDA (NVIDIA Corp - NASDAQ)', pct: 20 },
  ];

  // Benchmark multi-asset classes for Wealth Projection Mode
  const wealthAssets: AssetAllocationRow[] = [
    { id: 'w1', name: 'US Stock Market', pct: 60 },
    { id: 'w2', name: '10-year Treasury', pct: 40 },
  ];

  const [assets, setAssets] = useState<AssetAllocationRow[]>(institutionalAssets);

  // Switch assets when toggling mode
  const handleModeChange = (mode: 'INSTITUTIONAL' | 'WEALTH_PROJECTION') => {
    setConfigMode(mode);
    if (mode === 'INSTITUTIONAL') {
      setAssets(institutionalAssets);
    } else {
      setAssets(wealthAssets);
    }
  };

  const [notification, setNotification] = useState<string | null>(null);

  const notify = (msg: string) => {
    setNotification(msg);
    setTimeout(() => setNotification(null), 3000);
  };

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Array<{ symbol: string; name: string; exchange?: string }>>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSearchDropdown, setShowSearchDropdown] = useState(false);

  // Quick-add popular watchlist / global market mover presets
  const popularPresets = [
    { symbol: 'AAPL', name: 'Apple Inc. (NASDAQ)' },
    { symbol: 'NVDA', name: 'NVIDIA Corp (NASDAQ)' },
    { symbol: 'TSLA', name: 'Tesla Inc. (NASDAQ)' },
    { symbol: 'MSFT', name: 'Microsoft Corp (NASDAQ)' },
    { symbol: 'AMZN', name: 'Amazon.com Inc. (NASDAQ)' },
    { symbol: 'RELIANCE.NS', name: 'Reliance Industries (NSE)' },
    { symbol: 'TCS.NS', name: 'Tata Consultancy Services (NSE)' },
    { symbol: 'HDFCBANK.NS', name: 'HDFC Bank (NSE)' },
    { symbol: 'GLD', name: 'SPDR Gold Shares (ETF)' },
  ];

  const handleSearchTickers = async (q: string) => {
    setSearchQuery(q);
    if (!q || q.trim().length < 1) {
      setSearchResults([]);
      setShowSearchDropdown(false);
      return;
    }
    setIsSearching(true);
    try {
      const res = await fetch(`/api/v1/dashboard/liquidity/search-tickers?q=${encodeURIComponent(q.trim())}&limit=8`);
      if (res.ok) {
        const data = await res.json();
        setSearchResults(Array.isArray(data) ? data : []);
        setShowSearchDropdown(true);
      }
    } catch (err) {
      console.error('Ticker search error:', err);
    } finally {
      setIsSearching(false);
    }
  };

  const addAsset = (symbol: string, name?: string, exchange?: string) => {
    const formattedName = `${symbol}${name ? ` (${name}${exchange ? ` - ${exchange}` : ''})` : ''}`;
    // Check if already in list
    if (assets.some(a => a.name.includes(symbol))) {
      notify(`${symbol} is already in the asset allocations.`);
      setSearchQuery('');
      setShowSearchDropdown(false);
      return;
    }
    const newRow: AssetAllocationRow = {
      id: `custom_${Date.now()}_${symbol}`,
      name: formattedName,
      pct: 0,
    };
    setAssets(prev => [...prev, newRow]);
    setSearchQuery('');
    setShowSearchDropdown(false);
    notify(`Added ${symbol} to asset exposures.`);
  };

  const removeAsset = (id: string) => {
    if (assets.length <= 1) {
      notify('At least one asset allocation row is required.');
      return;
    }
    setAssets(prev => prev.filter(a => a.id !== id));
  };

  const handlePctChange = (id: string, val: string) => {
    const num = Math.max(0, Math.min(100, Number(val) || 0));
    setAssets((prev) => prev.map((a) => (a.id === id ? { ...a, pct: num } : a)));
  };

  const totalAllocation = assets.reduce((sum, a) => sum + (Number(a.pct) || 0), 0);

  const handleReset = () => {
    setConfigMode('INSTITUTIONAL');
    setPortfolioSelector('Global Equity Long/Short');
    setPortfolioValuationSource('Derived from M05 Valuation');
    setPositionSelection('All Holdings');
    setBenchmark('SPY');
    setCurrencyTimestamp('USD · Live Ingestion');
    setHoldingPeriodDays(1);
    setNumSimulations(2000);
    setRandomSeed(42);
    setConfidenceLevel(95);
    setSimulationModel('Student-t (Heavy Tail)');
    setLookbackPeriod('252 Trading Days (1 Year)');
    setReturnFrequency('Daily');
    setVolatilityAssumption('Realized Historical Volatility');
    setCorrelationAssumption('Empirical Higham-Repaired Correlation');
    setFactorShockAssumption('None (Full Covariance)');
    setLiquidityShockAssumption('Standard Execution Haircut');
    setTransactionCostBps(5.0);
    setMarketRegime('Current Regime');
    setInitialAmount(1000000);
    setCashflows('Withdraw fixed amount periodically');
    setWithdrawalAmount(45000);
    setInflationAdjusted('Yes');
    setWithdrawalFrequency('Annually');
    setSimulationPeriodYears(30);
    setTaxTreatment('Pre-tax Returns');
    setWealthSimModel('Historical Returns');
    setBootstrapModel('Single Year');
    setSequenceOfReturns('No Adjustments');
    setRebalancing('Rebalance annually');
    setAssets([
      { id: '1', name: 'RELIANCE.NS (Reliance Industries - NSE)', pct: 25 },
      { id: '2', name: 'TCS.NS (Tata Consultancy Services - NSE)', pct: 20 },
      { id: '3', name: 'HDFCBANK.NS (HDFC Bank - NSE)', pct: 15 },
      { id: '4', name: 'AAPL (Apple Inc. - NASDAQ)', pct: 20 },
      { id: '5', name: 'NVDA (NVIDIA Corp - NASDAQ)', pct: 20 },
    ]);
    notify('All configuration fields and allocations restored to defaults.');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onRunSimulation({
      portfolio_mode: configMode,
      portfolio_selector: portfolioSelector,
      portfolio_valuation_source: portfolioValuationSource,
      position_selection: positionSelection,
      benchmark,
      currency_timestamp: currencyTimestamp,
      holding_period_days: holdingPeriodDays,
      num_simulations: numSimulations,
      lookback_period: lookbackPeriod,
      return_frequency: returnFrequency,
      random_seed: randomSeed,
      confidence_level: confidenceLevel / 100,
      volatility_assumption: volatilityAssumption,
      correlation_assumption: correlationAssumption,
      factor_shock: factorShockAssumption,
      liquidity_shock: liquidityShockAssumption,
      transaction_cost_bps: transactionCostBps,
      market_regime: marketRegime,
      // Wealth projection mapping
      initial_amount: initialAmount,
      cashflows,
      withdrawal_amount: withdrawalAmount,
      inflation_adjusted: inflationAdjusted === 'Yes',
      withdrawal_frequency: withdrawalFrequency,
      simulation_period_years: configMode === 'INSTITUTIONAL' ? Math.max(1, Math.round(holdingPeriodDays / 252)) : simulationPeriodYears,
      tax_treatment: taxTreatment,
      simulation_model: wealthSimModel,
      bootstrap_model: bootstrapModel,
      sequence_of_returns_risk: sequenceOfReturns,
      rebalancing,
      allocations: assets
        .filter((a) => a.pct > 0)
        .map((a) => ({
          asset_id: a.id,
          asset_name: a.name,
          allocation_pct: a.pct,
        })),
    });
  };

  return (
    <div className="bg-surface border border-line rounded-xl p-6 shadow-xl space-y-6">
      {/* Toast Notification */}
      {notification && (
        <div role="status" className="bg-brand text-white text-xs px-4 py-2 rounded shadow flex items-center justify-between">
          <span>{notification}</span>
          <button onClick={() => setNotification(null)} className="font-bold ml-4">✕</button>
        </div>
      )}

      {/* Title & Mode Switcher */}
      <div className="border-b border-line pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-ink">Proposed Simulation Model Configuration</h2>
            <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-positive-soft text-positive border border-positive/20">
              Recommended Structure
            </span>
          </div>
          <p className="text-xs text-muted mt-0.5">
            Institutional portfolio-risk configuration across Indian and US market equities derived from M05 holdings.
          </p>
        </div>

        {/* Mode Selector */}
        <div className="flex bg-canvas p-1 rounded-lg border border-line">
          <button
            type="button"
            onClick={() => handleModeChange('INSTITUTIONAL')}
            aria-pressed={configMode === 'INSTITUTIONAL'}
            className={`px-3 py-1.5 text-xs font-semibold rounded transition flex items-center gap-1.5 ${
              configMode === 'INSTITUTIONAL'
                ? 'bg-brand text-white shadow-sm'
                : 'text-muted hover:text-secondary'
            }`}
          >
            <Layers className="size-3.5" />
            Institutional Portfolio Risk
          </button>
          <button
            type="button"
            onClick={() => handleModeChange('WEALTH_PROJECTION')}
            aria-pressed={configMode === 'WEALTH_PROJECTION'}
            className={`px-3 py-1.5 text-xs font-semibold rounded transition flex items-center gap-1.5 ${
              configMode === 'WEALTH_PROJECTION'
                ? 'bg-brand text-white shadow-sm'
                : 'text-muted hover:text-secondary'
            }`}
          >
            Wealth Projection (Multi-Asset)
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6 text-xs">
        {/* SECTION 1: Portfolio Inputs */}
        <div className="space-y-3">
          <div className="text-xs font-bold text-ink uppercase flex items-center gap-2 border-b border-line pb-1.5">
            <span>Portfolio Inputs</span>
            <span className="text-muted text-[10px] font-normal">(Valuation & Exposure Scope)</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3">
            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Portfolio Selector</label>
              <select
                value={portfolioSelector}
                onChange={(e) => setPortfolioSelector(e.target.value)}
                className="w-64 bg-canvas border border-line rounded px-3 py-1.5 text-secondary"
              >
                <option value="Global Equity Long/Short">Global Equity Long/Short</option>
                <option value="US Quantitative Equity">US Quantitative Equity</option>
                <option value="India Alpha Long-Only">India Alpha Long-Only</option>
                <option value="Cross-Border High Conviction">Cross-Border High Conviction</option>
              </select>
            </div>

            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Portfolio Valuation</label>
              <input
                type="text"
                readOnly
                value={portfolioValuationSource}
                className="w-64 bg-subtle/60 border border-line rounded px-3 py-1.5 text-muted font-sans"
              />
            </div>

            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Position Selection</label>
              <select
                value={positionSelection}
                onChange={(e) => setPositionSelection(e.target.value)}
                className="w-64 bg-canvas border border-line rounded px-3 py-1.5 text-secondary"
              >
                <option value="All Holdings">All Holdings (Indian + US Equities)</option>
                <option value="Indian Equities Only">Indian Equities Only (NSE / BSE)</option>
                <option value="US Equities Only">US Equities Only (NYSE / NASDAQ)</option>
                <option value="Selected Custom Core">Selected Holdings Core</option>
              </select>
            </div>

            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Benchmark Selector</label>
              <select
                value={benchmark}
                onChange={(e) => setBenchmark(e.target.value)}
                className="w-64 bg-canvas border border-line rounded px-3 py-1.5 text-secondary"
              >
                <option value="SPY">SPY (S&P 500 ETF)</option>
                <option value="NIFTY 50">NIFTY 50 (National Stock Exchange Index)</option>
                <option value="MSCI ACWI">MSCI ACWI (All Country World Index)</option>
                <option value="CUSTOM_BLENDED">Custom 50% NIFTY / 50% SPY</option>
              </select>
            </div>

            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Currency & Valuation Timestamp</label>
              <input
                type="text"
                readOnly
                value={currencyTimestamp}
                className="w-64 bg-subtle/60 border border-line rounded px-3 py-1.5 text-muted font-sans"
              />
            </div>
          </div>
        </div>

        {/* SECTION 2: Simulation Parameters */}
        <div className="space-y-3">
          <div className="text-xs font-bold text-ink uppercase flex items-center gap-2 border-b border-line pb-1.5">
            <span>Simulation Parameters</span>
            <span className="text-muted text-[10px] font-normal">(Horizon & Engine Setup)</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3">
            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium flex items-center gap-1">
                Holding Period (Horizon)
                <HelpCircle className="size-3 text-muted" />
              </label>
              <select
                value={holdingPeriodDays}
                onChange={(e) => setHoldingPeriodDays(Number(e.target.value))}
                className="w-64 bg-canvas border border-line rounded px-3 py-1.5 text-secondary font-sans font-semibold"
              >
                <option value={1}>1 Trading Day (Short-Term Market Risk)</option>
                <option value={5}>5 Trading Days (Weekly Risk)</option>
                <option value={10}>10 Trading Days (Two-Week Risk)</option>
                <option value={20}>20 Trading Days (Monthly Horizon)</option>
                <option value={252}>252 Trading Days (1-Year Strategic)</option>
                <option value={7560}>7,560 Trading Days (30-Year Wealth Projection)</option>
              </select>
            </div>

            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Simulation Model</label>
              <select
                value={simulationModel}
                onChange={(e) => setSimulationModel(e.target.value)}
                className="w-64 bg-canvas border border-line rounded px-3 py-1.5 text-secondary"
              >
                <option value="Student-t (Heavy Tail)">Student-t (Heavy Tail Copula)</option>
                <option value="Historical Returns">Historical Resampling (Non-Parametric)</option>
                <option value="Parametric">Parametric (Multivariate Normal)</option>
                <option value="Bootstrap">Circular Block Bootstrap</option>
              </select>
            </div>

            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Number of Simulations</label>
              <select
                value={numSimulations}
                onChange={(e) => setNumSimulations(Number(e.target.value))}
                className="w-64 bg-canvas border border-line rounded px-3 py-1.5 text-secondary font-sans"
              >
                <option value={1000}>1,000 Paths (Fast Exploratory)</option>
                <option value={2000}>2,000 Paths (Standard High Precision)</option>
                <option value={5000}>5,000 Paths (Institutional Rigor)</option>
                <option value={10000}>10,000 Paths (Regulatory Tier 1)</option>
              </select>
            </div>

            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Historical Lookback Period</label>
              <select
                value={lookbackPeriod}
                onChange={(e) => setLookbackPeriod(e.target.value)}
                className="w-64 bg-canvas border border-line rounded px-3 py-1.5 text-secondary"
              >
                <option value="252 Trading Days (1 Year)">252 Trading Days (1 Year)</option>
                <option value="504 Trading Days (2 Years)">504 Trading Days (2 Years)</option>
                <option value="1260 Trading Days (5 Years)">1,260 Trading Days (5 Years)</option>
                <option value="Full History">Full Available History (Unconstrained)</option>
              </select>
            </div>

            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Return Frequency</label>
              <select
                value={returnFrequency}
                onChange={(e) => setReturnFrequency(e.target.value)}
                className="w-64 bg-canvas border border-line rounded px-3 py-1.5 text-secondary"
              >
                <option value="Daily">Daily Steps</option>
                <option value="Weekly">Weekly Aggregated Steps</option>
                <option value="Monthly">Monthly Steps</option>
              </select>
            </div>

            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Random Seed (PCG64)</label>
              <input
                type="number"
                value={randomSeed}
                onChange={(e) => setRandomSeed(Number(e.target.value))}
                className="w-64 bg-canvas border border-line rounded px-3 py-1.5 text-secondary font-sans"
              />
            </div>

            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Confidence Level</label>
              <select
                value={confidenceLevel}
                onChange={(e) => setConfidenceLevel(Number(e.target.value))}
                className="w-64 bg-canvas border border-line rounded px-3 py-1.5 text-secondary font-sans"
              >
                <option value={95}>95% Confidence (Basel Standard)</option>
                <option value={99}>99% Confidence (Extreme Downside Tail)</option>
                <option value={97.5}>97.5% Confidence (FRTB ES Standard)</option>
              </select>
            </div>
          </div>
        </div>

        {/* SECTION 3: Risk Assumptions */}
        <div className="space-y-3">
          <div className="text-xs font-bold text-ink uppercase flex items-center gap-2 border-b border-line pb-1.5">
            <span>Risk Assumptions</span>
            <span className="text-muted text-[10px] font-normal">(Vol, Correlation & Market Regimes)</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-3">
            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Volatility Assumptions</label>
              <select
                value={volatilityAssumption}
                onChange={(e) => setVolatilityAssumption(e.target.value)}
                className="w-64 bg-canvas border border-line rounded px-3 py-1.5 text-secondary"
              >
                <option value="Realized Historical Volatility">Realized Historical Volatility</option>
                <option value="EWMA Stressed Volatility">EWMA Stressed Volatility (Lambda 0.94)</option>
                <option value="VIX / India VIX Implied Scaling">VIX / India VIX Implied Scaling</option>
              </select>
            </div>

            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Correlation Assumptions</label>
              <select
                value={correlationAssumption}
                onChange={(e) => setCorrelationAssumption(e.target.value)}
                className="w-64 bg-canvas border border-line rounded px-3 py-1.5 text-secondary"
              >
                <option value="Empirical Higham-Repaired Correlation">Empirical Higham-Repaired Matrix</option>
                <option value="Crisis Correlation (+0.30 Breakdown)">Crisis Stressed (+0.30 Co-movement)</option>
                <option value="Zero Cross-Border Correlation">Zero Cross-Border Correlation</option>
              </select>
            </div>

            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Factor Shock Assumptions</label>
              <select
                value={factorShockAssumption}
                onChange={(e) => setFactorShockAssumption(e.target.value)}
                className="w-64 bg-canvas border border-line rounded px-3 py-1.5 text-secondary"
              >
                <option value="None (Full Covariance)">None (Full Covariance)</option>
                <option value="Tech Momentum Crash (-15%)">Tech Momentum Shock (-15%)</option>
                <option value="FX INR Depreciation (+5%)">FX USD/INR Surge (+5%)</option>
              </select>
            </div>

            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Liquidity & Slippage</label>
              <select
                value={liquidityShockAssumption}
                onChange={(e) => setLiquidityShockAssumption(e.target.value)}
                className="w-64 bg-canvas border border-line rounded px-3 py-1.5 text-secondary"
              >
                <option value="Standard Execution Haircut">Standard Tiered Liquidity Haircut</option>
                <option value="Extreme Illiquidity (2x Spread)">Extreme Market Illiquidity (2x Spread)</option>
                <option value="Zero Slippage (Frictionless)">Zero Slippage (Frictionless)</option>
              </select>
            </div>

            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Transaction Cost Model</label>
              <div className="relative w-64">
                <input
                  type="number"
                  step="0.5"
                  value={transactionCostBps}
                  onChange={(e) => setTransactionCostBps(Number(e.target.value))}
                  className="w-full bg-canvas border border-line rounded px-3 py-1.5 text-secondary font-sans"
                />
                <span className="absolute right-3 top-1.5 text-muted text-[11px]">bps</span>
              </div>
            </div>

            <div className="flex items-center justify-between gap-4">
              <label className="text-secondary font-medium">Market Regime</label>
              <select
                value={marketRegime}
                onChange={(e) => setMarketRegime(e.target.value)}
                className="w-64 bg-canvas border border-line rounded px-3 py-1.5 text-secondary"
              >
                <option value="Current Regime">Current Regime (Baseline Drift)</option>
                <option value="High Volatility Regime">High Volatility / Bear Drift</option>
                <option value="Sideways / High Dispersion">Sideways / Sector Rotation</option>
              </select>
            </div>
          </div>
        </div>

        {/* SECTION 4: Multi-Asset Holdings Breakdown */}
        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-line pb-1.5 gap-2">
            <div className="text-xs font-bold text-ink uppercase flex items-center gap-2">
              <span>
                {configMode === 'INSTITUTIONAL'
                  ? 'M05 Cross-Market Equity Portfolio Exposures'
                  : 'Multi-Asset Wealth Allocation Sleeves'}
              </span>
              <span className={`text-[11px] font-sans font-bold px-2 py-0.5 rounded ${
                Math.abs(totalAllocation - 100) < 0.1 ? 'bg-positive-soft text-positive' : 'bg-warning-soft text-warning'
              }`}>
                Total: {totalAllocation.toFixed(1)}%
              </span>
            </div>

            {/* Global Stock Search / Add Asset Input */}
            <div className="relative">
              <div className="flex items-center gap-1.5">
                <input
                  type="text"
                  placeholder="Search global stocks (e.g. AAPL, TSLA, RELIANCE)..."
                  value={searchQuery}
                  onChange={(e) => handleSearchTickers(e.target.value)}
                  onFocus={() => { if (searchResults.length > 0) setShowSearchDropdown(true); }}
                  className="w-72 bg-canvas border border-line rounded px-2.5 py-1 text-xs text-ink placeholder:text-muted focus:outline-none focus:border-brand"
                />
                {isSearching && <RefreshCw className="size-3 animate-spin text-muted" />}
              </div>

              {/* Autocomplete Dropdown */}
              {showSearchDropdown && searchResults.length > 0 && (
                <div className="absolute right-0 top-full mt-1 w-80 bg-surface border border-line-strong rounded-lg shadow-2xl z-50 max-h-56 overflow-y-auto">
                  <div className="p-1.5 text-[10px] uppercase font-bold text-muted border-b border-line">
                    Global Market Search Results
                  </div>
                  {searchResults.map((item) => (
                    <button
                      key={item.symbol}
                      type="button"
                      onClick={() => addAsset(item.symbol, item.name, item.exchange)}
                      className="w-full text-left px-3 py-2 text-xs hover:bg-hover flex items-center justify-between border-b border-line/40 last:border-0"
                    >
                      <div>
                        <div className="font-bold text-ink">{item.symbol}</div>
                        <div className="text-[11px] text-muted truncate max-w-[200px]">{item.name}</div>
                      </div>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-subtle text-secondary font-mono">
                        {item.exchange || 'EQUITY'}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Quick-Add Watchlist / Market Movers Pills */}
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[10px] text-muted uppercase font-bold mr-1">Quick Add:</span>
            {popularPresets.map((preset) => (
              <button
                key={preset.symbol}
                type="button"
                onClick={() => addAsset(preset.symbol, preset.name)}
                className="text-[10px] font-sans px-2 py-0.5 rounded bg-subtle hover:bg-hover border border-line text-secondary hover:text-ink transition flex items-center gap-1"
              >
                <Plus className="size-2.5" />
                {preset.symbol}
              </button>
            ))}
          </div>

          <div className="space-y-2">
            {assets.map((asset) => (
              <div key={asset.id} className="flex items-center gap-3 bg-canvas/40 p-2 rounded border border-line">
                <span className="flex-1 font-mono text-secondary font-semibold">{asset.name}</span>
                <div className="flex items-center gap-1.5 w-32">
                  <input
                    type="number"
                    value={asset.pct}
                    onChange={(e) => handlePctChange(asset.id, e.target.value)}
                    className="w-20 bg-canvas border border-line rounded px-2 py-1 text-right font-sans font-semibold text-ink"
                  />
                  <span className="text-muted">%</span>
                </div>
                <button
                  type="button"
                  onClick={() => removeAsset(asset.id)}
                  title="Remove asset"
                  className="p-1 rounded text-muted hover:text-negative hover:bg-negative-soft transition"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Execution Controls Toolbar */}
        <div className="border-t border-line pt-4 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={isRunning}
              className="px-5 py-2 rounded-lg bg-brand hover:bg-brand-hover text-white font-bold text-xs flex items-center gap-2 shadow-sm transition disabled:opacity-50"
            >
              {isRunning ? <RefreshCw className="size-3.5 animate-spin" /> : <Play className="size-3.5 fill-current" />}
              {isRunning ? 'Simulating Engine...' : 'Run Simulation'}
            </button>

            <button
              type="button"
              onClick={() => notify('Configuration saved as institutional template.')}
              className="px-3 py-2 rounded-lg bg-subtle hover:bg-hover border border-line-strong text-secondary font-medium text-xs flex items-center gap-1.5 transition"
            >
              <Save className="size-3.5 text-muted" />
              Save Configuration
            </button>

            <button
              type="button"
              onClick={onCompareResults}
              disabled={isRunning || !canCompareResults}
              aria-describedby={!canCompareResults ? 'simulation-comparison-help' : undefined}
              className="px-3 py-2 rounded-lg bg-subtle hover:bg-hover border border-line-strong text-secondary font-medium text-xs flex items-center gap-1.5 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <GitCompare className="size-3.5 text-muted" />
              Compare Results
            </button>
          </div>

          <button
            type="button"
            onClick={handleReset}
            disabled={isRunning}
            className="px-3 py-2 rounded-lg bg-subtle hover:bg-hover border border-line text-muted hover:text-secondary text-xs flex items-center gap-1.5 transition"
          >
            <RotateCcw className="size-3.5" />
            Reset Configuration
          </button>
        </div>
        {!canCompareResults && <p id="simulation-comparison-help" className="text-xs text-muted">Run two simulations to compare their results. The latest two successful runs are kept for this portfolio during this session.</p>}
      </form>
    </div>
  );
};
