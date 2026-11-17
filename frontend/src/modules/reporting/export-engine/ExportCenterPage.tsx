import React, { useState, useEffect } from 'react';
import {
  DatasetRegistryItem,
  ExportJobSummary,
  ExportFormat,
  ExportCreateRequestPayload,
} from '../../../types/exportEngine';
import { ExportControlBar } from './components/ExportControlBar';
import { FieldSelectionMatrix } from './components/FieldSelectionMatrix';
import { ExportHistoryTable } from './components/ExportHistoryTable';

export const ExportCenterPage: React.FC = () => {
  const [datasets, setDatasets] = useState<DatasetRegistryItem[]>([]);
  const [selectedDatasetCode, setSelectedDatasetCode] = useState<string>('daily_risk_positions');
  const [selectedFormats, setSelectedFormats] = useState<ExportFormat[]>(['CSV', 'XLSX', 'PDF']);
  const [selectedFields, setSelectedFields] = useState<string[]>([]);
  const [portfolioId, setPortfolioId] = useState<string>('port_liq_001');
  const [reportingCurrency, setReportingCurrency] = useState<string>('INR');
  const [jobs, setJobs] = useState<ExportJobSummary[]>([]);
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'configure' | 'history'>('configure');

  useEffect(() => {
    fetchDatasets();
    fetchJobs();
  }, []);

  const fetchDatasets = async () => {
    try {
      const res = await fetch('/api/v1/exports/datasets');
      if (res.ok) {
        const data = await res.json();
        setDatasets(data);
        if (data.length > 0 && !selectedDatasetCode) {
          setSelectedDatasetCode(data[0].dataset_code);
          setSelectedFields(data[0].fields.map((f: any) => f.field_name));
        } else if (data.length > 0) {
          const current = data.find((d: any) => d.dataset_code === selectedDatasetCode) || data[0];
          setSelectedFields(current.fields.map((f: any) => f.field_name));
        }
      }
    } catch (e) {
      console.error('Failed to load registered datasets', e);
    }
  };

  const fetchJobs = async () => {
    try {
      const res = await fetch('/api/v1/exports');
      if (res.ok) {
        const data = await res.json();
        setJobs(data);
      }
    } catch (e) {
      console.error('Failed to load export jobs', e);
    }
  };

  const handleSelectDataset = (code: string) => {
    setSelectedDatasetCode(code);
    const ds = datasets.find((d) => d.dataset_code === code);
    if (ds) {
      setSelectedFields(ds.fields.map((f) => f.field_name));
      // Reset formats to supported
      setSelectedFormats(ds.supported_formats);
    }
  };

  const handleToggleFormat = (fmt: ExportFormat) => {
    if (selectedFormats.includes(fmt)) {
      if (selectedFormats.length > 1) {
        setSelectedFormats(selectedFormats.filter((f) => f !== fmt));
      }
    } else {
      setSelectedFormats([...selectedFormats, fmt]);
    }
  };

  const handleToggleField = (fieldName: string) => {
    if (selectedFields.includes(fieldName)) {
      setSelectedFields(selectedFields.filter((f) => f !== fieldName));
    } else {
      setSelectedFields([...selectedFields, fieldName]);
    }
  };

  const currentDataset = datasets.find((d) => d.dataset_code === selectedDatasetCode);

  const handleSelectAll = () => {
    if (currentDataset) {
      setSelectedFields(currentDataset.fields.map((f) => f.field_name));
    }
  };

  const handleDeselectAll = () => {
    if (currentDataset) {
      const req = currentDataset.fields.filter((f) => f.is_required).map((f) => f.field_name);
      setSelectedFields(req);
    }
  };

  const handleExecuteExport = async () => {
    if (!currentDataset) return;
    setIsExecuting(true);
    try {
      const payload: ExportCreateRequestPayload = {
        source: {
          module: currentDataset.source_module,
          feature: currentDataset.source_feature,
          dataset_id: currentDataset.dataset_code,
        },
        formats: selectedFormats,
        scope: {
          portfolio_id: portfolioId,
        },
        fields: selectedFields,
        options: {
          reporting_currency: reportingCurrency,
          timezone: 'UTC',
          include_methodology: true,
          include_metadata: true,
          include_data_quality: true,
        },
      };

      const res = await fetch('/api/v1/exports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        await fetchJobs();
        setActiveTab('history');
      }
    } catch (e) {
      console.error('Failed to execute export', e);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleDownloadArtifact = (jobId: number, artifactId: number, fileName: string) => {
    window.open(`/api/v1/exports/${jobId}/download/${artifactId}`, '_blank');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <ExportControlBar
        datasets={datasets}
        selectedDatasetCode={selectedDatasetCode}
        onSelectDataset={handleSelectDataset}
        selectedFormats={selectedFormats}
        onToggleFormat={handleToggleFormat}
        portfolioId={portfolioId}
        onPortfolioChange={setPortfolioId}
        reportingCurrency={reportingCurrency}
        onCurrencyChange={setReportingCurrency}
        isExecuting={isExecuting}
        onExecuteExport={handleExecuteExport}
      />

      {/* Tabs */}
      <div className="flex border-b border-slate-800 mb-6 gap-6">
        <button
          onClick={() => setActiveTab('configure')}
          className={`pb-3 text-sm font-semibold transition-colors flex items-center gap-2 ${
            activeTab === 'configure'
              ? 'border-b-2 border-emerald-500 text-emerald-400'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>Dataset & Matrix Configuration</span>
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`pb-3 text-sm font-semibold transition-colors flex items-center gap-2 ${
            activeTab === 'history'
              ? 'border-b-2 border-emerald-500 text-emerald-400'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <span>Export Archive & Artifacts</span>
          <span className="px-1.5 py-0.2 bg-slate-800 rounded-full text-xs text-slate-300">
            {jobs.length}
          </span>
        </button>
      </div>

      {activeTab === 'configure' ? (
        currentDataset && (
          <FieldSelectionMatrix
            fields={currentDataset.fields}
            selectedFields={selectedFields}
            onToggleField={handleToggleField}
            onSelectAll={handleSelectAll}
            onDeselectAll={handleDeselectAll}
          />
        )
      ) : (
        <ExportHistoryTable
          jobs={jobs}
          onRefresh={fetchJobs}
          onDownloadArtifact={handleDownloadArtifact}
        />
      )}
    </div>
  );
};

export default ExportCenterPage;
