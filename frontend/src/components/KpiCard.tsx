import React from 'react';

type Props = {
  title: string;
  value: string | number;
  unit?: string;
  tooltip?: string;
};

export const KpiCard: React.FC<Props> = ({ title, value, unit, tooltip }) => (
  <div className="bg-slate-800 rounded-lg p-4 flex flex-col shadow-sm">
    <div className="flex items-center space-x-1">
      <h3 className="text-sm font-medium text-slate-300">{title}</h3>
      {tooltip && (
        <span className="cursor-help text-slate-500" title={tooltip}>ℹ️</span>
      )}
    </div>
    <p className="mt-2 text-xl font-semibold text-slate-100">
      {typeof value === 'number' ? value.toLocaleString() : value}{unit && <span className="ml-1 text-sm">{unit}</span>}
    </p>
  </div>
);
