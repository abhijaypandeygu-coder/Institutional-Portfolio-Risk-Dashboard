import React, { useState, useEffect } from 'react';
import {
  ReportArchiveSummary,
  ReportArchiveDetail,
  VersionComparison,
  RetentionEvaluationResponse,
} from '../../../types/reportArchive';
import { ArchiveFilterBar } from './components/ArchiveFilterBar';
import { ArchiveResultsTable } from './components/ArchiveResultsTable';
import { ArchiveDetailDrawer } from './components/ArchiveDetailDrawer';

export const HistoricalReportArchivePage: React.FC = () => {
  const [archives, setArchives] = useState<ReportArchiveSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [selectedDetail, setSelectedDetail] = useState<ReportArchiveDetail | null>(null);
  const [versionHistory, setVersionHistory] = useState<ReportArchiveSummary[]>([]);
  const [comparison, setComparison] = useState<VersionComparison | null>(null);
  const [retentionDryRun, setRetentionDryRun] = useState<RetentionEvaluationResponse | null>(null);

  // Filters
  const [portfolioId, setPortfolioId] = useState<string>('PORT-001');
  const [reportType, setReportType] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [runIdFilter, setRunIdFilter] = useState<string>('');

  const fetchArchives = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (portfolioId) params.append('portfolio_id', portfolioId);
      if (reportType) params.append('report_type', reportType);
      if (statusFilter) params.append('status', statusFilter);
      if (runIdFilter) params.append('report_run_id', runIdFilter);

      const res = await fetch(`/api/v1/report-archive?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setArchives(data.items || []);
      }
    } catch (e) {
      console.error('Failed to load archives', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchArchives();
  }, []);

  const handleSelectArchive = async (archiveId: string) => {
    try {
      const resDetail = await fetch(`/api/v1/report-archive/${archiveId}`);
      if (resDetail.ok) {
        const detail = await resDetail.json();
        setSelectedDetail(detail);

        // Fetch version history
        const resHist = await fetch(`/api/v1/report-archive/${archiveId}/versions`);
        if (resHist.ok) {
          const hist = await resHist.json();
          setVersionHistory(hist);
        }
      }
    } catch (e) {
      console.error('Failed to load archive details', e);
    }
  };

  const handleDownload = (archiveId: string) => {
    window.open(`/api/v1/report-archive/${archiveId}/download`, '_blank');
  };

  const handleVerifyIntegrity = async (archiveId: string) => {
    try {
      const res = await fetch(`/api/v1/report-archive/${archiveId}/integrity`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        alert(`Integrity Verification: ${data.integrity_status}\nHash: ${data.calculated_hash}`);
        fetchArchives();
      }
    } catch (e) {
      alert('Integrity check failed');
    }
  };

  const handleCompareVersions = async (baseId: string, otherId: string) => {
    try {
      const res = await fetch(`/api/v1/report-archive/${baseId}/compare/${otherId}`);
      if (res.ok) {
        const data = await res.json();
        setComparison(data);
      }
    } catch (e) {
      console.error('Failed to compare versions', e);
    }
  };

  const handleApplyLegalHold = async (archiveId: string, reason: string) => {
    try {
      const res = await fetch('/api/v1/report-archive/legal-holds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          archive_id: archiveId,
          reason,
          initiated_by: 'COMPLIANCE_OFFICER',
        }),
      });
      if (res.ok) {
        alert('Compliance legal hold successfully placed.');
        handleSelectArchive(archiveId);
        fetchArchives();
      }
    } catch (e) {
      alert('Failed to place legal hold');
    }
  };

  const handleRunDryRun = async () => {
    try {
      const res = await fetch('/api/v1/report-archive/retention/dry-run');
      if (res.ok) {
        const data = await res.json();
        setRetentionDryRun(data);
      }
    } catch (e) {
      console.error('Dry-run failed', e);
    }
  };

  return (
    <div className="min-h-screen bg-canvas text-ink p-6">
      <div className="max-w-7xl mx-auto">
        <header className="mb-6 flex justify-between items-center border-b border-line pb-4">
          <div>
            <h1 className="text-2xl font-black  text-ink flex items-center gap-2">
              <span className="text-brand">M14.08</span> Historical Report Archive
            </h1>
            <p className="text-xs text-muted mt-1">
              Institutional-grade immutable report preservation, cryptographic integrity verification, and provenance tracking.
            </p>
          </div>
          <div className="flex gap-2">
            <span className="text-xs bg-surface border border-line text-secondary px-3 py-1.5 rounded font-sans">
              Total Preserved: <strong className="text-brand">{archives.length}</strong>
            </span>
          </div>
        </header>

        {/* Filter Bar */}
        <ArchiveFilterBar
          portfolioId={portfolioId}
          setPortfolioId={setPortfolioId}
          reportType={reportType}
          setReportType={setReportType}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
          runIdFilter={runIdFilter}
          setRunIdFilter={setRunIdFilter}
          onSearch={fetchArchives}
          onReset={() => {
            setPortfolioId('');
            setReportType('');
            setStatusFilter('');
            setRunIdFilter('');
          }}
          onRunDryRun={handleRunDryRun}
        />

        {/* Results Table */}
        <ArchiveResultsTable
          items={archives}
          loading={loading}
          onSelectArchive={handleSelectArchive}
          onDownload={handleDownload}
          onVerifyIntegrity={handleVerifyIntegrity}
        />

        {/* Detail Drawer */}
        {selectedDetail && (
          <ArchiveDetailDrawer
            detail={selectedDetail}
            versionHistory={versionHistory}
            onClose={() => setSelectedDetail(null)}
            onDownload={handleDownload}
            onCompareVersions={handleCompareVersions}
            onApplyLegalHold={handleApplyLegalHold}
          />
        )}

        {/* Version Comparison Modal */}
        {comparison && (
          <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
            <div className="bg-surface border border-line rounded-lg max-w-2xl w-full p-6 max-h-[85vh] overflow-y-auto">
              <div className="flex justify-between items-center mb-4 border-b border-line pb-3">
                <h3 className="font-bold text-ink text-sm">
                  Comparing v{comparison.base_archive.version_number} vs v{comparison.compared_archive.version_number}
                </h3>
                <button onClick={() => setComparison(null)} className="text-muted hover:text-ink">&times;</button>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs mb-4">
                <div className="bg-canvas p-3 rounded">
                  <div className="font-bold text-brand">Base: {comparison.base_archive.archive_id}</div>
                  <div className="text-muted font-sans mt-1">NAV: {comparison.base_archive.summary_nav || 'N/A'}</div>
                  <div className="text-muted font-sans">VaR: {comparison.base_archive.summary_var_value || 'N/A'}</div>
                </div>
                <div className="bg-canvas p-3 rounded">
                  <div className="font-bold text-positive">Target: {comparison.compared_archive.archive_id}</div>
                  <div className="text-muted font-sans mt-1">NAV: {comparison.compared_archive.summary_nav || 'N/A'}</div>
                  <div className="text-muted font-sans">VaR: {comparison.compared_archive.summary_var_value || 'N/A'}</div>
                </div>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <h4 className="font-semibold text-secondary mb-1">Model Changes</h4>
                  {comparison.model_changes.length > 0 ? (
                    <ul className="list-disc pl-5 text-muted">
                      {comparison.model_changes.map((c, i) => <li key={i}>{c}</li>)}
                    </ul>
                  ) : <span className="text-muted">No model specification changes.</span>}
                </div>

                <div>
                  <h4 className="font-semibold text-secondary mb-1">Data Source Changes</h4>
                  {comparison.data_source_changes.length > 0 ? (
                    <ul className="list-disc pl-5 text-muted">
                      {comparison.data_source_changes.map((c, i) => <li key={i}>{c}</li>)}
                    </ul>
                  ) : <span className="text-muted">Identical data source snapshots.</span>}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Retention Policy Dry-Run Modal */}
        {retentionDryRun && (
          <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
            <div className="bg-surface border border-line rounded-lg max-w-3xl w-full p-6 max-h-[85vh] overflow-y-auto">
              <div className="flex justify-between items-center mb-4 border-b border-line pb-3">
                <h3 className="font-bold text-ink text-sm">Retention Policy Dry-Run Evaluation</h3>
                <button onClick={() => setRetentionDryRun(null)} className="text-muted hover:text-ink">&times;</button>
              </div>

              <div className="grid grid-cols-3 gap-3 text-xs mb-4">
                <div className="bg-canvas p-3 rounded text-center">
                  <span className="text-muted block">Evaluated</span>
                  <span className="text-lg font-bold text-ink">{retentionDryRun.total_evaluated}</span>
                </div>
                <div className="bg-canvas p-3 rounded text-center">
                  <span className="text-muted block">Protected By Holds</span>
                  <span className="text-lg font-bold text-warning">{retentionDryRun.held_count}</span>
                </div>
                <div className="bg-canvas p-3 rounded text-center">
                  <span className="text-muted block">Disposal Eligible</span>
                  <span className="text-lg font-bold text-negative">{retentionDryRun.eligible_for_disposal_count}</span>
                </div>
              </div>

              <div className="space-y-2">
                {retentionDryRun.items.map((it) => (
                  <div key={it.archive_id} className="bg-canvas p-2.5 rounded border border-line flex justify-between text-xs">
                    <div>
                      <span className="font-sans text-brand mr-2">{it.archive_id}</span>
                      <span className="text-muted">({it.report_type}) - Age: {it.age_days} days</span>
                    </div>
                    <span className={`font-semibold ${it.has_legal_hold ? 'text-warning' : it.eligible_for_disposal ? 'text-negative' : 'text-positive'}`}>
                      {it.recommended_action}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
