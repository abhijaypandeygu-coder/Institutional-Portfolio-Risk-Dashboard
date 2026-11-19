import React, { useState, useEffect } from 'react';
import { 
  ShieldAlert, 
  Power, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  RefreshCw, 
  BookOpen, 
  Activity,
  Lock,
  Unlock
} from 'lucide-react';

interface KillSwitch {
  switch_code: string;
  switch_name: string;
  scope_type: string;
  scope_id?: string;
  state: 'INACTIVE' | 'ACTIVE' | 'REACTIVATION_PENDING' | 'RECOVERY_REQUIRED';
  activation_reason?: string;
  activated_by?: string;
  activated_at?: string;
  revision: number;
}

interface Incident {
  incident_reference: string;
  title: string;
  description?: string;
  severity: string;
  status: string;
  affected_scope: string;
  detected_at: string;
}

interface SafetyOverview {
  overall_safety_state: 'NORMAL' | 'DEGRADED' | 'BLOCKED' | 'RECOVERY_REQUIRED' | 'UNKNOWN';
  global_execution_enabled: boolean;
  active_kill_switches_count: number;
  active_incidents_count: number;
  safety_policy_version: string;
  kill_switches: KillSwitch[];
  incidents: Incident[];
  timestamp: string;
}

export const OperationalSafetyPage: React.FC = () => {
  const [safety, setSafety] = useState<SafetyOverview | null>(null);
  const [runbooks, setRunbooks] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [actionReason, setActionReason] = useState<string>('');
  const [actionMessage, setActionMessage] = useState<string>('');

  const fetchSafetyData = async () => {
    setLoading(true);
    try {
      const sRes = await fetch('/api/v1/operational-safety/status');
      if (sRes.ok) setSafety(await sRes.json());

      const rRes = await fetch('/api/v1/operational-safety/runbooks');
      if (rRes.ok) setRunbooks(await rRes.json());
    } catch (err) {
      console.error('Error fetching safety status', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSafetyData();
  }, []);

  const handleToggleGlobalKillSwitch = async (activate: boolean) => {
    if (activate && !actionReason.trim()) {
      setActionMessage('An explicit reason is required to activate the emergency kill switch.');
      return;
    }

    setLoading(true);
    setActionMessage('');
    try {
      if (activate) {
        const res = await fetch('/api/v1/operational-safety/kill-switches/activate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            switch_code: 'GLOBAL_EXECUTION',
            reason: actionReason || 'Emergency halt via Operator Dashboard',
            confirm_action: true,
            activated_by: 'Operator'
          })
        });
        if (res.ok) {
          setActionMessage('GLOBAL KILL SWITCH ACTIVATED. Live order submissions are blocked.');
          setActionReason('');
          fetchSafetyData();
        }
      } else {
        const res = await fetch('/api/v1/operational-safety/kill-switches/reactivate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            switch_code: 'GLOBAL_EXECUTION',
            reason: 'Deactivation confirmed after recovery verification',
            requested_by: 'Operator'
          })
        });
        if (res.ok) {
          setActionMessage('GLOBAL KILL SWITCH DEACTIVATED. Normal routing restored.');
          fetchSafetyData();
        }
      }
    } catch (err: any) {
      setActionMessage(`Operation failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center bg-surface border border-line p-6 rounded-xl shadow-lg">
        <div>
          <div className="flex items-center space-x-3">
            <ShieldAlert className="h-8 w-8 text-negative" />
            <h1 className="text-2xl font-bold text-ink ">M15.12 Operational Safety & Kill Switch</h1>
          </div>
          <p className="text-sm text-muted mt-1">
            Fail-closed execution protection, emergency kill switches, incident logs, and operational runbooks.
          </p>
        </div>
        <button
          onClick={fetchSafetyData}
          disabled={loading}
          className="flex items-center space-x-2 px-4 py-2 bg-subtle hover:bg-hover text-secondary rounded-lg text-sm transition border border-line-strong"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Safety State</span>
        </button>
      </div>

      {/* Primary Emergency Banner */}
      <div className={`p-6 rounded-xl border flex flex-col md:flex-row justify-between items-center gap-6 ${
        safety?.global_execution_enabled
          ? 'bg-surface/90 border-positive/20 shadow-lg'
          : 'bg-negative-soft/40 border-negative/20 shadow-2xl '
      }`}>
        <div className="flex items-center space-x-4">
          <div className={`p-3 rounded-full ${
            safety?.global_execution_enabled ? 'bg-positive-soft text-positive' : 'bg-negative-soft text-negative'
          }`}>
            <Power className="h-8 w-8" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-ink">
              {safety?.global_execution_enabled ? 'Live Execution Active (Normal)' : 'EMERGENCY HALT: Global Kill Switch ACTIVE'}
            </h2>
            <p className="text-xs text-muted mt-1">
              {safety?.global_execution_enabled
                ? 'Pre-trade safety gateway is verifying limit checks and market data freshness.'
                : 'All live-capable order routes and submissions are completely blocked fail-closed.'}
            </p>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row items-center gap-3 w-full md:w-auto">
          {safety?.global_execution_enabled ? (
            <>
              <input
                type="text"
                placeholder="Reason for emergency shutdown..."
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
                className="bg-canvas border border-line-strong text-ink text-xs rounded-lg px-3 py-2 w-full sm:w-64 focus:outline-none focus:border-rose-500"
              />
              <button
                onClick={() => handleToggleGlobalKillSwitch(true)}
                disabled={loading}
                className="w-full sm:w-auto px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white font-bold rounded-lg text-xs uppercase  shadow-lg flex items-center justify-center space-x-2 transition"
              >
                <Lock className="h-4 w-4" />
                <span>HALT EXECUTION</span>
              </button>
            </>
          ) : (
            <button
              onClick={() => handleToggleGlobalKillSwitch(false)}
              disabled={loading}
              className="w-full sm:w-auto px-5 py-2.5 bg-brand hover:bg-brand-hover text-white font-bold rounded-lg text-xs uppercase  shadow-lg flex items-center justify-center space-x-2 transition"
            >
              <Unlock className="h-4 w-4" />
              <span>RESTORE EXECUTION</span>
            </button>
          )}
        </div>
      </div>

      {actionMessage && (
        <div className="p-3 bg-canvas border border-line rounded-lg text-xs font-sans text-brand">
          {actionMessage}
        </div>
      )}

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-surface border border-line p-5 rounded-xl">
          <div className="text-xs uppercase  text-muted font-semibold">Safety State</div>
          <div className="text-2xl font-bold text-ink mt-2">{safety?.overall_safety_state || 'NORMAL'}</div>
          <div className="text-xs text-muted mt-1">Platform policy v1.0.0</div>
        </div>

        <div className="bg-surface border border-line p-5 rounded-xl">
          <div className="text-xs uppercase  text-muted font-semibold">Active Switches</div>
          <div className="text-2xl font-bold text-negative mt-2">{safety?.active_kill_switches_count || 0}</div>
          <div className="text-xs text-muted mt-1">Global & scoped restrictions</div>
        </div>

        <div className="bg-surface border border-line p-5 rounded-xl">
          <div className="text-xs uppercase  text-muted font-semibold">Active Incidents</div>
          <div className="text-2xl font-bold text-warning mt-2">{safety?.active_incidents_count || 0}</div>
          <div className="text-xs text-muted mt-1">Operational containment</div>
        </div>

        <div className="bg-surface border border-line p-5 rounded-xl">
          <div className="text-xs uppercase  text-muted font-semibold">Runbooks Ready</div>
          <div className="text-2xl font-bold text-brand mt-2">{runbooks.length} Available</div>
          <div className="text-xs text-muted mt-1">Verified recovery checklists</div>
        </div>
      </div>

      {/* Kill Switches Table */}
      <div className="bg-surface border border-line p-6 rounded-xl">
        <h2 className="text-lg font-semibold text-ink mb-4 flex items-center space-x-2">
          <Power className="h-5 w-5 text-negative" />
          <span>Kill Switch Registry</span>
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-canvas text-muted uppercase ">
              <tr>
                <th className="p-3">Switch Name</th>
                <th className="p-3">Scope</th>
                <th className="p-3">State</th>
                <th className="p-3">Revision</th>
                <th className="p-3">Last Activation Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800 text-secondary">
              {safety?.kill_switches.map((sw) => (
                <tr key={sw.switch_code} className="hover:bg-subtle/40">
                  <td className="p-3 font-semibold text-ink">{sw.switch_name}</td>
                  <td className="p-3 text-muted font-sans">{sw.scope_type}</td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                      sw.state === 'ACTIVE'
                        ? 'bg-negative-soft/80 text-negative border border-negative/20'
                        : 'bg-positive-soft/80 text-positive border border-positive/20'
                    }`}>
                      {sw.state}
                    </span>
                  </td>
                  <td className="p-3 font-sans text-muted">rev.{sw.revision}</td>
                  <td className="p-3 text-muted">
                    {sw.activation_reason ? `${sw.activation_reason} (by ${sw.activated_by})` : 'Nominal'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Incident & Runbooks Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Incidents */}
        <div className="bg-surface border border-line p-6 rounded-xl">
          <h2 className="text-lg font-semibold text-ink mb-4 flex items-center space-x-2">
            <Activity className="h-5 w-5 text-warning" />
            <span>Incident Log</span>
          </h2>
          <div className="space-y-3">
            {safety?.incidents.map((inc) => (
              <div key={inc.incident_reference} className="p-3 bg-canvas border border-line rounded-lg text-xs space-y-1">
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-ink">{inc.title}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] bg-warning-soft/60 text-warning border border-warning/20">
                    {inc.severity}
                  </span>
                </div>
                <div className="text-muted">{inc.description}</div>
                <div className="text-muted text-[10px] font-sans">Ref: {inc.incident_reference} • Scope: {inc.affected_scope}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Runbooks */}
        <div className="bg-surface border border-line p-6 rounded-xl">
          <h2 className="text-lg font-semibold text-ink mb-4 flex items-center space-x-2">
            <BookOpen className="h-5 w-5 text-brand" />
            <span>Operational Runbooks & Checklists</span>
          </h2>
          <div className="space-y-4">
            {runbooks.map((rb) => (
              <div key={rb.runbook_code} className="p-3 bg-canvas border border-line rounded-lg text-xs space-y-2">
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-ink">{rb.title}</span>
                  <span className="text-[10px] font-sans text-brand">{rb.runbook_code}</span>
                </div>
                <p className="text-muted">{rb.summary}</p>
                <div className="pl-3 border-l border-line space-y-1 text-secondary font-sans text-[11px]">
                  {rb.steps.map((st: string, idx: number) => (
                    <div key={idx}>{st}</div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
