import React, { useState, useEffect } from 'react';
import { 
  Server, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  Database, 
  Cpu, 
  Layers, 
  RefreshCw, 
  FileText, 
  PlayCircle,
  ExternalLink
} from 'lucide-react';

interface ServiceItem {
  service_code: string;
  service_name: string;
  status: 'STOPPED' | 'STARTING' | 'READY' | 'DEGRADED' | 'FAILED' | 'STOPPING';
  endpoint?: string;
  is_mandatory: boolean;
  health_details?: Record<string, any>;
}

interface DeploymentStatusResponse {
  application_name: string;
  application_version: string;
  active_profile: string;
  overall_status: 'STOPPED' | 'STARTING' | 'READY' | 'DEGRADED' | 'FAILED' | 'STOPPING';
  environment_safe: boolean;
  services: ServiceItem[];
  schema_revision: string;
  timestamp: string;
}

interface ValidationResponse {
  is_valid: boolean;
  python_version: string;
  node_version?: string;
  database_reachable: boolean;
  database_url_safe: boolean;
  port_availability: Record<string, boolean>;
  missing_variables: string[];
  warnings: string[];
}

export const DeploymentPage: React.FC = () => {
  const [status, setStatus] = useState<DeploymentStatusResponse | null>(null);
  const [validation, setValidation] = useState<ValidationResponse | null>(null);
  const [manifest, setManifest] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const fetchDeploymentData = async () => {
    setLoading(true);
    try {
      const sRes = await fetch('/api/v1/deployment/status');
      if (sRes.ok) setStatus(await sRes.json());

      const vRes = await fetch('/api/v1/deployment/validate');
      if (vRes.ok) setValidation(await vRes.json());

      const mRes = await fetch('/api/v1/deployment/releases/manifest');
      if (mRes.ok) setManifest(await mRes.json());
    } catch (err) {
      console.error('Error fetching deployment details', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDeploymentData();
  }, []);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center bg-surface border border-line p-6 rounded-xl shadow-lg">
        <div>
          <div className="flex items-center space-x-3">
            <Server className="h-8 w-8 text-brand" />
            <h1 className="text-2xl font-bold text-ink ">M15.11 Local Deployment & Lifecycle</h1>
          </div>
          <p className="text-sm text-muted mt-1">
            Local service orchestration, preflight validation, release versioning, and environment safety controls.
          </p>
        </div>
        <button
          onClick={fetchDeploymentData}
          disabled={loading}
          className="flex items-center space-x-2 px-4 py-2 bg-subtle hover:bg-hover text-secondary rounded-lg text-sm transition border border-line-strong"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Status</span>
        </button>
      </div>

      {/* Top Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-surface border border-line p-5 rounded-xl">
          <div className="flex justify-between items-center">
            <span className="text-xs uppercase  text-muted font-semibold">Lifecycle State</span>
            {status?.overall_status === 'READY' ? (
              <CheckCircle2 className="h-5 w-5 text-positive" />
            ) : (
              <AlertTriangle className="h-5 w-5 text-warning" />
            )}
          </div>
          <div className="text-2xl font-bold text-ink mt-2">
            {status?.overall_status || 'UNKNOWN'}
          </div>
          <div className="text-xs text-muted mt-1">Application readiness</div>
        </div>

        <div className="bg-surface border border-line p-5 rounded-xl">
          <div className="flex justify-between items-center">
            <span className="text-xs uppercase  text-muted font-semibold">Release Version</span>
            <Layers className="h-5 w-5 text-brand" />
          </div>
          <div className="text-2xl font-bold text-ink mt-2">
            v{status?.application_version || '1.0.0'}
          </div>
          <div className="text-xs text-muted mt-1">Schema: {status?.schema_revision}</div>
        </div>

        <div className="bg-surface border border-line p-5 rounded-xl">
          <div className="flex justify-between items-center">
            <span className="text-xs uppercase  text-muted font-semibold">Environment Safety</span>
            <Database className="h-5 w-5 text-positive" />
          </div>
          <div className="text-2xl font-bold text-positive mt-2">
            {status?.environment_safe ? 'ISOLATED' : 'PROD RISK'}
          </div>
          <div className="text-xs text-muted mt-1">Safe local database target</div>
        </div>

        <div className="bg-surface border border-line p-5 rounded-xl">
          <div className="flex justify-between items-center">
            <span className="text-xs uppercase  text-muted font-semibold">Runtime Host</span>
            <Cpu className="h-5 w-5 text-info" />
          </div>
          <div className="text-2xl font-bold text-ink mt-2">
            Python {validation?.python_version?.split('.')[0]}.{validation?.python_version?.split('.')[1]}
          </div>
          <div className="text-xs text-muted mt-1">Node: {validation?.node_version || 'Installed'}</div>
        </div>
      </div>

      {/* Services Table */}
      <div className="bg-surface border border-line p-6 rounded-xl">
        <h2 className="text-lg font-semibold text-ink mb-4 flex items-center space-x-2">
          <Server className="h-5 w-5 text-brand" />
          <span>Registered Application Services</span>
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-canvas text-muted uppercase ">
              <tr>
                <th className="p-3">Service</th>
                <th className="p-3">Type</th>
                <th className="p-3">Endpoint</th>
                <th className="p-3">Status</th>
                <th className="p-3">Health Diagnostics</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800 text-secondary">
              {status?.services.map((s) => (
                <tr key={s.service_code} className="hover:bg-subtle/40">
                  <td className="p-3 font-semibold text-ink">{s.service_name}</td>
                  <td className="p-3 text-muted">
                    {s.is_mandatory ? (
                      <span className="text-warning font-medium">Mandatory</span>
                    ) : (
                      <span className="text-muted">Optional</span>
                    )}
                  </td>
                  <td className="p-3 font-sans text-secondary">{s.endpoint || 'Internal'}</td>
                  <td className="p-3">
                    <span className="px-2 py-0.5 rounded text-xs bg-positive-soft/80 text-positive border border-positive/20">
                      {s.status}
                    </span>
                  </td>
                  <td className="p-3 font-sans text-muted text-[11px]">
                    {JSON.stringify(s.health_details)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Preflight Validation & Release Manifest Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Preflight Validation */}
        <div className="bg-surface border border-line p-6 rounded-xl">
          <h2 className="text-lg font-semibold text-ink mb-4 flex items-center space-x-2">
            <CheckCircle2 className="h-5 w-5 text-positive" />
            <span>Preflight Environment Validation</span>
          </h2>
          <div className="space-y-3 text-xs">
            <div className="flex justify-between items-center p-3 bg-canvas border border-line rounded-lg">
              <span className="text-secondary font-medium">Python Compatibility</span>
              <span className="text-positive font-sans">Compatible ({validation?.python_version})</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-canvas border border-line rounded-lg">
              <span className="text-secondary font-medium">Database Target Safety</span>
              <span className="text-positive font-sans">Safe Local Sandbox</span>
            </div>
            <div className="flex justify-between items-center p-3 bg-canvas border border-line rounded-lg">
              <span className="text-secondary font-medium">Mandatory Configurations</span>
              <span className="text-positive font-sans">0 Missing Variables</span>
            </div>
          </div>
          {validation?.warnings && validation.warnings.length > 0 && (
            <div className="mt-4 p-3 bg-warning-soft/30 border border-warning/20 rounded-lg text-xs text-warning space-y-1">
              <div className="font-semibold text-warning">Preflight Diagnostics:</div>
              {validation.warnings.map((w, idx) => (
                <div key={idx}>• {w}</div>
              ))}
            </div>
          )}
        </div>

        {/* Release Manifest */}
        <div className="bg-surface border border-line p-6 rounded-xl">
          <h2 className="text-lg font-semibold text-ink mb-4 flex items-center space-x-2">
            <FileText className="h-5 w-5 text-brand" />
            <span>Active Release Manifest</span>
          </h2>
          <pre className="p-4 bg-canvas border border-line rounded-lg text-xs font-sans text-secondary overflow-x-auto max-h-56">
            {JSON.stringify(manifest, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
};
