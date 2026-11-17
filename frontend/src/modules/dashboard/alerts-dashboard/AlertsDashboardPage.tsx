import React, { useState, useEffect, useCallback } from 'react';
import {
  ActiveBreachSummaryResponse,
  ActiveBreachItem,
  RecentAlertSummaryResponse,
  AlertFeedItem,
  AlertDetailResponse,
  AlertTimelineEvent,
  AlertsPreferenceResponse,
  AlertsSavedViewResponse,
} from '../../../types/dashboard';
import { ActiveBreachSummary } from './components/ActiveBreachSummary';
import { ActiveBreachTable } from './components/ActiveBreachTable';
import { RecentAlertSummary } from './components/RecentAlertSummary';
import { RecentAlertFeed } from './components/RecentAlertFeed';
import { AlertDetailDrawer } from './components/AlertDetailDrawer';

export const AlertsDashboardPage: React.FC = () => {
  // Filters & Controls
  const [selectedPortfolioId, setSelectedPortfolioId] = useState<string>('');
  const [availablePortfolios, setAvailablePortfolios] = useState<Array<{ portfolio_id: string; portfolio_name: string }>>([]);
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'all' | 'breaches' | 'alerts'>('all');
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);
  const [refreshInterval, setRefreshInterval] = useState<number>(10); // seconds

  // Fetch available portfolios dynamically
  useEffect(() => {
    const fetchPortfolios = async () => {
      try {
        const res = await fetch('/api/v1/portfolios?limit=50');
        if (res.ok) {
          const list = await res.json();
          if (Array.isArray(list)) {
            setAvailablePortfolios(list);
          }
        }
      } catch (err) {
        console.error('Failed to load portfolios for alerts dashboard:', err);
      }
    };
    fetchPortfolios();
  }, []);

  // Data States
  const [breachSummary, setBreachSummary] = useState<ActiveBreachSummaryResponse | null>(null);
  const [breaches, setBreaches] = useState<ActiveBreachItem[]>([]);
  const [alertSummary, setAlertSummary] = useState<RecentAlertSummaryResponse | null>(null);
  const [alertFeed, setAlertFeed] = useState<AlertFeedItem[]>([]);
  const [selectedAlertDetail, setSelectedAlertDetail] = useState<AlertDetailResponse | null>(null);
  const [alertHistory, setAlertHistory] = useState<AlertTimelineEvent[]>([]);
  const [preferences, setPreferences] = useState<AlertsPreferenceResponse | null>(null);
  const [savedViews, setSavedViews] = useState<AlertsSavedViewResponse[]>([]);

  // Loading & Feedback
  const [loading, setLoading] = useState<boolean>(false);
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);
  const [bannerMessage, setBannerMessage] = useState<{ text: string; type: 'info' | 'warn' | 'success' } | null>(null);

  // Fetch Summaries & Feeds
  const fetchData = useCallback(async () => {
    try {
      // 1. Breach Summary & List
      const breachSumParams = new URLSearchParams();
      if (selectedPortfolioId) breachSumParams.append('portfolio_id', selectedPortfolioId);
      const bSumRes = await fetch(`/api/v1/dashboard/alerts/breaches/summary?${breachSumParams.toString()}`);
      if (bSumRes.ok) {
        setBreachSummary(await bSumRes.json());
      }

      const breachListParams = new URLSearchParams();
      if (selectedPortfolioId) breachListParams.append('portfolio_id', selectedPortfolioId);
      if (severityFilter) breachListParams.append('severity', severityFilter);
      const bListRes = await fetch(`/api/v1/dashboard/alerts/breaches?${breachListParams.toString()}`);
      if (bListRes.ok) {
        const bData = await bListRes.json();
        setBreaches(Array.isArray(bData) ? bData : (bData.items || []));
      }

      // 2. Alert Summary & Feed
      const alertSumParams = new URLSearchParams();
      if (selectedPortfolioId) alertSumParams.append('portfolio_id', selectedPortfolioId);
      const aSumRes = await fetch(`/api/v1/dashboard/alerts/summary?${alertSumParams.toString()}`);
      if (aSumRes.ok) {
        setAlertSummary(await aSumRes.json());
      }

      const alertFeedParams = new URLSearchParams();
      if (selectedPortfolioId) alertFeedParams.append('portfolio_id', selectedPortfolioId);
      if (severityFilter) alertFeedParams.append('severity', severityFilter);
      if (statusFilter) alertFeedParams.append('status', statusFilter);
      const aFeedRes = await fetch(`/api/v1/dashboard/alerts/feed?${alertFeedParams.toString()}`);
      if (aFeedRes.ok) {
        const aData = await aFeedRes.json();
        setAlertFeed(Array.isArray(aData) ? aData : (aData.items || []));
      }
    } catch (err) {
      console.error('Error fetching alerts dashboard data:', err);
    }
  }, [selectedPortfolioId, severityFilter, statusFilter]);

  // Initial & Auto Refresh
  useEffect(() => {
    setLoading(true);
    fetchData().finally(() => setLoading(false));
  }, [fetchData]);

  useEffect(() => {
    if (!autoRefresh) return;
    const timer = setInterval(() => {
      fetchData();
    }, refreshInterval * 1000);
    return () => clearInterval(timer);
  }, [autoRefresh, refreshInterval, fetchData]);

  // Load Preferences & Views
  useEffect(() => {
    const fetchPrefs = async () => {
      try {
        const pRes = await fetch('/api/v1/dashboard/alerts/preferences/me');
        if (pRes.ok) {
          const p = await pRes.json();
          setPreferences(p);
          if (p.auto_refresh_interval_sec) setRefreshInterval(p.auto_refresh_interval_sec);
        }
        const vRes = await fetch('/api/v1/dashboard/alerts/saved-views');
        if (vRes.ok) {
          setSavedViews(await vRes.json());
        }
      } catch (err) {
        console.error('Error loading preferences:', err);
      }
    };
    fetchPrefs();
  }, []);

  // Fetch Alert Detail & History
  const handleSelectAlert = async (item: AlertFeedItem) => {
    try {
      const dRes = await fetch(`/api/v1/dashboard/alerts/${item.alert_id}`);
      if (dRes.ok) {
        setSelectedAlertDetail(await dRes.json());
      }
      setHistoryLoading(true);
      const hRes = await fetch(`/api/v1/dashboard/alerts/${item.alert_id}/history`);
      if (hRes.ok) {
        const h = await hRes.json();
        setAlertHistory(h.events || []);
      }
    } catch (err) {
      console.error('Error fetching alert details:', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  // Actions
  const handleAcknowledgeAlert = async (alertId: string, notes?: string) => {
    const res = await fetch(`/api/v1/dashboard/alerts/${alertId}/acknowledge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes }),
    });
    if (res.ok) {
      const data = await res.json();
      setBannerMessage({ text: data.message, type: 'success' });
      fetchData();
      if (selectedAlertDetail?.alert_id === alertId) {
        handleSelectAlert({ ...selectedAlertDetail, alert_id: alertId } as AlertFeedItem);
      }
    }
  };

  const handleAssignAlert = async (alertId: string, assignedTo: string, notes?: string) => {
    const res = await fetch(`/api/v1/dashboard/alerts/${alertId}/assign`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assigned_to: assignedTo, notes }),
    });
    if (res.ok) {
      const data = await res.json();
      setBannerMessage({ text: data.message, type: 'success' });
      fetchData();
      if (selectedAlertDetail?.alert_id === alertId) {
        handleSelectAlert({ ...selectedAlertDetail, alert_id: alertId } as AlertFeedItem);
      }
    }
  };

  const handleCloseAlert = async (alertId: string, rationale: string, notes?: string) => {
    const res = await fetch(`/api/v1/dashboard/alerts/${alertId}/close`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resolution_rationale: rationale, notes }),
    });
    if (res.ok) {
      const data = await res.json();
      setBannerMessage({
        text: data.warning_note ? `${data.message} (${data.warning_note})` : data.message,
        type: data.warning_note ? 'warn' : 'success',
      });
      fetchData();
      if (selectedAlertDetail?.alert_id === alertId) {
        handleSelectAlert({ ...selectedAlertDetail, alert_id: alertId } as AlertFeedItem);
      }
    }
  };

  const handleReopenAlert = async (alertId: string, notes?: string) => {
    const res = await fetch(`/api/v1/dashboard/alerts/${alertId}/reopen`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes }),
    });
    if (res.ok) {
      const data = await res.json();
      setBannerMessage({ text: data.message, type: 'info' });
      fetchData();
      if (selectedAlertDetail?.alert_id === alertId) {
        handleSelectAlert({ ...selectedAlertDetail, alert_id: alertId } as AlertFeedItem);
      }
    }
  };

  const handleAcknowledgeBreach = async (breachId: string) => {
    const res = await fetch(`/api/v1/dashboard/alerts/breaches/${breachId}/acknowledge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes: 'Acknowledged via Institutional Alerts Dashboard' }),
    });
    if (res.ok) {
      const data = await res.json();
      setBannerMessage({ text: data.message, type: 'success' });
      fetchData();
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6 space-y-6">
      {/* Top Banner / Breadcrumb */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-800 gap-4">
        <div>
          <div className="text-xs uppercase tracking-wider text-slate-400 font-mono">
            M13 Dashboard & Visualization Layer / M13.08
          </div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight">Institutional Alerts Dashboard</h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time monitoring of active risk-limit breaches (M11) and dynamic risk alerts (M12).
          </p>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Portfolio filter */}
          <select
            value={selectedPortfolioId}
            onChange={(e) => setSelectedPortfolioId(e.target.value)}
            className="px-3 py-1.5 bg-slate-900 border border-slate-700 rounded text-xs text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
          >
            <option value="">All Portfolios</option>
            {availablePortfolios.map((p) => (
              <option key={p.portfolio_id} value={p.portfolio_id}>
                {p.portfolio_name ? `${p.portfolio_id} (${p.portfolio_name})` : p.portfolio_id}
              </option>
            ))}
          </select>

          {/* Severity filter */}
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="px-3 py-1.5 bg-slate-900 border border-slate-700 rounded text-xs text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
          >
            <option value="">All Severities</option>
            <option value="EMERGENCY">Emergency (L3)</option>
            <option value="CRITICAL">Critical (L2)</option>
            <option value="WARNING">Warning (L1)</option>
            <option value="INFO">Info</option>
          </select>

          {/* Status filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 bg-slate-900 border border-slate-700 rounded text-xs text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
          >
            <option value="">All Statuses</option>
            <option value="TRIGGERED">Triggered</option>
            <option value="ACKNOWLEDGED">Acknowledged</option>
            <option value="INVESTIGATING">Investigating</option>
            <option value="ESCALATED">Escalated</option>
            <option value="RESOLVED">Resolved</option>
            <option value="CLOSED">Closed</option>
          </select>

          {/* Auto Refresh Toggle */}
          <button
            type="button"
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-3 py-1.5 rounded text-xs font-mono border transition ${
              autoRefresh
                ? 'bg-emerald-950/60 border-emerald-700 text-emerald-300'
                : 'bg-slate-900 border-slate-700 text-slate-400'
            }`}
          >
            Auto {autoRefresh ? `ON (${refreshInterval}s)` : 'OFF'}
          </button>

          <button
            type="button"
            onClick={() => fetchData()}
            className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-semibold transition"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Banner Notice */}
      {bannerMessage && (
        <div
          className={`p-3 rounded text-xs flex items-center justify-between border ${
            bannerMessage.type === 'warn'
              ? 'bg-amber-950/70 border-amber-700 text-amber-200'
              : bannerMessage.type === 'info'
              ? 'bg-blue-950/70 border-blue-700 text-blue-200'
              : 'bg-emerald-950/70 border-emerald-700 text-emerald-200'
          }`}
        >
          <span>{bannerMessage.text}</span>
          <button
            type="button"
            onClick={() => setBannerMessage(null)}
            className="ml-4 text-xs font-mono hover:opacity-75"
          >
            ✕
          </button>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex border-b border-slate-800 space-x-4 text-xs">
        <button
          type="button"
          onClick={() => setActiveTab('all')}
          className={`pb-2.5 font-medium transition ${
            activeTab === 'all'
              ? 'border-b-2 border-indigo-500 text-indigo-400 font-bold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          All Activity & Metrics
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('breaches')}
          className={`pb-2.5 font-medium transition flex items-center gap-1.5 ${
            activeTab === 'breaches'
              ? 'border-b-2 border-indigo-500 text-indigo-400 font-bold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>Active Limit Breaches</span>
          {(breachSummary?.total_active_breaches || 0) > 0 && (
            <span className="px-1.5 py-0.2 bg-red-900 text-red-200 rounded-full text-[10px] font-mono">
              {breachSummary?.total_active_breaches}
            </span>
          )}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('alerts')}
          className={`pb-2.5 font-medium transition flex items-center gap-1.5 ${
            activeTab === 'alerts'
              ? 'border-b-2 border-indigo-500 text-indigo-400 font-bold'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>Alerts Feed</span>
          {(alertSummary?.unacknowledged_alerts || 0) > 0 && (
            <span className="px-1.5 py-0.2 bg-amber-900 text-amber-200 rounded-full text-[10px] font-mono">
              {alertSummary?.unacknowledged_alerts}
            </span>
          )}
        </button>
      </div>

      {/* Main Content Area */}
      {(activeTab === 'all' || activeTab === 'breaches') && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs uppercase font-mono tracking-wider text-slate-400">
              Risk Limits & Control Framework (M11 Authoritative Breaches)
            </h2>
          </div>
          <ActiveBreachSummary summary={breachSummary} loading={loading} />
          <ActiveBreachTable
            breaches={breaches}
            loading={loading}
            onSelectBreach={(b) => {
              const utilText = b.utilization_pct !== undefined ? `${b.utilization_pct.toFixed(1)}%` : (b.utilization ? `${Number(b.utilization).toFixed(1)}%` : '—');
              setBannerMessage({
                text: `Selected Breach: ${b.rule_name || b.risk_limit_id || b.breach_id} (${b.breach_id}) — Utilization: ${utilText}`,
                type: 'info',
              });
            }}
            onAcknowledgeBreach={handleAcknowledgeBreach}
          />
        </section>
      )}

      {(activeTab === 'all' || activeTab === 'alerts') && (
        <section className="space-y-3 pt-2">
          <div className="flex items-center justify-between">
            <h2 className="text-xs uppercase font-mono tracking-wider text-slate-400">
              Risk Alerts & Notification Subsystem (M12 Activity Stream)
            </h2>
          </div>
          <RecentAlertSummary summary={alertSummary} loading={loading} />
          <RecentAlertFeed
            alerts={alertFeed}
            loading={loading}
            selectedAlertId={selectedAlertDetail?.alert_id}
            onSelectAlert={handleSelectAlert}
            onQuickAcknowledge={(alertId) => handleAcknowledgeAlert(alertId)}
          />
        </section>
      )}

      {/* Detail Drawer */}
      <AlertDetailDrawer
        alert={selectedAlertDetail}
        historyEvents={alertHistory}
        loading={historyLoading}
        onClose={() => setSelectedAlertDetail(null)}
        onAcknowledge={handleAcknowledgeAlert}
        onAssign={handleAssignAlert}
        onCloseAlert={handleCloseAlert}
        onReopen={handleReopenAlert}
      />
    </div>
  );
};

export default AlertsDashboardPage;
