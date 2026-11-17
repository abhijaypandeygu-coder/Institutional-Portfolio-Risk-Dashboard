import React from "react";
import { ReportLimitStatusData } from "../../../types/dailyReport";

interface DailyReportControlStatusProps {
  limitStatus?: ReportLimitStatusData;
}

export const DailyReportControlStatus: React.FC<DailyReportControlStatusProps> = ({
  limitStatus,
}) => {
  if (!limitStatus) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-2">Control &amp; Risk Limit Status (M11)</h2>
        <p className="text-xs text-slate-500 italic">No limit status evaluation available for this report run.</p>
      </div>
    );
  }

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case "EMERGENCY":
        return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-purple-950 text-purple-300 border border-purple-700 animate-pulse">EMERGENCY</span>;
      case "CRITICAL":
        return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-rose-950 text-rose-400 border border-rose-800">CRITICAL</span>;
      default:
        return <span className="px-2 py-0.5 text-[10px] font-semibold rounded bg-amber-950 text-amber-400 border border-amber-800">WARNING</span>;
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">
            Control Oversight &amp; Risk Limit Breaches (M11)
          </h2>
          <p className="text-xs text-slate-500">
            Authoritative limit surveillance, threshold utilization, and unresolved breach audit trail
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs font-mono">
          <span className="text-slate-400">
            Limits Evaluated: <span className="text-slate-200 font-bold">{limitStatus.total_limits_evaluated}</span>
          </span>
          <span className="text-slate-400">
            Critical Breaches:{" "}
            <span className={limitStatus.critical_breaches_count > 0 ? "text-rose-400 font-bold" : "text-emerald-400 font-bold"}>
              {limitStatus.critical_breaches_count}
            </span>
          </span>
        </div>
      </div>

      {limitStatus.breaches.length === 0 ? (
        <div className="bg-slate-950/60 border border-emerald-900/40 rounded p-4 text-center">
          <span className="text-xs font-mono text-emerald-400 font-medium">
            ✓ ZERO RISK LIMIT BREACHES DETECTED — All portfolio limits within mandate tolerances
          </span>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border border-slate-800 rounded">
            <thead>
              <tr className="bg-slate-950/80 text-slate-400 font-mono border-b border-slate-800">
                <th className="py-2 px-3">Severity</th>
                <th className="py-2 px-3">Limit ID / Target</th>
                <th className="py-2 px-3">Metric</th>
                <th className="py-2 px-3 text-right">Observed</th>
                <th className="py-2 px-3 text-right">Threshold</th>
                <th className="py-2 px-3 text-right">Utilization</th>
                <th className="py-2 px-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80 font-mono">
              {limitStatus.breaches.map((b, idx) => (
                <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                  <td className="py-2 px-3">{getSeverityBadge(b.severity)}</td>
                  <td className="py-2 px-3 text-slate-200">
                    <span className="font-semibold">{b.limit_id}</span>
                    <span className="text-[10px] text-slate-500 block">{b.target_entity}</span>
                  </td>
                  <td className="py-2 px-3 text-slate-300">{b.metric_name}</td>
                  <td className="py-2 px-3 text-right text-slate-100">{b.observed_value.toLocaleString()}</td>
                  <td className="py-2 px-3 text-right text-slate-400">
                    {(b.critical_threshold ?? b.warning_threshold ?? 0).toLocaleString()} {b.unit}
                  </td>
                  <td className="py-2 px-3 text-right font-bold text-rose-400">
                    {b.utilization_pct.toFixed(1)}%
                  </td>
                  <td className="py-2 px-3 text-slate-400">
                    <span className="px-1.5 py-0.5 text-[10px] bg-slate-800 rounded border border-slate-700">
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
