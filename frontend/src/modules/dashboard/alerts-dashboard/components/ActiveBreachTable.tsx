import React from 'react';
import { ShieldCheck } from 'lucide-react';
import { ActiveBreachItem, BreachSeverity, SLAState } from '../../../../types/dashboard';

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
          <span className="px-2 py-0.5 text-xs font-bold rounded bg-negative-soft text-negative border border-negative/20">
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
          <span className="px-2 py-0.5 text-xs rounded bg-subtle text-secondary">
            {severity}
          </span>
        );
    }
  };

  const getSLABadge = (state: SLAState) => {
    switch (state) {
      case 'IN_SLA':
        return <span className="text-positive text-xs font-sans">IN SLA</span>;
      case 'NEAR_EXPIRY':
        return <span className="text-warning text-xs font-sans font-semibold ">NEAR EXPIRY</span>;
      case 'EXPIRED':
        return <span className="text-negative text-xs font-sans font-bold">OVERDUE</span>;
      default:
        return <span className="text-muted text-xs font-sans">—</span>;
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
      <div className="bg-surface border border-line rounded-lg p-8 text-center text-muted">
        Loading active breaches...
      </div>
    );
  }

  if (breaches.length === 0) {
    return (
      <div className="bg-surface border border-line rounded-lg p-8 text-center flex flex-col items-center">
        <div className="size-10 rounded-full bg-brand/10 border border-emerald-500/20 flex items-center justify-center text-positive mb-3">
          <ShieldCheck className="size-5" />
        </div>
        <div className="text-secondary font-semibold">No Active Breaches</div>
        <div className="text-muted text-sm mt-1">All risk limits are within compliant thresholds.</div>
      </div>
    );
  }

  return (
    <div className="bg-surface border border-line rounded-lg overflow-hidden shadow-sm">
      <div className="px-4 py-3 border-b border-line flex items-center justify-between">
        <h3 className="text-sm font-semibold text-secondary">Active Limit Breaches (M11 Authoritative)</h3>
        <span className="text-xs text-muted font-sans">{breaches.length} open</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-canvas/60 text-muted font-medium border-b border-line uppercase  text-[11px]">
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
          <tbody className="divide-y divide-slate-800/80 text-secondary">
            {breaches.map((b) => {
              const ruleName = b.rule_name || b.risk_limit_id || b.risk_metric || 'Limit Breach';
              const ruleCategory = b.rule_category || b.breach_type || 'RISK';
              const metricVal = b.current_metric_value ?? (b.current_value !== undefined ? parseFloat(String(b.current_value)) : 0);
              const limitVal = b.limit_threshold_value ?? (b.limit_value !== undefined ? parseFloat(String(b.limit_value)) : 0);
              const unit = b.unit || b.metric_unit || '';
              
              // Calculate utilization percentage correctly:
              // If limitVal is present and > 0, compute (metricVal / limitVal) * 100
              // If backend provides b.utilization as a decimal ratio (e.g. 1.2 for 120%), convert <= 5.0 to percent (* 100)
              let utilPct: number = 0;
              if (b.utilization_pct !== undefined && b.utilization_pct !== null) {
                utilPct = parseFloat(String(b.utilization_pct));
              } else if (limitVal > 0) {
                utilPct = (metricVal / limitVal) * 100;
              } else if (b.utilization !== undefined && b.utilization !== null) {
                const rawUtil = parseFloat(String(b.utilization));
                utilPct = rawUtil <= 5.0 ? rawUtil * 100 : rawUtil;
              }
              const isAck = b.is_acknowledged || b.acknowledgement_status === 'ACKNOWLEDGED';
              const slaBadge = b.sla_state ? getSLABadge(b.sla_state) : (
                <span className="text-positive text-xs font-sans">{b.sla_status || 'ON_TRACK'}</span>
              );

              return (
                <tr
                  key={b.breach_id}
                  className="hover:bg-subtle/50 transition cursor-pointer"
                  onClick={() => onSelectBreach(b)}
                >
                  <td className="py-2.5 px-3 whitespace-nowrap">{getSeverityBadge(b.severity)}</td>
                  <td className="py-2.5 px-3 font-medium text-ink">
                    <div>{ruleName}</div>
                    <div className="text-[10px] text-muted">{ruleCategory}</div>
                  </td>
                  <td className="py-2.5 px-3">
                    <div className="font-sans text-secondary">{b.portfolio_name || b.portfolio_id}</div>
                    {b.instrument_id && (
                      <div className="text-[10px] text-muted font-sans">{b.instrument_id}</div>
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-right font-sans text-ink">
                    {isNaN(metricVal) ? '—' : metricVal.toLocaleString(undefined, { maximumFractionDigits: 2 })} {unit}
                  </td>
                  <td className="py-2.5 px-3 text-right font-sans text-muted">
                    {isNaN(limitVal) ? '—' : limitVal.toLocaleString(undefined, { maximumFractionDigits: 2 })} {unit}
                  </td>
                  <td className="py-2.5 px-3 text-right font-sans font-semibold">
                    <span
                      className={
                        utilPct >= 100
                          ? 'text-negative'
                          : utilPct >= 85
                          ? 'text-yellow-400'
                          : 'text-secondary'
                      }
                    >
                      {isNaN(utilPct) ? '—' : `${utilPct.toFixed(1)}%`}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 font-sans text-muted whitespace-nowrap">
                    {b.duration_display || formatDuration(b.duration_minutes)}
                  </td>
                  <td className="py-2.5 px-3 whitespace-nowrap">{slaBadge}</td>
                  <td className="py-2.5 px-3 font-sans text-muted">{b.current_escalation_level || `L${b.escalation_level || 1}`}</td>
                  <td
                    className="py-2.5 px-3 text-right whitespace-nowrap"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {!isAck ? (
                      <button
                        type="button"
                        onClick={() => onAcknowledgeBreach(b.breach_id)}
                        className="px-2 py-1 bg-warning-soft/60 hover:bg-warning-soft text-warning rounded text-[11px] font-semibold border border-warning/20 transition"
                      >
                        Acknowledge
                      </button>
                    ) : (
                      <span className="text-[10px] text-positive font-sans">
                        Ack'd ({b.acknowledged_by || 'Risk'})
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
