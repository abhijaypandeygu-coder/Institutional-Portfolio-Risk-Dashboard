import React from 'react';
import { InstrumentLiquidationProfile, PortfolioLiquidityDashboardResponse } from '../../../types/dashboard';
import { money, duration } from '../../../utils/liquidityAnalytics';

interface LiquidationPanelProps {
  liquidationProfile: InstrumentLiquidationProfile | null;
  participationRate: number;
  onParticipationRateChange: (rate: number) => void;
  portfolioData?: PortfolioLiquidityDashboardResponse | null;
}

export const LiquidationPanel: React.FC<LiquidationPanelProps> = ({ liquidationProfile: profile, participationRate, onParticipationRateChange, portfolioData }) => {
  if (!profile) return <div className="rounded-lg border border-line bg-surface p-5 text-sm text-muted">No liquidation estimate available.</div>;
  const currency = profile.currency || 'USD';
  return <section aria-labelledby="liquidation-heading" className="min-w-0 rounded-xl border border-line bg-surface p-5 space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <h3 id="liquidation-heading" className="text-lg font-semibold">Liquidation scenarios &amp; execution costs</h3>
      <label className="text-xs text-muted">Participation rate <select aria-label="Liquidation participation rate" value={participationRate} onChange={e => onParticipationRateChange(Number(e.target.value))} className="rounded border border-line bg-canvas p-2 text-secondary">
        <option value={.05}>5% of daily ADV</option><option value={.10}>10% of daily ADV</option><option value={.20}>20% of daily ADV</option>
      </select></label>
    </div>
    <div className="rounded-lg border border-line bg-canvas p-3 text-xs space-y-2">
      <p><strong>{profile.symbol}</strong> · {profile.position_direction} · {Number(profile.current_position_shares).toLocaleString()} shares · {money(profile.current_position_notional, currency)}</p>
      <p>{profile.liquidation_direction === 'SELL' ? 'Sell to liquidate a long position' : profile.liquidation_direction === 'BUY' ? 'Buy to cover a short position' : 'No position to liquidate'} · Single instrument estimate</p>
      <p className="text-muted">Session: {profile.calendar_description || 'Unavailable'} · {profile.session_minutes ?? 'Unknown'} trading minutes/session.</p>
      <p className="text-muted">Duration = shares ÷ (observed average daily volume × participation rate) × session minutes. Estimates count trading time, excluding nights, holidays and halts.</p>
      <p>Portfolio aggregate ({Number(portfolioData?.participation_rate ?? participationRate) * 100}% participation): <strong>{portfolioData && portfolioData.costs_complete !== false ? money(portfolioData.total_full_liquidation_cost_usd, portfolioData.reporting_currency) : 'Unavailable / incomplete'}</strong> · {portfolioData ? new Date(portfolioData.as_of_date).toLocaleString() : 'No portfolio snapshot'}</p>
      {profile.calculated_at && <p className="text-muted">Instrument estimate calculated {new Date(profile.calculated_at).toLocaleString()}. Amounts use {currency}; native quotes and base-currency valuations are not relabeled as USD.</p>}
    </div>
    {profile.is_portfolio_holding === false ? <p className="text-sm text-muted">External instrument: not held in the selected portfolio. No portfolio position is assumed.</p> : profile.scenarios.length === 0 ? <p role="status" className="text-sm text-warning">Estimate unavailable: {profile.model_status === 'INSUFFICIENT_ADV' ? 'observed daily volume is missing or zero.' : 'required inputs are unavailable.'}</p> : <>
      <div className="hidden md:block">
        <table className="w-full table-fixed text-left text-xs" aria-label="Liquidation cost scenarios">
          <thead><tr className="border-b border-line text-muted"><th className="py-3">Target</th><th>Shares</th><th>Estimated cost</th><th>Notional ({currency})</th><th>Total bps</th><th className="hidden xl:table-cell">Spread bps</th><th className="hidden xl:table-cell">Impact bps</th><th className="hidden xl:table-cell">Slippage bps</th><th>Trading duration</th></tr></thead>
          <tbody>{profile.scenarios.map(s => <tr key={s.target_percentage} className="border-b border-line">
            <th scope="row" className="py-4">{(Number(s.target_percentage)*100).toFixed(0)}%</th><td>{Number(s.shares_to_liquidate).toLocaleString()}</td>
            <td className="font-semibold text-negative break-words">{money(s.total_cost_usd, currency)}</td><td className="break-words">{money(s.notional_value, currency, true)}</td><td>{Number(s.total_cost_bps).toFixed(2)}</td>
            <td className="hidden xl:table-cell">{Number(s.spread_cost_bps).toFixed(2)}</td><td className="hidden xl:table-cell">{Number(s.market_impact_cost_bps).toFixed(2)}</td><td className="hidden xl:table-cell">{Number(s.slippage_cost_bps).toFixed(2)}</td>
            <td>{duration(s.estimated_duration_minutes)}<span className="block text-muted">{Number(s.estimated_trading_days).toFixed(4)} sessions</span></td>
          </tr>)}</tbody>
        </table>
      </div>
      <div className="space-y-3 md:hidden">{profile.scenarios.map(s => <article key={s.target_percentage} className="rounded-lg border border-line p-3 space-y-2 text-xs">
        <div className="flex justify-between gap-3"><strong>{(Number(s.target_percentage)*100).toFixed(0)}% liquidation</strong><strong className="text-negative">{money(s.total_cost_usd, currency)}</strong></div>
        <p>{Number(s.shares_to_liquidate).toLocaleString()} shares · {money(s.notional_value, currency)} · {duration(s.estimated_duration_minutes)}</p>
        <p className="text-muted">Spread {Number(s.spread_cost_bps).toFixed(2)} + impact {Number(s.market_impact_cost_bps).toFixed(2)} + slippage {Number(s.slippage_cost_bps).toFixed(2)} = {Number(s.total_cost_bps).toFixed(2)} bps</p>
      </article>)}</div>
      <details className="text-xs text-muted"><summary className="cursor-pointer">Cost model and breakdown</summary><p>Estimated cost = notional × total bps ÷ 10,000. Total bps = half quoted spread + modeled impact + modeled slippage. These are execution estimates, not guaranteed fill prices.</p></details>
    </>}
  </section>;
};
