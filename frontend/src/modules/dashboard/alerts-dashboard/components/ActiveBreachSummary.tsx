import React from 'react';
import { ActiveBreachSummaryResponse } from '../../../../types/dashboard';

interface ActiveBreachSummaryProps {
  summary: ActiveBreachSummaryResponse | null;
  loading: boolean;
}

export const ActiveBreachSummary: React.FC<ActiveBreachSummaryProps> = ({ summary, loading }) => {
  if (loading && !summary) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 mb-6">
        {[...Array(7)].map((_, i) => (
          <div key={i} className="bg-slate-900 border border-slate-800 rounded-lg p-4 animate-pulse h-24" />
        ))}
      </div>
    );
  }

  const totalActive = summary?.counts?.total_active ?? summary?.total_active_breaches ?? 0;
  const emergency = summary?.counts?.emergency ?? summary?.emergency_breaches ?? 0;
  const critical = summary?.counts?.critical ?? summary?.critical_breaches ?? 0;
  const warning = summary?.counts?.warning ?? summary?.warning_breaches ?? 0;
  const unacknowledged = summary?.counts?.unacknowledged ?? summary?.unacknowledged_breaches ?? 0;
  const escalated = summary?.counts?.awaiting_remediation ?? summary?.escalated_breaches ?? 0;
  const overdueSla = summary?.counts?.overdue_escalation ?? summary?.overdue_sla_breaches ?? 0;

  const cards = [
    {
      label: 'Total Active',
      value: totalActive,
      color: 'text-slate-100',
      bgColor: 'bg-slate-900/80',
      border: 'border-slate-800',
      icon: '🛡️',
    },
    {
      label: 'Emergency (L3)',
      value: emergency,
      color: 'text-red-400 font-bold',
      bgColor: emergency > 0 ? 'bg-red-950/40' : 'bg-slate-900/80',
      border: emergency > 0 ? 'border-red-800' : 'border-slate-800',
      icon: '🚨',
    },
    {
      label: 'Critical (L2)',
      value: critical,
      color: 'text-orange-400 font-bold',
      bgColor: critical > 0 ? 'bg-orange-950/40' : 'bg-slate-900/80',
      border: critical > 0 ? 'border-orange-800' : 'border-slate-800',
      icon: '⚠️',
    },
    {
      label: 'Warning (L1)',
      value: warning,
      color: 'text-yellow-400 font-semibold',
      bgColor: 'bg-slate-900/80',
      border: 'border-slate-800',
      icon: '⚡',
    },
    {
      label: 'Unacknowledged',
      value: unacknowledged,
      color: unacknowledged > 0 ? 'text-amber-400 font-bold' : 'text-slate-200',
      bgColor: unacknowledged > 0 ? 'bg-amber-950/30' : 'bg-slate-900/80',
      border: unacknowledged > 0 ? 'border-amber-800/60' : 'border-slate-800',
      icon: '📬',
    },
    {
      label: 'Awaiting Remediation',
      value: escalated,
      color: 'text-purple-400 font-semibold',
      bgColor: 'bg-slate-900/80',
      border: 'border-slate-800',
      icon: '🔺',
    },
    {
      label: 'Overdue SLA',
      value: overdueSla,
      color: overdueSla > 0 ? 'text-rose-400 font-bold' : 'text-slate-400',
      bgColor: overdueSla > 0 ? 'bg-rose-950/40 animate-pulse' : 'bg-slate-900/80',
      border: overdueSla > 0 ? 'border-rose-700' : 'border-slate-800',
      icon: '⏱️',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 mb-6">
      {cards.map((c, idx) => (
        <div
          key={idx}
          className={`${c.bgColor} ${c.border} border rounded-lg p-3 flex flex-col justify-between shadow-sm transition hover:border-slate-700`}
        >
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>{c.label}</span>
            <span>{c.icon}</span>
          </div>
          <div className={`text-2xl mt-2 tracking-tight ${c.color}`}>{c.value}</div>
        </div>
      ))}
    </div>
  );
};
