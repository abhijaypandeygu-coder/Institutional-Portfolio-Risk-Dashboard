import React from 'react';
import { StandardMetricValue } from '../../../types/dashboard';
import { DataQualityBadge } from '../shared/DataQualityBadge';
import { formatUtcTimestamp } from '../../../utils/financialFormatting';

interface PortfolioSummaryTableProps {
  rows: StandardMetricValue[];
}

export const PortfolioSummaryTable: React.FC<PortfolioSummaryTableProps> = ({ rows }) => {
  return (
    <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden mb-6">
      <div className="px-5 py-4 border-b border-slate-200">
        <h3 className="text-sm font-semibold text-slate-900">
          Portfolio Overview Metrics Summary
        </h3>
        <p className="text-xs text-slate-500 mt-0.5">
          Consolidated authoritative metric representations across M05 Valuation and M06 Exposure engines.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
          <thead className="bg-slate-50 text-slate-600 font-semibold uppercase tracking-wider">
            <tr>
              <th scope="col" className="px-4 py-3">Metric</th>
              <th scope="col" className="px-4 py-3">Value</th>
              <th scope="col" className="px-4 py-3">Unit</th>
              <th scope="col" className="px-4 py-3">Quality</th>
              <th scope="col" className="px-4 py-3">Source Engine</th>
              <th scope="col" className="px-4 py-3">Calculation Basis</th>
              <th scope="col" className="px-4 py-3">As of (UTC)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {rows.map((row) => (
              <tr key={row.metric_code} className="hover:bg-slate-50 transition">
                <td className="px-4 py-3 font-medium text-slate-900">
                  {row.metric_name}
                </td>
                <td className={`px-4 py-3 font-semibold ${row.is_negative ? 'text-rose-600' : 'text-slate-900'}`}>
                  {row.value_display}
                </td>
                <td className="px-4 py-3 text-slate-500">{row.unit}</td>
                <td className="px-4 py-3">
                  <DataQualityBadge status={row.quality_status} />
                </td>
                <td className="px-4 py-3 text-slate-600 font-mono text-[11px]">
                  {row.source_module}
                </td>
                <td className="px-4 py-3 text-slate-500 font-mono text-[11px]">
                  {row.calculation_basis}
                </td>
                <td className="px-4 py-3 text-slate-400">
                  {formatUtcTimestamp(row.as_of, false)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
