import React from 'react';
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
          <div key={i} className="bg-slate-900 border border-slate-800 rounded-lg p-4 animate-pulse h-20" />
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
      color: 'text-slate-100',
      bgColor: 'bg-slate-900/80',
      border: 'border-slate-800',
      icon: '🔔',
    },
    {
      label: 'Unacknowledged',
      value: unacknowledged,
      color: unacknowledged > 0 ? 'text-amber-400 font-bold' : 'text-slate-300',
      bgColor: unacknowledged > 0 ? 'bg-amber-950/30' : 'bg-slate-900/80',
      border: unacknowledged > 0 ? 'border-amber-800/60' : 'border-slate-800',
      icon: '📬',
    },
    {
      label: 'High Priority (P≥75)',
      value: highPriority,
      color: highPriority > 0 ? 'text-rose-400 font-bold' : 'text-slate-300',
      bgColor: highPriority > 0 ? 'bg-rose-950/30' : 'bg-slate-900/80',
      border: highPriority > 0 ? 'border-rose-800/60' : 'border-slate-800',
      icon: '🔥',
    },
    {
      label: 'Under Investigation',
      value: underInvestigation,
      color: 'text-indigo-400 font-semibold',
      bgColor: 'bg-slate-900/80',
      border: 'border-slate-800',
      icon: '🔍',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      {cards.map((c, idx) => (
        <div
          key={idx}
          className={`${c.bgColor} ${c.border} border rounded-lg p-3.5 flex flex-col justify-between shadow-sm transition hover:border-slate-700`}
        >
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>{c.label}</span>
            <span>{c.icon}</span>
          </div>
          <div className={`text-2xl mt-1 tracking-tight ${c.color}`}>{c.value}</div>
        </div>
      ))}
    </div>
  );
};
