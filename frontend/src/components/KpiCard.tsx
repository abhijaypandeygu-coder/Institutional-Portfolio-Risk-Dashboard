import React from 'react';

type Props = {
  title: string;
  value: string | number;
  unit?: string;
  tooltip?: string;
};

export const KpiCard: React.FC<Props> = ({ title, value, unit, tooltip }) => (
  <div className="bg-surface border border-line rounded-lg p-4 flex flex-col">
    <div className="flex items-center space-x-1">
      <h3 className="text-sm font-medium text-secondary">{title}</h3>
      {tooltip && (
        <span className="sr-only">{tooltip}</span>
      )}
    </div>
    <p className="mt-2 text-xl font-semibold tabular-nums text-ink">
      {typeof value === 'number' ? value.toLocaleString() : value}{unit && <span className="ml-1 text-sm">{unit}</span>}
    </p>
  </div>
);
