import React from 'react';
import { QualityStatus } from '../../../types/dashboard';
import { getQualityBadgeColor } from '../../../utils/financialFormatting';

interface DataQualityBadgeProps {
  status: QualityStatus | string;
  className?: string;
}

export const DataQualityBadge: React.FC<DataQualityBadgeProps> = ({ status, className = '' }) => {
  const badgeClasses = getQualityBadgeColor(status);
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${badgeClasses} ${className}`}
      title={`Data Quality Status: ${status}`}
    >
      {status}
    </span>
  );
};
