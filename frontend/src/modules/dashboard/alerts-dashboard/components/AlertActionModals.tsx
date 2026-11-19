import React, { useState } from 'react';
import { AlertTriangle } from 'lucide-react';

interface ActionModalProps {
  isOpen: boolean;
  title: string;
  confirmLabel: string;
  confirmColorClass?: string;
  warningNotice?: string | null;
  requiresRationale?: boolean;
  requiresAssignee?: boolean;
  onClose: () => void;
  onConfirm: (payload: { notes?: string; rationale?: string; assigned_to?: string }) => void;
  loading: boolean;
}

export const AlertActionModal: React.FC<ActionModalProps> = ({
  isOpen,
  title,
  confirmLabel,
  confirmColorClass = 'bg-brand hover:bg-brand-hover',
  warningNotice,
  requiresRationale = false,
  requiresAssignee = false,
  onClose,
  onConfirm,
  loading,
}) => {
  const [notes, setNotes] = useState('');
  const [rationale, setRationale] = useState('');
  const [assignee, setAssignee] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (requiresRationale && !rationale.trim()) return;
    if (requiresAssignee && !assignee.trim()) return;

    onConfirm({
      notes: notes.trim() || undefined,
      rationale: rationale.trim() || undefined,
      assigned_to: assignee.trim() || undefined,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 ">
      <div className="bg-surface border border-line-strong rounded-lg max-w-md w-full p-5 shadow-xl text-ink">
        <h3 className="text-base font-semibold mb-3">{title}</h3>

        {warningNotice && (
          <div className="mb-4 p-3 rounded bg-warning-soft/60 border border-warning/20 text-warning text-xs">
            <div className="font-bold mb-1 flex items-center gap-1.5">
              <AlertTriangle className="size-3.5 text-warning" />
              <span>CAUTION — INDEPENDENT CONTROL BOUNDARY</span>
            </div>
            <div>{warningNotice}</div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          {requiresAssignee && (
            <div>
              <label className="block text-xs font-medium text-muted mb-1">
                Assignee User ID / Name <span className="text-negative">*</span>
              </label>
              <input
                type="text"
                value={assignee}
                onChange={(e) => setAssignee(e.target.value)}
                placeholder="e.g. risk_officer_1"
                required
                className="w-full px-3 py-1.5 bg-canvas border border-line-strong rounded text-xs text-ink focus:outline-none focus:border-indigo-500 font-sans"
              />
            </div>
          )}

          {requiresRationale && (
            <div>
              <label className="block text-xs font-medium text-muted mb-1">
                Mandatory Resolution Rationale <span className="text-negative">*</span>
              </label>
              <textarea
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                placeholder="Provide detailed institutional reason for closing this risk alert..."
                required
                rows={3}
                className="w-full px-3 py-1.5 bg-canvas border border-line-strong rounded text-xs text-ink focus:outline-none focus:border-indigo-500 font-sans"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-muted mb-1">Operational Notes (Optional)</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Audit log / contextual notes..."
              rows={2}
              className="w-full px-3 py-1.5 bg-canvas border border-line-strong rounded text-xs text-ink focus:outline-none focus:border-indigo-500 font-sans"
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-line">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-3 py-1.5 rounded text-xs text-muted hover:text-secondary border border-line-strong hover:bg-subtle transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || (requiresRationale && !rationale.trim()) || (requiresAssignee && !assignee.trim())}
              className={`px-3 py-1.5 rounded text-xs font-semibold text-ink transition ${confirmColorClass} disabled:opacity-50`}
            >
              {loading ? 'Processing...' : confirmLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
