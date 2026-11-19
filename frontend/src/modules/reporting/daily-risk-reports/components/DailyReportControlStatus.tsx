import React from "react";
import { ReportLimitStatusData } from "../../../../types/dailyReport";

interface DailyReportControlStatusProps {
  limitStatus?: ReportLimitStatusData;
}

export const DailyReportControlStatus: React.FC<DailyReportControlStatusProps> = ({
  limitStatus,
}) => {
  if (!limitStatus) {
    return (
      <div className="bg-surface border border-line rounded-lg p-5">
        <h2 className="text-sm font-semibold text-secondary mb-2">Control &amp; Risk Limit Status (M11)</h2>
        <p className="text-xs text-muted italic">No limit status evaluation available for this report run.</p>
      </div>
    );
  }

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case "EMERGENCY":
        return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-info-soft text-info border border-info/20 ">EMERGENCY</span>;
      case "CRITICAL":
        return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-negative-soft text-negative border border-negative/20">CRITICAL</span>;
      default:
        return <span className="px-2 py-0.5 text-[10px] font-semibold rounded bg-warning-soft text-warning border border-warning/20">WARNING</span>;
    }
  };

  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-lg">
      <div className="flex items-center justify-between border-b border-line pb-3 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-secondary">
            Control Oversight &amp; Risk Limit Breaches (M11)
          </h2>
          <p className="text-xs text-muted">
            Authoritative limit surveillance, threshold utilization, and unresolved breach audit trail
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs font-sans">
          <span className="text-muted">
            Limits Evaluated: <span className="text-secondary font-bold">{limitStatus.total_limits_evaluated}</span>
          </span>
          <span className="text-muted">
            Critical Breaches:{" "}
            <span className={limitStatus.critical_breaches_count > 0 ? "text-negative font-bold" : "text-positive font-bold"}>
              {limitStatus.critical_breaches_count}
            </span>
          </span>
        </div>
      </div>

      {limitStatus.breaches.length === 0 ? (
        <div className="bg-canvas/60 border border-positive/20 rounded p-4 text-center">
          <span className="text-xs font-sans text-positive font-medium">
            ✓ ZERO RISK LIMIT BREACHES DETECTED — All portfolio limits within mandate tolerances
          </span>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border border-line rounded">
            <thead>
              <tr className="bg-canvas/80 text-muted font-sans border-b border-line">
                <th className="py-2 px-3">Severity</th>
                <th className="py-2 px-3">Limit ID / Target</th>
                <th className="py-2 px-3">Metric</th>
                <th className="py-2 px-3 text-right">Observed</th>
                <th className="py-2 px-3 text-right">Threshold</th>
                <th className="py-2 px-3 text-right">Utilization</th>
                <th className="py-2 px-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80 font-sans">
              {limitStatus.breaches.map((b, idx) => (
                <tr key={idx} className="hover:bg-subtle/40 transition-colors">
                  <td className="py-2 px-3">{getSeverityBadge(b.severity)}</td>
                  <td className="py-2 px-3 text-secondary">
                    <span className="font-semibold">{b.limit_id}</span>
                    <span className="text-[10px] text-muted block">{b.target_entity}</span>
                  </td>
                  <td className="py-2 px-3 text-secondary">{b.metric_name}</td>
                  <td className="py-2 px-3 text-right text-ink">{b.observed_value.toLocaleString()}</td>
                  <td className="py-2 px-3 text-right text-muted">
                    {(b.critical_threshold ?? b.warning_threshold ?? 0).toLocaleString()} {b.unit}
                  </td>
                  <td className="py-2 px-3 text-right font-bold text-negative">
                    {b.utilization_pct.toFixed(1)}%
                  </td>
                  <td className="py-2 px-3 text-muted">
                    <span className="px-1.5 py-0.5 text-[10px] bg-subtle rounded border border-line-strong">
                      {b.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
