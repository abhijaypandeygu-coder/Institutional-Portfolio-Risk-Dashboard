import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
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
  BarChart3,
  SlidersHorizontal,
  RefreshCw,
  FolderOpen
} from 'lucide-react';
import { ErrorBoundary } from './components/ErrorBoundary';
import { ExternalProvidersPage } from './modules/dashboard/ExternalProvidersPage';
import { PortfolioOverviewPage } from './modules/dashboard/portfolio-overview/PortfolioOverviewPage';
import { AlertsDashboardPage } from './modules/dashboard/alerts-dashboard/AlertsDashboardPage';
import { LiquidityDashboardPage } from './modules/dashboard/liquidity-dashboard/LiquidityDashboardPage';
import { StressTestingDashboardPage } from './modules/dashboard/stress-dashboard/StressTestingDashboardPage';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'alerts' | 'liquidity' | 'stress' | 'providers'>('overview');
  const [timeRange, setTimeRange] = useState<'1D' | '1W' | '1M' | '3M' | '6M' | '1Y' | 'All'>('1Y');
  const [selectedPortfolio, setSelectedPortfolio] = useState<string>('PORT_ALR_b16421');
  const [portfolioList, setPortfolioList] = useState<Array<{ portfolio_id: string; portfolio_name: string }>>([]);
  const [showEngineDetails, setShowEngineDetails] = useState<boolean>(false);

  useEffect(() => {
    fetch('/api/v1/portfolios?limit=20')
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setPortfolioList(data);
          setSelectedPortfolio(data[0].portfolio_id);
        }
      })
      .catch(() => {});
  }, []);

  const marketWatch = [
    { symbol: 'AAPL', name: 'Apple Inc.', price: '$191.45', change: '+1.25%', up: true },
    { symbol: 'GOOGL', name: 'Alphabet Inc.', price: '$163.85', change: '+0.85%', up: true },
    { symbol: 'AMZN', name: 'Amazon.com', price: '$179.32', change: '+2.31%', up: true },
    { symbol: 'MSFT', name: 'Microsoft Corp.', price: '$415.59', change: '+0.92%', up: true },
    { symbol: 'TSLA', name: 'Tesla, Inc.', price: '$171.21', change: '-0.45%', up: false },
  ];

  const topHoldings = [
    { symbol: 'AAPL', name: 'Apple Inc.', pct: '23.5%', notional: '$30,215.30', bg: 'bg-emerald-500' },
    { symbol: 'MSFT', name: 'Microsoft Corp.', pct: '18.7%', notional: '$24,070.45', bg: 'bg-cyan-500' },
    { symbol: 'AMZN', name: 'Amazon.com', pct: '15.3%', notional: '$19,690.20', bg: 'bg-amber-500' },
    { symbol: 'VOO', name: 'Vanguard S&P 500 ETF', pct: '12.1%', notional: '$15,590.50', bg: 'bg-indigo-500' },
    { symbol: 'TSLA', name: 'Tesla, Inc.', pct: '8.9%', notional: '$11,449.10', bg: 'bg-rose-500' },
  ];

  const recentTransactions = [
    { symbol: 'AAPL', title: 'Apple Inc. (AAPL)', subtitle: 'Buy 2 Shares • May 18, 2026', amount: '-$382.90', isNegative: true },
    { symbol: 'MSFT', title: 'Dividend from Microsoft', subtitle: 'May 17, 2026', amount: '+$50.25', isNegative: false },
    { symbol: 'VOO', title: 'Vanguard S&P 500 ETF', subtitle: 'Buy 1 Share • May 16, 2026', amount: '-$410.50', isNegative: true },
    { symbol: 'USD', title: 'Interest from Cash Reserve', subtitle: 'May 15, 2026', amount: '+$12.35', isNegative: false },
  ];

  const upcomingEvents = [
    { title: 'Fed Interest Rate Decision', date: 'May 21, 2026', tag: 'MACRO', color: 'text-purple-400 bg-purple-950/60 border-purple-800/40' },
    { title: 'Earnings Report — NVIDIA', date: 'May 28, 2026', tag: 'EARNINGS', color: 'text-emerald-400 bg-emerald-950/60 border-emerald-800/40' },
    { title: 'US Non-Farm Payrolls (Jobs Report)', date: 'June 6, 2026', tag: 'EMPLOYMENT', color: 'text-amber-400 bg-amber-950/60 border-amber-800/40' },
  ];

  return (
    <div className="min-h-screen bg-[#080B10] text-slate-100 font-sans flex flex-col selection:bg-emerald-500/30 selection:text-emerald-300">
      {/* 1. FinSight Institutional Top Navigation */}
      <header className="sticky top-0 z-50 backdrop-blur-md bg-[#080B10]/95 border-b border-[#181F2C] px-6 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-8">
          {/* Brand Logo */}
          <div className="flex items-center gap-2.5 cursor-pointer" onClick={() => setActiveTab('overview')}>
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-emerald-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <Activity className="w-5 h-5 text-[#080B10] stroke-[2.5]" />
            </div>
            <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
              FinSight
            </span>
            <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              M15 Risk
            </span>
          </div>

          {/* Clean Module Tabs */}
          <nav className="flex items-center gap-1.5 bg-[#0D121C] p-1 rounded-xl border border-[#182030]">
            {[
              { id: 'overview', label: 'Executive Dashboard' },
              { id: 'alerts', label: 'Risk Alerts' },
              { id: 'liquidity', label: 'Liquidity Analytics' },
              { id: 'stress', label: 'Stress Testing' },
              { id: 'providers', label: 'Data Feeds' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 ${
                  activeTab === tab.id
                    ? 'bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-[#141B26]'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Global Controls & User Profile */}
        <div className="flex items-center gap-4">
          {/* Portfolio Selector dropdown directly in header */}
          <div className="flex items-center gap-2 bg-[#0D121C] border border-[#182030] rounded-xl px-3 py-1.5">
            <FolderOpen className="w-3.5 h-3.5 text-emerald-400" />
            <select
              value={selectedPortfolio}
              onChange={(e) => setSelectedPortfolio(e.target.value)}
              className="bg-transparent text-xs font-semibold text-slate-200 focus:outline-none cursor-pointer"
            >
              {portfolioList.map((p) => (
                <option key={p.portfolio_id} value={p.portfolio_id} className="bg-[#0D121C] text-slate-200">
                  {p.portfolio_name} ({p.portfolio_id})
                </option>
              ))}
            </select>
          </div>

          <div className="relative hidden md:block">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search ticker, ISIN, factor..."
              className="pl-9 pr-4 py-1.5 bg-[#0D121C] border border-[#182030] rounded-xl text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-emerald-500/50 w-52 transition-all"
            />
          </div>

          <button className="relative p-2 rounded-xl bg-[#0D121C] border border-[#182030] text-slate-400 hover:text-slate-200 hover:border-slate-700 transition">
            <Bell className="w-4 h-4" />
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-emerald-400 ring-2 ring-[#080B10]"></span>
          </button>

          <div className="flex items-center gap-2.5 pl-2 border-l border-[#182030]">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-500 to-emerald-400 p-[1.5px] cursor-pointer">
              <div className="w-full h-full rounded-full bg-[#101622] flex items-center justify-center font-bold text-xs text-emerald-400">
                OR
              </div>
            </div>
            <div className="flex flex-col text-left">
              <span className="text-xs font-semibold text-slate-200 leading-tight">Olivia Rhye</span>
              <span className="text-[10px] text-emerald-400/90 font-medium">Head of Risk</span>
            </div>
          </div>
        </div>
      </header>

      {/* 2. Page Content */}
      <main className="flex-1 px-6 py-6 max-w-[1600px] w-full mx-auto space-y-6">
        {/* Sub-pages: Risk Alerts, Liquidity, Stress, Providers */}
        {activeTab !== 'overview' && (
          <div className="bg-[#0D121C] border border-[#182030] rounded-2xl p-6 shadow-2xl">
            <ErrorBoundary fallbackTitle="Module View Error">
              {activeTab === 'alerts' && <AlertsDashboardPage />}
              {activeTab === 'liquidity' && <LiquidityDashboardPage />}
              {activeTab === 'stress' && <StressTestingDashboardPage />}
              {activeTab === 'providers' && <ExternalProvidersPage />}
            </ErrorBoundary>
          </div>
        )}

        {/* Executive Dashboard Layout */}
        {activeTab === 'overview' && (
          <>
            {/* Top Bar: Title & Primary Controls */}
            <div className="flex flex-wrap items-center justify-between gap-4 pb-1">
              <div>
                <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
                  Dashboard Overview
                  <span className="text-xs font-medium text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded-md border border-emerald-800/50">
                    Live Session
                  </span>
                </h1>
                <p className="text-xs text-slate-400 mt-0.5">
                  Institutional portfolio performance, asset allocation, and underlying risk metrics.
                </p>
              </div>

              <div className="flex items-center gap-2.5">
                <button
                  onClick={() => setShowEngineDetails(!showEngineDetails)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition ${
                    showEngineDetails
                      ? 'bg-emerald-500 text-slate-950 border-emerald-400 shadow-md shadow-emerald-500/20'
                      : 'bg-[#0D121C] border-[#182030] text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <SlidersHorizontal className="w-3.5 h-3.5" />
                  <span>{showEngineDetails ? 'Hide Deep Risk Metrics' : 'Detailed Risk Breakdown'}</span>
                </button>

                <button className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#0D121C] border border-[#182030] text-xs font-medium text-slate-300 hover:border-slate-700 transition">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  <span>May 12 – May 18, 2026</span>
                  <ChevronDown className="w-3 h-3 text-slate-500" />
                </button>

                <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#0D121C] border border-[#182030] text-xs font-medium text-slate-300 hover:border-slate-700 transition">
                  <Share2 className="w-3.5 h-3.5 text-slate-400" />
                  <span>Export</span>
                </button>

                <button className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-emerald-500 to-cyan-500 text-xs font-bold text-slate-950 hover:brightness-110 shadow-lg shadow-emerald-500/20 transition">
                  <Plus className="w-3.5 h-3.5 stroke-[3]" />
                  <span>New Order / Allocation</span>
                </button>
              </div>
            </div>

            {/* Top 4 KPI Metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-[#0D121C] border border-[#182030] hover:border-emerald-500/40 transition-all rounded-2xl p-5 shadow-lg flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400">Total Portfolio Value</span>
                  <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                    <Wallet className="w-4 h-4 text-emerald-400" />
                  </div>
                </div>
                <div className="mt-4">
                  <div className="text-2xl font-bold tracking-tight text-white font-mono">$128,750.60</div>
                  <div className="flex items-center gap-1 mt-1.5 text-xs text-emerald-400 font-medium">
                    <ArrowUpRight className="w-3.5 h-3.5" />
                    <span>+5.21%</span>
                    <span className="text-slate-500 ml-1">vs last week</span>
                  </div>
                </div>
              </div>

              <div className="bg-[#0D121C] border border-[#182030] hover:border-cyan-500/40 transition-all rounded-2xl p-5 shadow-lg flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400">Total Gains</span>
                  <div className="w-8 h-8 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center">
                    <TrendingUp className="w-4 h-4 text-cyan-400" />
                  </div>
                </div>
                <div className="mt-4">
                  <div className="text-2xl font-bold tracking-tight text-white font-mono">$12,540.75</div>
                  <div className="flex items-center gap-1 mt-1.5 text-xs text-emerald-400 font-medium">
                    <ArrowUpRight className="w-3.5 h-3.5" />
                    <span>+8.75%</span>
                    <span className="text-slate-500 ml-1">vs last week</span>
                  </div>
                </div>
              </div>

              <div className="bg-[#0D121C] border border-[#182030] hover:border-purple-500/40 transition-all rounded-2xl p-5 shadow-lg flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400">Total Income</span>
                  <div className="w-8 h-8 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center">
                    <Layers className="w-4 h-4 text-purple-400" />
                  </div>
                </div>
                <div className="mt-4">
                  <div className="text-2xl font-bold tracking-tight text-white font-mono">$2,340.50</div>
                  <div className="flex items-center gap-1 mt-1.5 text-xs text-emerald-400 font-medium">
                    <ArrowUpRight className="w-3.5 h-3.5" />
                    <span>+3.18%</span>
                    <span className="text-slate-500 ml-1">vs last week</span>
                  </div>
                </div>
              </div>

              <div className="bg-[#0D121C] border border-[#182030] hover:border-amber-500/40 transition-all rounded-2xl p-5 shadow-lg flex flex-col justify-between">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400">Cash Balance</span>
                  <div className="w-8 h-8 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                    <Activity className="w-4 h-4 text-amber-400" />
                  </div>
                </div>
                <div className="mt-4">
                  <div className="text-2xl font-bold tracking-tight text-white font-mono">$8,954.30</div>
                  <div className="flex items-center gap-1 mt-1.5 text-xs text-rose-400 font-medium">
                    <ArrowDownRight className="w-3.5 h-3.5" />
                    <span>-1.23%</span>
                    <span className="text-slate-500 ml-1">vs last week</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Section 1: Portfolio Performance & Asset Allocation Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Performance Curve (Col 8) */}
              <div className="lg:col-span-8 bg-[#0D121C] border border-[#182030] rounded-2xl p-6 shadow-xl flex flex-col justify-between">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
                  <div>
                    <h2 className="text-base font-bold text-white flex items-center gap-2">
                      Portfolio Performance
                      <span className="text-[10px] text-slate-500 font-normal">Daily MTM Mark-to-Market</span>
                    </h2>
                  </div>

                  <div className="flex items-center bg-[#101622] border border-[#1E293B] rounded-xl p-1 gap-1">
                    {(['1D', '1W', '1M', '3M', '6M', '1Y', 'All'] as const).map((r) => (
                      <button
                        key={r}
                        onClick={() => setTimeRange(r)}
                        className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition ${
                          timeRange === r
                            ? 'bg-[#182232] text-emerald-400 shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {r}
                      </button>
                    ))}
                  </div>
                </div>

                {/* SVG Performance Line Graph */}
                <div className="relative w-full h-64 mt-2">
                  <svg className="w-full h-full overflow-visible" viewBox="0 0 800 240" preserveAspectRatio="none">
                    <defs>
                      <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#10b981" stopOpacity="0.25" />
                        <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>

                    <line x1="0" y1="40" x2="800" y2="40" stroke="#141B26" strokeDasharray="4 4" />
                    <line x1="0" y1="100" x2="800" y2="100" stroke="#141B26" strokeDasharray="4 4" />
                    <line x1="0" y1="160" x2="800" y2="160" stroke="#141B26" strokeDasharray="4 4" />
                    <line x1="0" y1="220" x2="800" y2="220" stroke="#141B26" strokeDasharray="4 4" />

                    <polygon
                      fill="url(#chartGradient)"
                      points="
                        0,200 
                        60,190 120,185 180,165 240,175 300,150 360,135 
                        420,140 480,110 540,115 600,90 660,95 720,70 780,60 800,55
                        800,240 0,240
                      "
                    />

                    <polyline
                      fill="none"
                      stroke="#10b981"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      points="
                        0,200 
                        60,190 120,185 180,165 240,175 300,150 360,135 
                        420,140 480,110 540,115 600,90 660,95 720,70 780,60 800,55
                      "
                    />

                    <circle cx="800" cy="55" r="5" fill="#10b981" className="animate-ping origin-center" />
                    <circle cx="800" cy="55" r="4" fill="#10b981" stroke="#080B10" strokeWidth="2" />
                  </svg>

                  <div className="absolute right-4 top-2 bg-[#101622]/95 border border-emerald-500/40 rounded-xl px-3 py-2 shadow-xl backdrop-blur-sm pointer-events-none">
                    <span className="text-[10px] text-slate-400 block font-medium">May 18, 2026</span>
                    <span className="text-sm font-bold text-white font-mono">$128,750.60</span>
                    <span className="text-[11px] text-emerald-400 font-semibold block mt-0.5">↑ +5.21%</span>
                  </div>

                  <div className="flex justify-between text-[11px] text-slate-500 font-mono mt-3">
                    <span>Jun 2025</span>
                    <span>Aug 2025</span>
                    <span>Oct 2025</span>
                    <span>Dec 2025</span>
                    <span>Feb 2026</span>
                    <span>Apr 2026</span>
                    <span>May 2026</span>
                  </div>
                </div>
              </div>

              {/* Asset Allocation Donut (Col 4) */}
              <div className="lg:col-span-4 bg-[#0D121C] border border-[#182030] rounded-2xl p-6 shadow-xl flex flex-col justify-between">
                <div className="flex items-center justify-between mb-1">
                  <h2 className="text-base font-bold text-white">Asset Allocation</h2>
                  <span className="text-xs text-slate-400 bg-[#101622] px-2.5 py-1 rounded-lg border border-[#1E293B]">
                    Multi-Asset
                  </span>
                </div>

                <div className="flex items-center justify-center my-3 relative">
                  <svg className="w-44 h-44 -rotate-90 transform" viewBox="0 0 100 100">
                    <circle cx="50" cy="50" r="38" stroke="#161F2E" strokeWidth="12" fill="none" />
                    <circle cx="50" cy="50" r="38" stroke="#10b981" strokeWidth="12" fill="none"
                      strokeDasharray="109 239" strokeDashoffset="0" />
                    <circle cx="50" cy="50" r="38" stroke="#06b6d4" strokeWidth="12" fill="none"
                      strokeDasharray="60 239" strokeDashoffset="-109" />
                    <circle cx="50" cy="50" r="38" stroke="#a855f7" strokeWidth="12" fill="none"
                      strokeDasharray="38 239" strokeDashoffset="-169" />
                    <circle cx="50" cy="50" r="38" stroke="#64748b" strokeWidth="12" fill="none"
                      strokeDasharray="21 239" strokeDashoffset="-207" />
                    <circle cx="50" cy="50" r="38" stroke="#f59e0b" strokeWidth="12" fill="none"
                      strokeDasharray="11 239" strokeDashoffset="-228" />
                  </svg>
                  
                  <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                    <span className="text-[10px] text-slate-400 uppercase font-medium">Total Value</span>
                    <span className="text-base font-bold text-white font-mono">$128,750</span>
                  </div>
                </div>

                <div className="space-y-1.5">
                  {[
                    { label: 'Stocks', pct: '45.6%', val: '$58,750', color: 'bg-emerald-500' },
                    { label: 'Bonds', pct: '25.3%', val: '$32,550', color: 'bg-cyan-500' },
                    { label: 'ETFs', pct: '15.8%', val: '$20,350', color: 'bg-purple-500' },
                    { label: 'Real Estate', pct: '8.7%', val: '$11,200', color: 'bg-slate-400' },
                    { label: 'Cash', pct: '4.6%', val: '$5,899', color: 'bg-amber-500' },
                  ].map((item) => (
                    <div key={item.label} className="flex items-center justify-between text-xs py-0.5">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${item.color}`} />
                        <span className="text-slate-300 font-medium">{item.label}</span>
                      </div>
                      <div className="flex items-center gap-3 font-mono">
                        <span className="text-slate-400">{item.pct}</span>
                        <span className="text-slate-200 font-semibold">{item.val}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Section 2: Market Watch Strip */}
            <div className="bg-[#0D121C] border border-[#182030] rounded-2xl p-4 shadow-xl">
              <div className="flex items-center justify-between mb-3 px-1">
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                  <Activity className="w-3.5 h-3.5 text-emerald-400" />
                  Live Market Watch
                </span>
                <span className="text-[11px] text-slate-500 font-mono">Real-time Quotes</span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                {marketWatch.map((item) => (
                  <div
                    key={item.symbol}
                    className="bg-[#101622] border border-[#182030] hover:border-slate-700 rounded-xl p-3 flex flex-col justify-between transition cursor-pointer group"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-xs font-bold text-white group-hover:text-emerald-400 transition">{item.symbol}</div>
                        <div className="text-[10px] text-slate-500 truncate max-w-[100px]">{item.name}</div>
                      </div>
                      <span className={`text-[11px] font-semibold font-mono ${item.up ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {item.change}
                      </span>
                    </div>

                    <div className="mt-2 text-xs font-bold font-mono text-slate-200">
                      {item.price}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Section 3: Recent Transactions | Top Holdings | Upcoming Events */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-[#0D121C] border border-[#182030] rounded-2xl p-5 shadow-xl flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-bold text-white">Recent Transactions</h3>
                    <button className="text-[11px] font-semibold text-emerald-400 hover:text-emerald-300">View All</button>
                  </div>

                  <div className="space-y-3">
                    {recentTransactions.map((tx, idx) => (
                      <div key={idx} className="flex items-center justify-between py-1.5 border-b border-[#141B26] last:border-none">
                        <div>
                          <div className="text-xs font-semibold text-slate-200">{tx.title}</div>
                          <div className="text-[10px] text-slate-500">{tx.subtitle}</div>
                        </div>
                        <span className={`text-xs font-bold font-mono ${tx.isNegative ? 'text-slate-300' : 'text-emerald-400'}`}>
                          {tx.amount}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="bg-[#0D121C] border border-[#182030] rounded-2xl p-5 shadow-xl flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-bold text-white">Top Holdings</h3>
                    <button className="text-[11px] font-semibold text-emerald-400 hover:text-emerald-300">View All</button>
                  </div>

                  <div className="space-y-3">
                    {topHoldings.map((h) => (
                      <div key={h.symbol} className="flex items-center justify-between py-1 border-b border-[#141B26] last:border-none">
                        <div className="flex items-center gap-2.5">
                          <div>
                            <div className="text-xs font-semibold text-slate-200">{h.name}</div>
                            <div className="w-24 bg-[#141B26] h-1.5 rounded-full mt-1 overflow-hidden">
                              <div className={`h-full ${h.bg}`} style={{ width: h.pct }}></div>
                            </div>
                          </div>
                        </div>

                        <div className="text-right font-mono">
                          <div className="text-xs font-bold text-slate-200">{h.notional}</div>
                          <div className="text-[10px] text-slate-500">{h.pct}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="bg-[#0D121C] border border-[#182030] rounded-2xl p-5 shadow-xl flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-bold text-white">Upcoming Events</h3>
                    <button className="text-[11px] font-semibold text-emerald-400 hover:text-emerald-300">Calendar</button>
                  </div>

                  <div className="space-y-3">
                    {upcomingEvents.map((evt, idx) => (
                      <div key={idx} className="p-3 rounded-xl bg-[#101622] border border-[#182030] flex items-start gap-3">
                        <div className="p-2 rounded-lg bg-[#141B26] text-slate-300">
                          <Calendar className="w-4 h-4 text-emerald-400" />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold text-slate-200">{evt.title}</span>
                            <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border ${evt.color}`}>
                              {evt.tag}
                            </span>
                          </div>
                          <span className="text-[11px] text-slate-500 block mt-1">{evt.date}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Section 4: Authoritative Risk Breakdown (Collapsible / Toggleable) */}
            {showEngineDetails && (
              <div className="bg-[#0D121C] border border-emerald-500/30 rounded-2xl p-6 shadow-2xl transition-all">
                <div className="flex items-center justify-between border-b border-[#182030] pb-4 mb-4">
                  <div>
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-emerald-400" />
                      Authoritative Risk Engine — Deep Breakdown
                    </h3>
                    <p className="text-xs text-slate-400">
                      M05.03 Valuation, M06 Exposure Limits, and M07 Market Risk Metrics
                    </p>
                  </div>
                  <button
                    onClick={() => setShowEngineDetails(false)}
                    className="text-xs text-slate-400 hover:text-slate-200 bg-[#101622] px-3 py-1 rounded-lg border border-[#182030]"
                  >
                    Close Breakdown
                  </button>
                </div>
                <PortfolioOverviewPage portfolioId={selectedPortfolio} />
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
};
