import React from 'react';
import { StandardMetricValue } from '../../../types/dashboard';
import { DataQualityBadge } from './DataQualityBadge';
import { formatUtcTimestamp } from '../../../utils/financialFormatting';

interface MetricCardProps {
  metric: StandardMetricValue;
  secondaryComparison?: string;
  onClick?: () => void;
  className?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  metric,
  secondaryComparison,
  onClick,
  className = '',
}) => {
  const isNegative = metric.is_negative || (metric.value !== null && metric.value < 0);
  const valueColor = isNegative
    ? 'text-negative'
    : metric.unit === 'PERCENTAGE' && metric.value !== null && metric.value > 0
    ? 'text-positive'
    : 'text-ink';

  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-lg border border-line p-4 shadow-sm hover:shadow transition-shadow ${
        onClick ? 'cursor-pointer' : ''
      } ${className}`}
    >
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-xs font-semibold uppercase  text-muted">
          {metric.metric_name}
        </h4>
        <DataQualityBadge status={metric.quality_status} />
      </div>

      <div className="flex items-baseline space-x-2">
        <span className={`text-2xl font-bold  ${valueColor}`}>
          {metric.value_display}
        </span>
        {secondaryComparison && (
          <span className="text-xs font-medium text-muted">
            {secondaryComparison}
          </span>
        )}
      </div>

      <div className="mt-3 pt-2 border-t border-line flex items-center justify-between text-[11px] text-muted">
        <span>Src: {metric.source_module}</span>
        <span>As of: {formatUtcTimestamp(metric.as_of, false)}</span>
      </div>
    </div>
  );
};
