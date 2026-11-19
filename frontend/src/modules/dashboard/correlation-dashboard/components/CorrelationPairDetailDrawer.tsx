import React, { useState } from 'react';
import axios from 'axios';
import { CorrelationPairDetailResponse } from '../../../../types/dashboard';

interface CorrelationPairDetailDrawerProps {
  detail: CorrelationPairDetailResponse | null;
  isLoading: boolean;
  portfolioId?: string | null;
  onClose: () => void;
}

export const CorrelationPairDetailDrawer: React.FC<CorrelationPairDetailDrawerProps> = ({
  detail,
  isLoading,
  portfolioId,
  onClose,
}) => {
  const [userNote, setUserNote] = useState('');
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  if (!detail && !isLoading) {
    return null;
  }

  const handleSaveInvestigation = async () => {
    if (!detail || !userNote.trim()) return;
    try {
      await axios.post('/api/v1/dashboard/correlation/investigations', {
        portfolio_id: portfolioId,
        instrument_a_id: detail.instrument_a_id,
        instrument_b_id: detail.instrument_b_id,
        correlation_value: detail.correlation,
        correlation_method: detail.estimator,
        lookback_days: detail.lookback_days,
        sampling_frequency: detail.frequency,
        observation_count: detail.sample_size,
        detection_reason: Number(detail.correlation) > 0 ? 'HIGH_POSITIVE_CORRELATION' : 'STRONG_NEGATIVE_CORRELATION',
        user_notes: userNote,
      });
      setSaveStatus('Investigation recorded successfully.');
      setUserNote('');
    } catch (err: unknown) {
      console.error('Failed to save investigation:', err);
      setSaveStatus('Failed to record investigation.');
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-xl bg-surface border-l border-line shadow-2xl z-50 overflow-y-auto flex flex-col">
      {/* Drawer Header */}
      <div className="p-5 border-b border-line flex items-center justify-between bg-canvas/80 sticky top-0 ">
        <div>
          <span className="text-[10px] font-bold uppercase  px-2 py-0.5 rounded bg-brand-soft text-brand border border-brand/20">
            RELATIONSHIP INSPECTION
          </span>
          <h3 className="text-lg font-bold text-ink mt-1">
            {detail ? `${detail.instrument_a_symbol} ↔ ${detail.instrument_b_symbol}` : 'Loading Pair...'}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="text-muted hover:text-secondary p-2 rounded-lg hover:bg-subtle transition-colors"
        >
          ✕
        </button>
      </div>

      {/* Drawer Content */}
      <div className="p-5 flex-1 space-y-6 text-xs">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-48 space-y-3">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
            <p className="text-xs text-muted">Retrieving pairwise statistics & return observations...</p>
          </div>
        ) : detail ? (
          <>
            {/* KPI Cards */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-subtle/60 p-3 rounded-lg border border-line">
                <div className="text-[11px] text-muted">Correlation (ρ)</div>
                <div className="text-base font-extrabold text-ink mt-0.5">
                  {Number(detail.correlation).toFixed(4)}
                </div>
              </div>
              <div className="bg-subtle/60 p-3 rounded-lg border border-line">
                <div className="text-[11px] text-muted">Sample Size</div>
                <div className="text-base font-extrabold text-ink mt-0.5">
                  {detail.sample_size} Days
                </div>
              </div>
              <div className="bg-subtle/60 p-3 rounded-lg border border-line">
                <div className="text-[11px] text-muted">95% CI Range</div>
                <div className="text-xs font-bold text-secondary mt-1">
                  [{Number(detail.ci_lower_95 || 0).toFixed(2)}, {Number(detail.ci_upper_95 || 0).toFixed(2)}]
                </div>
              </div>
            </div>

            {/* Statistical Diagnostics */}
            <div className="bg-subtle/40 border border-line rounded-lg p-3.5 space-y-1.5 text-secondary">
              <div className="font-semibold text-secondary border-b border-line-strong/60 pb-1 mb-2">
                Statistical Diagnostics & Covariance
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Covariance (σ_ab):</span>
                <span>{detail.covariance !== null && detail.covariance !== undefined ? Number(detail.covariance).toFixed(6) : 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">t-Statistic / p-Value:</span>
                <span>{detail.t_statistic ? Number(detail.t_statistic).toFixed(2) : '—'} (p = {detail.p_value ? Number(detail.p_value).toFixed(4) : '—'})</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Standard Error (SE):</span>
                <span>{detail.std_error ? Number(detail.std_error).toFixed(4) : '—'}</span>
              </div>
              {detail.least_squares_slope !== null && detail.least_squares_slope !== undefined && (
                <div className="flex justify-between">
                  <span className="text-muted">OLS Regression Slope (β):</span>
                  <span className="font-semibold text-brand">{Number(detail.least_squares_slope).toFixed(3)}</span>
                </div>
              )}
            </div>

            {/* Return Scatter Plot Table */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-semibold uppercase  text-muted">
                  Paired Return Observations ({detail.scatter_points.length} Sessions)
                </h4>
                <span className="text-[10px] text-muted">Log Returns</span>
              </div>

              <div className="border border-line rounded-lg overflow-hidden bg-canvas/40 max-h-48 overflow-y-auto">
                <table className="min-w-full divide-y divide-slate-800 text-[11px]">
                  <thead className="bg-surface/60 text-muted">
                    <tr>
                      <th className="py-1.5 px-3 text-left">Trading Date</th>
                      <th className="py-1.5 px-3 text-right">{detail.instrument_a_symbol} Return</th>
                      <th className="py-1.5 px-3 text-right">{detail.instrument_b_symbol} Return</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 text-secondary">
                    {detail.scatter_points.map((pt, i) => (
                      <tr key={i} className="hover:bg-subtle/40">
                        <td className="py-1 px-3 text-muted">{pt.observation_date}</td>
                        <td className="py-1 px-3 text-right font-sans">
                          {Number(pt.return_a) > 0 ? '+' : ''}{(Number(pt.return_a) * 100).toFixed(2)}%
                        </td>
                        <td className="py-1 px-3 text-right font-sans">
                          {Number(pt.return_b) > 0 ? '+' : ''}{(Number(pt.return_b) * 100).toFixed(2)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Operational Investigation Note */}
            <div className="bg-canvas border border-line rounded-lg p-3.5 space-y-2">
              <div className="font-semibold text-secondary">Record Operational Investigation Note</div>
              <textarea
                value={userNote}
                onChange={(e) => setUserNote(e.target.value)}
                placeholder="Document thesis, regime change context, or review notes..."
                className="w-full bg-surface border border-line-strong rounded p-2 text-xs text-ink placeholder-muted focus:outline-none focus:ring-1 focus:ring-blue-500"
                rows={3}
              />
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={handleSaveInvestigation}
                  className="px-3 py-1.5 bg-brand hover:bg-brand-hover text-white rounded font-semibold text-xs transition-colors"
                >
                  Save Investigation
                </button>
                {saveStatus && <span className="text-[11px] text-positive">{saveStatus}</span>}
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
};
