import React from 'react';
import { Bell, Mail, Flame, Search } from 'lucide-react';
import { RecentAlertSummaryResponse } from '../../../../types/dashboard';

interface RecentAlertSummaryProps {
  summary: RecentAlertSummaryResponse | null;
  loading: boolean;
}

export const RecentAlertSummary: React.FC<RecentAlertSummaryProps> = ({ summary, loading }) => {
  if (loading && !summary) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-surface border border-line rounded-lg p-4  h-20" />
        ))}
      </div>
    );
  }

  const totalAlerts = summary?.counts?.total_alerts ?? summary?.total_alerts_24h ?? 0;
  const unacknowledged = summary?.counts?.unacknowledged ?? summary?.unacknowledged_alerts ?? 0;
  const highPriority = summary?.counts?.high_priority ?? summary?.high_priority_alerts ?? 0;
  const underInvestigation = summary?.counts?.under_investigation ?? summary?.under_investigation ?? 0;

  const cards = [
    {
      label: 'Alerts (Last 24h)',
      value: totalAlerts,
      color: 'text-ink',
      bgColor: 'bg-surface/80',
      border: 'border-line',
      icon: Bell,
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
      label: 'High Priority (P≥75)',
      value: highPriority,
      color: highPriority > 0 ? 'text-negative font-bold' : 'text-secondary',
      bgColor: highPriority > 0 ? 'bg-negative-soft/30' : 'bg-surface/80',
      border: highPriority > 0 ? 'border-negative/20' : 'border-line',
      icon: Flame,
    },
    {
      label: 'Under Investigation',
      value: underInvestigation,
      color: 'text-brand font-semibold',
      bgColor: 'bg-surface/80',
      border: 'border-line',
      icon: Search,
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      {cards.map((c, idx) => {
        const Icon = c.icon;
        return (
          <div
            key={idx}
            className={`${c.bgColor} ${c.border} border rounded-lg p-3.5 flex flex-col justify-between shadow-sm transition hover:border-line-strong`}
          >
            <div className="flex items-center justify-between text-xs text-muted">
              <span>{c.label}</span>
              <Icon className="size-3.5 opacity-70" />
            </div>
            <div className={`text-2xl mt-1  ${c.color}`}>{c.value}</div>
          </div>
        );
      })}
    </div>
  );
};
