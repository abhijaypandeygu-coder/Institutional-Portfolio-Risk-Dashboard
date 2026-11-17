import React from 'react';
import { ActiveBreachItem, BreachSeverity, SLAState } from '../../../types/dashboard';

interface ActiveBreachTableProps {
  breaches: ActiveBreachItem[];
  loading: boolean;
  onSelectBreach: (breach: ActiveBreachItem) => void;
  onAcknowledgeBreach: (breachId: string) => void;
}

export const ActiveBreachTable: React.FC<ActiveBreachTableProps> = ({
  breaches,
  loading,
  onSelectBreach,
  onAcknowledgeBreach,
}) => {
  const getSeverityBadge = (severity: BreachSeverity) => {
    switch (severity) {
      case 'EMERGENCY':
        return (
          <span className="px-2 py-0.5 text-xs font-bold rounded bg-red-950 text-red-300 border border-red-700">
            EMERGENCY
          </span>
        );
      case 'CRITICAL':
        return (
          <span className="px-2 py-0.5 text-xs font-bold rounded bg-orange-950 text-orange-300 border border-orange-700">
            CRITICAL
          </span>
        );
      case 'WARNING':
        return (
          <span className="px-2 py-0.5 text-xs font-semibold rounded bg-yellow-950/80 text-yellow-300 border border-yellow-700/80">
            WARNING
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 text-xs rounded bg-slate-800 text-slate-300">
            {severity}
          </span>
        );
    }
  };

  const getSLABadge = (state: SLAState) => {
    switch (state) {
      case 'IN_SLA':
        return <span className="text-emerald-400 text-xs font-mono">IN SLA</span>;
      case 'NEAR_EXPIRY':
        return <span className="text-amber-400 text-xs font-mono font-semibold animate-pulse">NEAR EXPIRY</span>;
      case 'EXPIRED':
        return <span className="text-red-400 text-xs font-mono font-bold">OVERDUE</span>;
      default:
        return <span className="text-slate-500 text-xs font-mono">—</span>;
    }
  };

  const formatDuration = (mins: number) => {
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    const rem = mins % 60;
    return `${hrs}h ${rem}m`;
  };

  if (loading && breaches.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-8 text-center text-slate-500">
        Loading active breaches...
      </div>
    );
  }

  if (breaches.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-8 text-center">
        <div className="text-3xl mb-2">✅</div>
        <div className="text-slate-300 font-semibold">No Active Breaches</div>
        <div className="text-slate-500 text-sm mt-1">All risk limits are within compliant thresholds.</div>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden shadow-sm">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200">Active Limit Breaches (M11 Authoritative)</h3>
        <span className="text-xs text-slate-400 font-mono">{breaches.length} open</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-950/60 text-slate-400 font-medium border-b border-slate-800 uppercase tracking-wider text-[11px]">
            <tr>
              <th className="py-2.5 px-3">Severity</th>
              <th className="py-2.5 px-3">Rule / Limit</th>
              <th className="py-2.5 px-3">Portfolio / Target</th>
              <th className="py-2.5 px-3 text-right">Metric Value</th>
              <th className="py-2.5 px-3 text-right">Threshold</th>
              <th className="py-2.5 px-3 text-right">Utilization</th>
              <th className="py-2.5 px-3">Duration</th>
              <th className="py-2.5 px-3">SLA Status</th>
              <th className="py-2.5 px-3">Escalation</th>
              <th className="py-2.5 px-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80 text-slate-300">
            {breaches.map((b) => (
              <tr
                key={b.breach_id}
                className="hover:bg-slate-800/50 transition cursor-pointer"
                onClick={() => onSelectBreach(b)}
              >
                <td className="py-2.5 px-3 whitespace-nowrap">{getSeverityBadge(b.severity)}</td>
                <td className="py-2.5 px-3 font-medium text-slate-100">
                  <div>{b.rule_name}</div>
                  <div className="text-[10px] text-slate-500">{b.rule_category}</div>
                </td>
                <td className="py-2.5 px-3">
                  <div className="font-mono text-slate-200">{b.portfolio_name || b.portfolio_id}</div>
                  {b.instrument_id && (
                    <div className="text-[10px] text-slate-400 font-mono">{b.instrument_id}</div>
                  )}
                </td>
                <td className="py-2.5 px-3 text-right font-mono text-slate-100">
                  {b.current_metric_value.toLocaleString(undefined, { maximumFractionDigits: 2 })} {b.unit}
                </td>
                <td className="py-2.5 px-3 text-right font-mono text-slate-400">
                  {b.limit_threshold_value.toLocaleString(undefined, { maximumFractionDigits: 2 })} {b.unit}
                </td>
                <td className="py-2.5 px-3 text-right font-mono font-semibold">
                  <span
                    className={
                      b.utilization_pct >= 100
                        ? 'text-red-400'
                        : b.utilization_pct >= 85
                        ? 'text-yellow-400'
                        : 'text-slate-300'
                    }
                  >
                    {b.utilization_pct.toFixed(1)}%
                  </span>
                </td>
                <td className="py-2.5 px-3 font-mono text-slate-400 whitespace-nowrap">
                  {formatDuration(b.duration_minutes)}
                </td>
                <td className="py-2.5 px-3 whitespace-nowrap">{getSLABadge(b.sla_state)}</td>
                <td className="py-2.5 px-3 font-mono text-slate-400">L{b.escalation_level}</td>
                <td
                  className="py-2.5 px-3 text-right whitespace-nowrap"
                  onClick={(e) => e.stopPropagation()}
                >
                  {!b.is_acknowledged ? (
                    <button
                      type="button"
                      onClick={() => onAcknowledgeBreach(b.breach_id)}
                      className="px-2 py-1 bg-amber-900/60 hover:bg-amber-800 text-amber-200 rounded text-[11px] font-semibold border border-amber-700/60 transition"
                    >
                      Acknowledge
                    </button>
                  ) : (
                    <span className="text-[10px] text-emerald-400 font-mono">
                      Ack'd ({b.acknowledged_by || 'Risk'})
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
