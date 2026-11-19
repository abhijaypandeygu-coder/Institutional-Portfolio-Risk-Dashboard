import React from 'react';
import { 
  ShieldAlert, 
  AlertOctagon, 
  AlertTriangle, 
  Zap, 
  Mail, 
  ArrowUpRight, 
  Clock 
} from 'lucide-react';
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
          <div key={i} className="bg-surface border border-line rounded-lg p-4  h-24" />
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
      color: 'text-ink',
      bgColor: 'bg-surface/80',
      border: 'border-line',
      icon: ShieldAlert,
    },
    {
      label: 'Emergency (L3)',
      value: emergency,
      color: 'text-negative font-bold',
      bgColor: emergency > 0 ? 'bg-negative-soft/40' : 'bg-surface/80',
      border: emergency > 0 ? 'border-negative/20' : 'border-line',
      icon: AlertOctagon,
    },
    {
      label: 'Critical (L2)',
      value: critical,
      color: 'text-orange-400 font-bold',
      bgColor: critical > 0 ? 'bg-orange-950/40' : 'bg-surface/80',
      border: critical > 0 ? 'border-orange-800' : 'border-line',
      icon: AlertTriangle,
    },
    {
      label: 'Warning (L1)',
      value: warning,
      color: 'text-yellow-400 font-semibold',
      bgColor: 'bg-surface/80',
      border: 'border-line',
      icon: Zap,
    },
    {
      label: 'Unacknowledged',
      value: unacknowledged,
      color: unacknowledged > 0 ? 'text-warning font-bold' : 'text-secondary',
      bgColor: unacknowledged > 0 ? 'bg-warning-soft/30' : 'bg-surface/80',
      border: unacknowledged > 0 ? 'border-warning/20' : 'border-line',
      icon: Mail,
    },
    {
      label: 'Awaiting Remediation',
      value: escalated,
      color: 'text-info font-semibold',
      bgColor: 'bg-surface/80',
      border: 'border-line',
      icon: ArrowUpRight,
    },
    {
      label: 'Overdue SLA',
      value: overdueSla,
      color: overdueSla > 0 ? 'text-negative font-bold' : 'text-muted',
      bgColor: overdueSla > 0 ? 'bg-negative-soft/40 ' : 'bg-surface/80',
      border: overdueSla > 0 ? 'border-negative/20' : 'border-line',
      icon: Clock,
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 mb-6">
      {cards.map((c, idx) => {
        const Icon = c.icon;
        return (
          <div
            key={idx}
            className={`${c.bgColor} ${c.border} border rounded-lg p-3 flex flex-col justify-between shadow-sm transition hover:border-line-strong`}
          >
            <div className="flex items-center justify-between text-xs text-muted">
              <span>{c.label}</span>
              <Icon className="size-3.5 opacity-70" />
            </div>
            <div className={`text-2xl mt-2  ${c.color}`}>{c.value}</div>
          </div>
        );
      })}
    </div>
  );
};
