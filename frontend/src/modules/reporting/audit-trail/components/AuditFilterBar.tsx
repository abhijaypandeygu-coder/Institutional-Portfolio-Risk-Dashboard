import React from 'react';
import { EventCategory, EventOutcome, EventSeverity } from '../../../../types/auditTrail';

interface Props {
  selectedCategory: string;
  onSelectCategory: (cat: string) => void;
  selectedModule: string;
  onSelectModule: (mod: string) => void;
  searchCorrelation: string;
  onCorrelationChange: (corr: string) => void;
  onVerifyIntegrity: () => void;
  isVerifying: boolean;
  onRefresh: () => void;
}

export const AuditFilterBar: React.FC<Props> = ({
  selectedCategory,
  onSelectCategory,
  selectedModule,
  onSelectModule,
  searchCorrelation,
  onCorrelationChange,
  onVerifyIntegrity,
  isVerifying,
  onRefresh,
}) => {
  return (
    <div className="bg-surface border border-line rounded-xl p-5 mb-6 text-ink shadow-xl">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-4 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded text-xs font-semibold bg-brand/20 text-positive border border-emerald-500/30">
              M14.07 AUDIT TRAIL
            </span>
            <span className="text-xs text-muted">Cryptographically Chained Immutability</span>
          </div>
          <h2 className="text-xl font-bold  text-ink mt-1">
            Governance & Operational Audit Trail
          </h2>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onVerifyIntegrity}
            disabled={isVerifying}
            className={`px-4 py-2 rounded-lg text-xs font-bold  transition-opacity border flex items-center gap-2 ${
              isVerifying
                ? 'bg-subtle text-muted border-line-strong cursor-not-allowed'
                : 'bg-brand/20 text-positive border-emerald-500/40 hover:bg-brand-hover/30'
            }`}
          >
            {isVerifying ? (
              <>
                <svg className="animate-spin h-3.5 w-3.5 text-positive" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <span>Verifying SHA-256 Chain...</span>
              </>
            ) : (
              <>
                <span className="w-2 h-2 rounded-full bg-emerald-400 " />
                <span>Verify Chain Integrity</span>
              </>
            )}
          </button>

          <button
            onClick={onRefresh}
            className="px-3 py-2 bg-subtle hover:bg-hover text-secondary border border-line-strong rounded-lg text-xs font-medium"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Category */}
        <div>
          <label className="block text-xs font-medium text-muted mb-1.5 uppercase ">
            Event Category
          </label>
          <select
            value={selectedCategory}
            onChange={(e) => onSelectCategory(e.target.value)}
            className="w-full bg-canvas border border-line-strong rounded-lg px-3 py-2 text-xs text-secondary focus:outline-none focus:border-emerald-500"
          >
            <option value="">All Categories</option>
            <option value="USER_ACTION">USER_ACTION</option>
            <option value="CONFIGURATION_CHANGE">CONFIGURATION_CHANGE</option>
            <option value="CONTROL_DECISION">CONTROL_DECISION</option>
            <option value="APPROVAL">APPROVAL</option>
            <option value="SYSTEM_EVENT">SYSTEM_EVENT</option>
            <option value="INTEGRITY_EVENT">INTEGRITY_EVENT</option>
          </select>
        </div>

        {/* Module */}
        <div>
          <label className="block text-xs font-medium text-muted mb-1.5 uppercase ">
            Source Module
          </label>
          <select
            value={selectedModule}
            onChange={(e) => onSelectModule(e.target.value)}
            className="w-full bg-canvas border border-line-strong rounded-lg px-3 py-2 text-xs text-secondary focus:outline-none focus:border-emerald-500"
          >
            <option value="">All Modules (M01–M14)</option>
            <option value="M01">M01: Feed Registry</option>
            <option value="M05">M05: Portfolio Management</option>
            <option value="M07">M07: Quantitative Market Risk</option>
            <option value="M10">M10: Scenario Analysis</option>
            <option value="M11">M11: Risk Limits</option>
            <option value="M12">M12: Risk Alerts</option>
            <option value="M14">M14: Reporting & Export</option>
          </select>
        </div>

        {/* Correlation ID */}
        <div>
          <label className="block text-xs font-medium text-muted mb-1.5 uppercase ">
            Correlation ID Search
          </label>
          <input
            type="text"
            value={searchCorrelation}
            onChange={(e) => onCorrelationChange(e.target.value)}
            placeholder="e.g. WF-202611-001"
            className="w-full bg-canvas border border-line-strong rounded-lg px-3 py-2 text-xs text-secondary focus:outline-none focus:border-emerald-500 font-sans"
          />
        </div>
      </div>
    </div>
  );
};
