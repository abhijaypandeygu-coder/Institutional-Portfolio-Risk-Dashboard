import { ModalSurface } from './ModalSurface';
import React, { useState, useEffect } from 'react';
import { 
  X, 
  Plus, 
  ShieldCheck, 
  ShieldAlert, 
  AlertTriangle, 
  CheckCircle2, 
  Loader2, 
  TrendingUp, 
  ArrowRight,
  Layers,
  Search,
  Globe,
  RefreshCw
} from 'lucide-react';

interface OrderModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedPortfolio: string;
  portfolioList: Array<{ portfolio_id: string; portfolio_name: string }>;
  onOrderSuccess?: (portfolioId: string) => void;
}

interface ValidationCheckResult {
  check_name: string;
  check_category: string;
  check_status: 'PASS' | 'WARNING' | 'FAIL' | 'REVIEW_REQUIRED';
  current_value: string;
  projected_value: string;
  effective_limit: string;
  utilization_percentage: string;
  unit: string;
  source_module?: string;
  reason_code?: string;
}

export const OrderAllocationModal: React.FC<OrderModalProps> = ({
  isOpen,
  onClose,
  selectedPortfolio,
  portfolioList,
  onOrderSuccess,
}) => {
  const [targetPortfolio, setTargetPortfolio] = useState<string>(selectedPortfolio || 'PORT_STR_a74557');
  const [ticker, setTicker] = useState<string>('AAPL');
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY');
  const [orderType, setOrderType] = useState<'MARKET' | 'LIMIT'>('LIMIT');
  const [quantity, setQuantity] = useState<number>(50);
  const [limitPrice, setLimitPrice] = useState<number>(185.50);
  const [exchange, setExchange] = useState<string>('NASDAQ');
  
  // Keep targetPortfolio in sync with parent prop
  useEffect(() => {
    if (selectedPortfolio) {
      setTargetPortfolio(selectedPortfolio);
    }
  }, [selectedPortfolio]);

  // Market Selection & Ticker Search state
  const [marketTab, setMarketTab] = useState<'ALL' | 'INDIAN' | 'US' | 'OTHER'>('ALL');
  const [tickerQuery, setTickerQuery] = useState('');
  const [tickerSearchResults, setTickerSearchResults] = useState<Array<{ symbol: string; name: string; exchange?: string; sector?: string }>>([]);
  const [isSearchingTickers, setIsSearchingTickers] = useState(false);
  const [showTickerDropdown, setShowTickerDropdown] = useState(false);

  // Quick select presets across global markets
  const marketPresets = {
    INDIAN: [
      { symbol: 'RELIANCE.NS', name: 'Reliance Industries', exchange: 'NSE', price: 2500.0 },
      { symbol: 'TCS.NS', name: 'Tata Consultancy Services', exchange: 'NSE', price: 3500.0 },
      { symbol: 'HDFCBANK.NS', name: 'HDFC Bank', exchange: 'NSE', price: 1650.0 },
      { symbol: 'INFY.NS', name: 'Infosys Ltd', exchange: 'NSE', price: 1550.0 },
      { symbol: 'ICICIBANK.NS', name: 'ICICI Bank', exchange: 'NSE', price: 1050.0 },
    ],
    US: [
      { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ', price: 185.50 },
      { symbol: 'NVDA', name: 'NVIDIA Corporation', exchange: 'NASDAQ', price: 135.00 },
      { symbol: 'MSFT', name: 'Microsoft Corp.', exchange: 'NASDAQ', price: 420.00 },
      { symbol: 'AMZN', name: 'Amazon.com Inc.', exchange: 'NASDAQ', price: 190.00 },
      { symbol: 'TSLA', name: 'Tesla Inc.', exchange: 'NASDAQ', price: 215.00 },
    ],
    OTHER: [
      { symbol: 'GLD', name: 'SPDR Gold Trust ETF', exchange: 'ARCA', price: 240.00 },
      { symbol: 'SPY', name: 'SPDR S&P 500 ETF Trust', exchange: 'NYSE', price: 540.00 },
      { symbol: 'AAPL.TO', name: 'Apple CDR (CAD Hedged)', exchange: 'TOR', price: 32.50 },
    ]
  };

  const handleSearchTickers = async (q: string) => {
    setTickerQuery(q);
    if (!q || q.trim().length < 1) {
      setTickerSearchResults([]);
      setShowTickerDropdown(false);
      return;
    }
    setIsSearchingTickers(true);
    try {
      const res = await fetch(`/api/v1/dashboard/liquidity/search-tickers?q=${encodeURIComponent(q.trim())}&limit=8`);
      if (res.ok) {
        const data = await res.json();
        setTickerSearchResults(Array.isArray(data) ? data : []);
        setShowTickerDropdown(true);
      }
    } catch (err) {
      console.error('Ticker search failed', err);
    } finally {
      setIsSearchingTickers(false);
    }
  };

  const selectTicker = (sym: string, ex?: string, defaultPx?: number) => {
    setTicker(sym.toUpperCase());
    if (ex) setExchange(ex.toUpperCase());
    else if (sym.toUpperCase().endsWith('.NS') || sym.toUpperCase().endsWith('.BO')) setExchange('NSE');
    else setExchange('NASDAQ');
    if (defaultPx) setLimitPrice(defaultPx);
    setShowTickerDropdown(false);
    setTickerQuery('');
  };
  
  const [step, setStep] = useState<'input' | 'evaluated' | 'confirmed'>('input');
  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [decisionResponse, setDecisionResponse] = useState<any>(null);
  const [executionResult, setExecutionResult] = useState<any>(null);

  if (!isOpen) return null;

  const handleEvaluate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsEvaluating(true);
    setErrorMsg(null);

    const payload = {
      portfolio_id: targetPortfolio,
      instrument_id: ticker.toUpperCase().trim(),
      listing_id: `${ticker.toUpperCase().trim()}.OQ`,
      exchange: exchange,
      side: side,
      quantity: Number(quantity),
      order_type: orderType,
      limit_price: orderType === 'LIMIT' ? Number(limitPrice) : undefined,
      time_in_force: 'DAY',
      currency: 'USD',
      submitting_user_id: 'risk_desk_trader',
      originating_system: 'PORTFOLIO_DESK_UI',
    };

    try {
      const res = await fetch('/api/v1/pretrade/orders/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error?.message || `Order evaluation failed (${res.status})`);
      }

      const data = await res.json();
      setDecisionResponse(data);
      setStep('evaluated');
    } catch (err: any) {
      setErrorMsg(err.message || 'Error communicating with pre-trade risk engine');
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleConfirmOrder = async () => {
    setIsExecuting(true);
    setErrorMsg(null);

    // Register Position Event into the portfolio database
    const eventType = side === 'BUY' ? 'TRADE_BUY' : 'TRADE_SELL';
    const signedDelta = side === 'BUY' ? Number(quantity) : -Number(quantity);

    const payload = {
      portfolio_id: targetPortfolio,
      account_id: 'ACC_TRADING_01',
      instrument_id: ticker.toUpperCase().trim(),
      event_type: eventType,
      signed_quantity_delta: signedDelta,
      idempotency_key: `ORD_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      transaction_reference: decisionResponse?.order_id,
      source_system: 'PORTFOLIO_DESK_EXECUTION',
      reason: 'Desk order execution confirmed after pre-trade risk clearance',
    };

    try {
      const res = await fetch('/api/v1/positions/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error?.message || `Execution booking failed (${res.status})`);
      }

      const snap = await res.json();
      setExecutionResult(snap);
      setStep('confirmed');
      onOrderSuccess?.(targetPortfolio);
    } catch (err: any) {
      setErrorMsg(err.message || 'Execution failed');
    } finally {
      setIsExecuting(false);
    }
  };

  const handleReset = () => {
    setStep('input');
    setDecisionResponse(null);
    setExecutionResult(null);
    setErrorMsg(null);
  };

  const notional = (Number(quantity) * (orderType === 'LIMIT' ? Number(limitPrice) : 185.5)).toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
  });

  return (
    <ModalSurface open={isOpen} onClose={onClose} label="Order and allocation review" className="max-w-lg">
      <div 
        className="w-full min-w-0 bg-surface flex flex-col overflow-hidden text-ink"

      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-line/80 bg-surface/60">
          <div className="flex items-center gap-2.5">
            <div className="size-8 rounded-lg bg-brand/10 border border-emerald-500/20 flex items-center justify-center text-positive">
              <Plus className="size-4 stroke-[2.5]" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-ink">
                {step === 'input' && 'New Order / Portfolio Allocation'}
                {step === 'evaluated' && 'Pre-Trade Risk Clearance'}
                {step === 'confirmed' && 'Order Executed & Settled'}
              </h2>
              <p className="text-xs text-muted">
                {step === 'input' && 'Simulate, validate limits, and execute allocation'}
                {step === 'evaluated' && 'Review limit utilization and stress impact before execution'}
                {step === 'confirmed' && 'Position booked into authoritative ledger'}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close order and allocation review"
            className="size-8 rounded-lg flex items-center justify-center text-muted hover:text-secondary hover:bg-subtle transition-colors"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-4 overflow-y-auto max-h-[60dvh]">
          {errorMsg && (
            <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-negative text-xs">
              <ShieldAlert className="size-4 shrink-0" />
              <span role="alert">{errorMsg}</span>
            </div>
          )}

          {/* STEP 1: INPUT FORM */}
          {step === 'input' && (
            <form id="order-form" onSubmit={handleEvaluate} className="space-y-4">
              {/* Portfolio Select */}
              <div>
                <label htmlFor="orderallocationmodal-field-1" className="block text-xs font-semibold text-secondary mb-1.5">Target Portfolio</label>
                <select id="orderallocationmodal-field-1"
                  value={targetPortfolio}
                  onChange={(e) => setTargetPortfolio(e.target.value)}
                  className="w-full bg-canvas border border-line rounded-xl px-3 py-2 text-xs font-medium text-secondary focus:outline-none focus:border-line-strong"
                >
                  {portfolioList.map((p) => (
                    <option key={p.portfolio_id} value={p.portfolio_id}>
                      {p.portfolio_name} ({p.portfolio_id})
                    </option>
                  ))}
                </select>
              </div>

              {/* Market Selection Tabs & Global Stock Search */}
              <div className="space-y-2 pt-1 border-t border-line/60">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-secondary uppercase tracking-wider">Choose Market</span>
                  <div className="flex items-center gap-1 bg-canvas p-0.5 rounded-lg border border-line">
                    <button
                      type="button"
                      onClick={() => setMarketTab('ALL')}
                      className={`px-2 py-0.5 text-[10px] font-medium rounded ${marketTab === 'ALL' ? 'bg-subtle text-ink font-bold' : 'text-muted'}`}
                    >
                      All
                    </button>
                    <button
                      type="button"
                      onClick={() => setMarketTab('INDIAN')}
                      className={`px-2 py-0.5 text-[10px] font-medium rounded ${marketTab === 'INDIAN' ? 'bg-orange-500/20 text-orange-400 font-bold' : 'text-muted'}`}
                    >
                      🇮🇳 India
                    </button>
                    <button
                      type="button"
                      onClick={() => setMarketTab('US')}
                      className={`px-2 py-0.5 text-[10px] font-medium rounded ${marketTab === 'US' ? 'bg-blue-500/20 text-blue-400 font-bold' : 'text-muted'}`}
                    >
                      🇺🇸 US
                    </button>
                    <button
                      type="button"
                      onClick={() => setMarketTab('OTHER')}
                      className={`px-2 py-0.5 text-[10px] font-medium rounded ${marketTab === 'OTHER' ? 'bg-emerald-500/20 text-emerald-400 font-bold' : 'text-muted'}`}
                    >
                      Global
                    </button>
                  </div>
                </div>

                {/* Quick Presets Pills */}
                <div className="flex flex-wrap items-center gap-1.5">
                  {(marketTab === 'ALL' || marketTab === 'INDIAN') && marketPresets.INDIAN.map((p) => (
                    <button
                      key={p.symbol}
                      type="button"
                      onClick={() => selectTicker(p.symbol, p.exchange, p.price)}
                      className={`text-[10px] font-sans px-2 py-0.5 rounded border transition-colors flex items-center gap-1 ${
                        ticker === p.symbol 
                          ? 'bg-orange-500/20 border-orange-500/40 text-orange-400 font-bold' 
                          : 'bg-canvas hover:bg-subtle border-line text-secondary'
                      }`}
                    >
                      <span>{p.symbol}</span>
                    </button>
                  ))}
                  {(marketTab === 'ALL' || marketTab === 'US') && marketPresets.US.map((p) => (
                    <button
                      key={p.symbol}
                      type="button"
                      onClick={() => selectTicker(p.symbol, p.exchange, p.price)}
                      className={`text-[10px] font-sans px-2 py-0.5 rounded border transition-colors flex items-center gap-1 ${
                        ticker === p.symbol 
                          ? 'bg-blue-500/20 border-blue-500/40 text-blue-400 font-bold' 
                          : 'bg-canvas hover:bg-subtle border-line text-secondary'
                      }`}
                    >
                      <span>{p.symbol}</span>
                    </button>
                  ))}
                  {(marketTab === 'ALL' || marketTab === 'OTHER') && marketPresets.OTHER.map((p) => (
                    <button
                      key={p.symbol}
                      type="button"
                      onClick={() => selectTicker(p.symbol, p.exchange, p.price)}
                      className={`text-[10px] font-sans px-2 py-0.5 rounded border transition-colors flex items-center gap-1 ${
                        ticker === p.symbol 
                          ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400 font-bold' 
                          : 'bg-canvas hover:bg-subtle border-line text-secondary'
                      }`}
                    >
                      <span>{p.symbol}</span>
                    </button>
                  ))}
                </div>

                {/* Global Stock Live Search Input */}
                <div className="relative">
                  <div className="relative">
                    <input
                      type="text"
                      placeholder="Search any global stock (e.g. RELIANCE, TCS, TSLA, AAPL)..."
                      value={tickerQuery}
                      onChange={(e) => handleSearchTickers(e.target.value)}
                      onFocus={() => { if (tickerSearchResults.length > 0) setShowTickerDropdown(true); }}
                      className="w-full bg-canvas border border-line rounded-xl pl-8 pr-3 py-1.5 text-xs text-ink placeholder:text-muted focus:outline-none focus:border-brand"
                    />
                    <Search className="size-3.5 text-muted absolute left-2.5 top-2.5" />
                    {isSearchingTickers && <RefreshCw className="size-3.5 text-brand animate-spin absolute right-2.5 top-2.5" />}
                  </div>

                  {/* Search Dropdown */}
                  {showTickerDropdown && tickerSearchResults.length > 0 && (
                    <div className="absolute left-0 right-0 top-full mt-1 bg-surface border border-line-strong rounded-xl shadow-2xl z-50 max-h-48 overflow-y-auto">
                      <div className="p-2 text-[10px] font-bold text-muted uppercase border-b border-line">
                        Live Market Results
                      </div>
                      {tickerSearchResults.map((item) => (
                        <button
                          key={item.symbol}
                          type="button"
                          onClick={() => selectTicker(item.symbol, item.exchange)}
                          className="w-full text-left px-3 py-2 text-xs hover:bg-hover flex items-center justify-between border-b border-line/40 last:border-0"
                        >
                          <div>
                            <div className="font-bold text-ink">{item.symbol}</div>
                            <div className="text-[11px] text-muted truncate max-w-[240px]">{item.name}</div>
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

              {/* Side & Symbol */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-secondary mb-1.5">Action Side</label>
                  <div className="grid grid-cols-2 gap-1.5 p-1 bg-canvas border border-line rounded-xl">
                    <button
                      type="button"
                      onClick={() => setSide('BUY')}
                      className={`py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                        side === 'BUY'
                          ? 'bg-brand text-white shadow-sm'
                          : 'text-muted hover:text-secondary'
                      }`}
                    >
                      BUY
                    </button>
                    <button
                      type="button"
                      onClick={() => setSide('SELL')}
                      className={`py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                        side === 'SELL'
                          ? 'bg-rose-500 text-white shadow-sm'
                          : 'text-muted hover:text-secondary'
                      }`}
                    >
                      SELL
                    </button>
                  </div>
                </div>

                <div>
                  <label htmlFor="orderallocationmodal-field-2" className="block text-xs font-semibold text-secondary mb-1.5">Ticker Symbol</label>
                  <input id="orderallocationmodal-field-2"
                    type="text"
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value.toUpperCase())}
                    placeholder="e.g. AAPL, NVDA"
                    required
                    className="w-full bg-canvas border border-line rounded-xl px-3 py-2 text-xs font-sans font-bold text-ink uppercase focus:outline-none focus:border-line-strong"
                  />
                </div>
              </div>

              {/* Order Type & Exchange */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="orderallocationmodal-field-3" className="block text-xs font-semibold text-secondary mb-1.5">Order Type</label>
                  <select id="orderallocationmodal-field-3"
                    value={orderType}
                    onChange={(e) => setOrderType(e.target.value as any)}
                    className="w-full bg-canvas border border-line rounded-xl px-3 py-2 text-xs text-secondary focus:outline-none focus:border-line-strong"
                  >
                    <option value="LIMIT">LIMIT</option>
                    <option value="MARKET">MARKET</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="orderallocationmodal-field-4" className="block text-xs font-semibold text-secondary mb-1.5">Execution Venue</label>
                  <select id="orderallocationmodal-field-4"
                    value={exchange}
                    onChange={(e) => setExchange(e.target.value)}
                    className="w-full bg-canvas border border-line rounded-xl px-3 py-2 text-xs text-secondary focus:outline-none focus:border-line-strong"
                  >
                    <option value="NASDAQ">NASDAQ</option>
                    <option value="NYSE">NYSE</option>
                    <option value="BATS">BATS</option>
                    <option value="NSE">NSE</option>
                  </select>
                </div>
              </div>

              {/* Quantity & Price */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="orderallocationmodal-field-5" className="block text-xs font-semibold text-secondary mb-1.5">Quantity (Units)</label>
                  <input id="orderallocationmodal-field-5"
                    type="number"
                    min="1"
                    step="1"
                    value={quantity}
                    onChange={(e) => setQuantity(Number(e.target.value))}
                    required
                    className="w-full bg-canvas border border-line rounded-xl px-3 py-2 text-xs font-sans text-ink focus:outline-none focus:border-line-strong"
                  />
                </div>

                <div>
                  <label htmlFor="orderallocationmodal-field-6" className="block text-xs font-semibold text-secondary mb-1.5">
                    {orderType === 'LIMIT' ? 'Limit Price ($)' : 'Estimated Market ($)'}
                  </label>
                  <input id="orderallocationmodal-field-6"
                    type="number"
                    min="0.01"
                    step="0.01"
                    disabled={orderType === 'MARKET'}
                    value={limitPrice}
                    onChange={(e) => setLimitPrice(Number(e.target.value))}
                    className="w-full bg-canvas border border-line rounded-xl px-3 py-2 text-xs font-sans text-ink focus:outline-none focus:border-line-strong disabled:opacity-50"
                  />
                </div>
              </div>

              {/* Order Summary Box */}
              <div className="p-3.5 rounded-xl bg-canvas/70 border border-line flex items-center justify-between text-xs">
                <div>
                  <span className="text-muted">Estimated Gross Notional:</span>
                  <span className="font-bold font-sans text-ink ml-2">{notional}</span>
                </div>
                <div className="text-[11px] text-muted font-medium">Pre-trade check mandatory</div>
              </div>
            </form>
          )}

          {/* STEP 2: PRE-TRADE EVALUATED CHECKS */}
          {step === 'evaluated' && decisionResponse && (
            <div className="space-y-4">
              {/* Decision Banner */}
              <div
                className={`p-3.5 rounded-xl border flex items-center justify-between ${
                  decisionResponse.decision === 'PASS'
                    ? 'bg-brand/10 border-emerald-500/30 text-positive'
                    : 'bg-rose-500/10 border-rose-500/30 text-negative'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  {decisionResponse.decision === 'PASS' ? (
                    <ShieldCheck className="size-5 text-positive shrink-0" />
                  ) : (
                    <AlertTriangle className="size-5 text-negative shrink-0" />
                  )}
                  <div>
                    <div className="text-xs font-bold ">
                      {decisionResponse.decision === 'PASS' ? 'PRE-TRADE CHECKS PASSED' : 'LIMIT BREACH DETECTED'}
                    </div>
                    <div className="text-[11px] opacity-90">{decisionResponse.reason_summary}</div>
                  </div>
                </div>
                <span className="text-[10px] font-sans px-2 py-0.5 rounded bg-surface border border-line">
                  {decisionResponse.decision_id}
                </span>
              </div>

              {/* Simulation Projected Impact */}
              {decisionResponse.simulation && (
                <div className="p-3 bg-canvas border border-line rounded-xl space-y-2">
                  <div className="text-xs font-semibold text-secondary flex items-center gap-1.5">
                    <TrendingUp className="size-3.5 text-positive" />
                    <span>Projected Portfolio Impact</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-[11px]">
                    <div className="p-2 rounded bg-surface border border-line/80">
                      <div className="text-muted">Projected Exposure</div>
                      <div className="font-sans font-semibold text-secondary mt-0.5">
                        ${Number(decisionResponse.simulation.projected_gross_exposure).toLocaleString()}
                      </div>
                    </div>
                    <div className="p-2 rounded bg-surface border border-line/80">
                      <div className="text-muted">Projected 95% VaR</div>
                      <div className="font-sans font-semibold text-secondary mt-0.5">
                        ${Number(decisionResponse.simulation.projected_var).toLocaleString()}
                      </div>
                    </div>
                    <div className="p-2 rounded bg-surface border border-line/80">
                      <div className="text-muted">Incremental VaR</div>
                      <div className="font-sans font-semibold text-positive mt-0.5">
                        +${Number(decisionResponse.simulation.incremental_var).toLocaleString()}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Checklist Table */}
              <div>
                <div className="text-xs font-semibold text-muted mb-2">Mandatory Pre-Trade Checks (7 Rules)</div>
                <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                  {decisionResponse.check_results?.map((chk: ValidationCheckResult, idx: number) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2 rounded-lg bg-canvas/60 border border-line text-[11px]"
                    >
                      <div className="flex items-center gap-2">
                        {chk.check_status === 'PASS' ? (
                          <CheckCircle2 className="size-3.5 text-positive" />
                        ) : (
                          <AlertTriangle className="size-3.5 text-warning" />
                        )}
                        <span className="font-medium text-secondary capitalize">
                          {chk.check_name.replace(/_/g, ' ')}
                        </span>
                        <span className="text-[9px] font-sans text-muted uppercase">{chk.source_module}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="font-sans text-muted">
                          {chk.projected_value} / {chk.effective_limit}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-surface border border-line text-muted">
                          {chk.utilization_percentage}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* STEP 3: EXECUTION SUCCESS CONFIRMATION */}
          {step === 'confirmed' && executionResult && (
            <div className="p-4 rounded-xl bg-canvas border border-line text-center space-y-3">
              <div className="size-12 rounded-full bg-brand/10 border border-emerald-500/20 flex items-center justify-center text-positive mx-auto">
                <CheckCircle2 className="size-6 stroke-[2.5]" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-ink">Trade Executed & Settled</h3>
                <p className="text-xs text-muted mt-1">
                  Booked {side} {quantity} shares of {ticker} into portfolio {targetPortfolio}
                </p>
              </div>

              <div className="p-3 rounded-lg bg-surface border border-line/80 text-left text-xs font-sans space-y-1">
                <div className="flex justify-between">
                  <span className="text-muted">Position ID:</span>
                  <span className="text-secondary">{executionResult.position_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">Snapshot ID:</span>
                  <span className="text-secondary">{executionResult.snapshot_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">Net Quantity:</span>
                  <span className="text-positive">{executionResult.net_signed_quantity} shares</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">Recorded At:</span>
                  <span className="text-muted">{executionResult.recorded_at?.slice(0, 19)}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-line/80 bg-surface/60 flex items-center justify-between">
          <button
            type="button"
            onClick={step === 'input' ? onClose : handleReset}
            className="px-3.5 py-1.5 rounded-xl border border-line text-xs font-medium text-muted hover:text-secondary hover:border-line-strong transition-colors"
          >
            {step === 'confirmed' ? 'New Order' : 'Cancel'}
          </button>

          <div className="flex items-center gap-2">
            {step === 'input' && (
              <button
                type="submit"
                form="order-form"
                disabled={isEvaluating}
                className="flex items-center gap-2 px-4 py-1.5 rounded-xl bg-brand hover:bg-brand-hover text-white text-xs font-bold transition-colors disabled:opacity-50"
              >
                {isEvaluating ? (
                  <>
                    <Loader2 className="size-3.5 " />
                    <span>Evaluating Risk...</span>
                  </>
                ) : (
                  <>
                    <span>Simulate & Validate</span>
                    <ArrowRight className="size-3.5" />
                  </>
                )}
              </button>
            )}

            {step === 'evaluated' && (
              <>
                <button
                  type="button"
                  onClick={() => setStep('input')}
                  className="px-3.5 py-1.5 rounded-xl border border-line text-xs font-medium text-muted hover:text-secondary"
                >
                  Edit Order
                </button>
                {/* Warning message if pretrade check fails */}
                {decisionResponse?.decision !== 'PASS' && (
                  <div className="text-[11px] text-amber-500 bg-amber-500/10 border border-amber-500/20 p-2.5 rounded-lg flex items-center justify-between">
                    <span>Order exceeds standard risk limit benchmarks, but desk administrative override execution is permitted.</span>
                    <button
                      type="button"
                      onClick={handleConfirmOrder}
                      disabled={isExecuting}
                      className="px-2.5 py-1 bg-amber-600 hover:bg-amber-700 text-white rounded text-[10px] font-bold transition ml-2 shrink-0"
                    >
                      Override & Book
                    </button>
                  </div>
                )}

                <button
                  type="button"
                  onClick={handleConfirmOrder}
                  disabled={isExecuting}
                  className="flex items-center gap-2 px-4 py-1.5 rounded-xl bg-brand hover:bg-brand-hover text-white text-xs font-bold transition-colors disabled:opacity-50"
                >
                  {isExecuting ? (
                    <>
                      <Loader2 className="size-3.5 " />
                      <span>Booking Trade...</span>
                    </>
                  ) : (
                    <>
                      <ShieldCheck className="size-3.5" />
                      <span>Confirm & Execute Trade</span>
                    </>
                  )}
                </button>
              </>
            )}

            {step === 'confirmed' && (
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-1.5 rounded-xl bg-brand hover:bg-brand-hover text-white text-xs font-bold transition-colors"
              >
                Done
              </button>
            )}
          </div>
        </div>
      </div>
    </ModalSurface>
  );
};
