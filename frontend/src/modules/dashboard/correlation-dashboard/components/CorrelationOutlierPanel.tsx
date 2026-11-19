import React from 'react';
import { CorrelationOutliersResponse, CorrelationOutlierItem } from '../../../../types/dashboard';

interface CorrelationOutlierPanelProps {
  outliers: CorrelationOutliersResponse | null;
  isLoading: boolean;
  onSelectPair: (item: CorrelationOutlierItem) => void;
}

export const CorrelationOutlierPanel: React.FC<CorrelationOutlierPanelProps> = ({
  outliers,
  isLoading,
  onSelectPair,
}) => {
  if (isLoading) {
    return (
      <div className="bg-surface border border-line rounded-lg p-8 flex items-center justify-center">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500" />
      </div>
    );
  }

  if (!outliers) {
    return null;
  }

  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-line">
        <div>
          <h3 className="text-sm font-semibold text-ink uppercase ">
            Correlation Outliers & Changing Relationships ({outliers.total_outliers_flagged} Flagged)
          </h3>
          <p className="text-[11px] text-muted mt-0.5">
            Pairs exceeding configured positive/negative thresholds or exhibiting material regime movements.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Strongest Positive */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-positive uppercase  flex items-center justify-between">
            <span>High Positive (&gt; 0.75)</span>
            <span>({outliers.high_positive_pairs.length})</span>
          </h4>
          <div className="space-y-1.5 max-h-56 overflow-y-auto">
            {outliers.high_positive_pairs.length === 0 ? (
              <p className="text-xs text-muted italic p-2">None exceeding threshold.</p>
            ) : (
              outliers.high_positive_pairs.map((item, idx) => renderOutlierCard(item, idx, onSelectPair))
            )}
          </div>
        </div>

        {/* Strongest Negative */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-negative uppercase  flex items-center justify-between">
            <span>Strong Negative (&lt; -0.50)</span>
            <span>({outliers.strong_negative_pairs.length})</span>
          </h4>
          <div className="space-y-1.5 max-h-56 overflow-y-auto">
            {outliers.strong_negative_pairs.length === 0 ? (
              <p className="text-xs text-muted italic p-2">None exceeding threshold.</p>
            ) : (
              outliers.strong_negative_pairs.map((item, idx) => renderOutlierCard(item, idx, onSelectPair))
            )}
          </div>
        </div>

        {/* Material Changes */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-warning uppercase  flex items-center justify-between">
            <span>Largest Correlation Shifts (|Δρ| &gt; 0.30)</span>
            <span>({outliers.large_change_pairs.length})</span>
          </h4>
          <div className="space-y-1.5 max-h-56 overflow-y-auto">
            {outliers.large_change_pairs.length === 0 ? (
              <p className="text-xs text-muted italic p-2">No material shifts detected.</p>
            ) : (
              outliers.large_change_pairs.map((item, idx) => renderOutlierCard(item, idx, onSelectPair))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

function renderOutlierCard(
  item: CorrelationOutlierItem,
  idx: number,
  onSelectPair: (item: CorrelationOutlierItem) => void
) {
  const isPositive = Number(item.current_correlation) > 0;

  return (
    <div
      key={`${item.instrument_a_id}_${item.instrument_b_id}_${idx}`}
      onClick={() => onSelectPair(item)}
      className="p-2.5 rounded bg-subtle/60 border border-line-strong/60 hover:border-line-strong cursor-pointer flex items-center justify-between text-xs transition-colors"
    >
      <div>
        <div className="font-bold text-secondary">
          {item.instrument_a_symbol} <span className="text-muted">↔</span> {item.instrument_b_symbol}
        </div>
        {item.delta_correlation !== null && item.delta_correlation !== undefined && (
          <div className="text-[10px] text-muted mt-0.5">
            Δρ: <span className={Number(item.delta_correlation) > 0 ? 'text-positive' : 'text-negative'}>
              {Number(item.delta_correlation) > 0 ? '+' : ''}{Number(item.delta_correlation).toFixed(2)}
            </span> (Prev: {item.reference_correlation !== null && item.reference_correlation !== undefined ? Number(item.reference_correlation).toFixed(2) : '—'})
          </div>
        )}
      </div>

      <div className="text-right">
        <div className={`font-black text-sm ${isPositive ? 'text-positive' : 'text-negative'}`}>
          {Number(item.current_correlation).toFixed(2)}
        </div>
        <div className="text-[9px] text-muted uppercase">
          {item.detection_reason.replace(/_/g, ' ')}
        </div>
      </div>
    </div>
  );
}
