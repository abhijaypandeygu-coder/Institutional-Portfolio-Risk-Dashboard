import React from 'react';
import { StandardMetricValue } from '../../../types/dashboard';
import { DataQualityBadge } from '../shared/DataQualityBadge';
import { formatUtcTimestamp } from '../../../utils/financialFormatting';

interface PortfolioSummaryTableProps {
  rows: StandardMetricValue[];
}

export const PortfolioSummaryTable: React.FC<PortfolioSummaryTableProps> = ({ rows }) => {
  return (
    <div className="bg-white rounded-lg border border-line shadow-sm overflow-hidden mb-6">
      <div className="px-5 py-4 border-b border-line">
        <h3 className="text-sm font-semibold text-ink">
          Portfolio Overview Metrics Summary
        </h3>
        <p className="text-xs text-muted mt-0.5">
          Consolidated authoritative metric representations across M05 Valuation and M06 Exposure engines.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
          <thead className="bg-canvas text-secondary font-semibold uppercase ">
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
              <tr key={row.metric_code} className="hover:bg-canvas transition">
                <td className="px-4 py-3 font-medium text-ink">
                  {row.metric_name}
                </td>
                <td className={`px-4 py-3 font-semibold ${row.is_negative ? 'text-negative' : 'text-ink'}`}>
                  {row.value_display}
                </td>
                <td className="px-4 py-3 text-muted">{row.unit}</td>
                <td className="px-4 py-3">
                  <DataQualityBadge status={row.quality_status} />
                </td>
                <td className="px-4 py-3 text-secondary font-sans text-[11px]">
                  {row.source_module}
                </td>
                <td className="px-4 py-3 text-muted font-sans text-[11px]">
                  {row.calculation_basis}
                </td>
                <td className="px-4 py-3 text-muted">
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
