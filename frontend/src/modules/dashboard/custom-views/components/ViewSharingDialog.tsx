import React, { useState } from 'react';
import {
  CustomViewResponse,
  ViewVisibility,
  ViewShareResponse,
  ViewPermissionLevel,
} from '../../../../types/dashboard';

interface ViewSharingDialogProps {
  view: CustomViewResponse;
  shares: ViewShareResponse[];
  onUpdateVisibility: (visibility: ViewVisibility, ownerGroupId?: string) => void;
  onAddShare: (principalType: string, principalId: string, permission: ViewPermissionLevel) => void;
  isOpen: boolean;
  onClose: () => void;
}

export const ViewSharingDialog: React.FC<ViewSharingDialogProps> = ({
  view,
  shares,
  onUpdateVisibility,
  onAddShare,
  isOpen,
  onClose,
}) => {
  const [visibility, setVisibility] = useState<ViewVisibility>(view.visibility);
  const [groupId, setGroupId] = useState<string>(view.owner_group_id || 'GRP_RISK_TEAM');
  const [newPrincipalType, setNewPrincipalType] = useState<string>('GROUP');
  const [newPrincipalId, setNewPrincipalId] = useState<string>('GRP_QUANT_RESEARCH');
  const [newPermission, setNewPermission] = useState<ViewPermissionLevel>('VIEW');

  if (!isOpen) return null;

  const handleSaveVisibility = () => {
    onUpdateVisibility(visibility, visibility === 'GROUP' ? groupId : undefined);
  };

  const handleAddShareSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPrincipalId.trim()) {
      onAddShare(newPrincipalType, newPrincipalId.trim(), newPermission);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70  p-4">
      <div className="bg-surface border border-line rounded-xl shadow-2xl max-w-xl w-full p-6 text-ink space-y-6">
        <div className="flex items-center justify-between border-b border-line pb-3">
          <div>
            <h2 className="text-base font-bold text-ink flex items-center gap-2">
              Sharing & Access Controls
              <span className="text-[10px] px-2 py-0.5 rounded bg-subtle text-secondary font-sans">
                {view.view_id}
              </span>
            </h2>
            <p className="text-xs text-muted mt-0.5">
              Control personal privacy or grant group access without modifying financial data
            </p>
          </div>
          <button onClick={onClose} className="text-muted hover:text-ink p-1 rounded">
            ✕
          </button>
        </div>

        {/* Visibility Setting */}
        <div className="space-y-3 bg-canvas/60 p-4 rounded-lg border border-line">
          <label className="block text-xs uppercase  text-muted font-semibold">
            Workspace Visibility
          </label>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setVisibility('PERSONAL')}
              className={`p-3 rounded border text-left transition-opacity ${
                visibility === 'PERSONAL'
                  ? 'border-indigo-500 bg-brand-soft/40 text-ink'
                  : 'border-line bg-surface/50 text-muted hover:border-line-strong'
              }`}
            >
              <div className="text-xs font-bold text-secondary">Personal (Private)</div>
              <div className="text-[11px] text-muted mt-0.5">Only you and platform admins can access</div>
            </button>
            <button
              type="button"
              onClick={() => setVisibility('GROUP')}
              className={`p-3 rounded border text-left transition-opacity ${
                visibility === 'GROUP'
                  ? 'border-indigo-500 bg-brand-soft/40 text-ink'
                  : 'border-line bg-surface/50 text-muted hover:border-line-strong'
              }`}
            >
              <div className="text-xs font-bold text-secondary">Group Shared</div>
              <div className="text-[11px] text-muted mt-0.5">Available to authorized desk/group members</div>
            </button>
          </div>

          {visibility === 'GROUP' && (
            <div className="pt-2">
              <label className="block text-[11px] text-muted font-semibold mb-1">
                Owner Group Identifier
              </label>
              <select
                value={groupId}
                onChange={(e) => setGroupId(e.target.value)}
                className="w-full bg-subtle border border-line-strong text-ink text-xs rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                <option value="GRP_RISK_TEAM">GRP_RISK_TEAM (Enterprise Risk Management)</option>
                <option value="GRP_PORTFOLIO_MANAGERS">GRP_PORTFOLIO_MANAGERS (Desk Leads)</option>
                <option value="GRP_QUANT_RESEARCH">GRP_QUANT_RESEARCH (Quant Analytics)</option>
              </select>
            </div>
          )}

          <div className="text-right pt-2">
            <button
              onClick={handleSaveVisibility}
              className="px-3 py-1.5 bg-brand hover:bg-brand-hover text-white rounded text-xs font-semibold shadow transition-colors"
            >
              Save Visibility
            </button>
          </div>
        </div>

        {/* Existing Shares */}
        <div className="space-y-3">
          <label className="block text-xs uppercase  text-muted font-semibold">
            Active Group & User Shares ({shares.length})
          </label>
          {shares.length === 0 ? (
            <div className="text-xs text-muted p-3 bg-canvas/40 rounded border border-line text-center">
              No additional explicit user or group shares granted.
            </div>
          ) : (
            <div className="space-y-2 max-h-40 overflow-y-auto">
              {shares.map((s) => (
                <div
                  key={s.share_id}
                  className="flex items-center justify-between p-2.5 bg-canvas/60 rounded border border-line text-xs font-sans"
                >
                  <div>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-subtle text-secondary font-semibold mr-2">
                      {s.principal_type}
                    </span>
                    <span className="text-secondary">{s.principal_id}</span>
                  </div>
                  <span className="text-xs px-2 py-0.5 rounded bg-brand-soft text-brand border border-brand/20 font-semibold">
                    {s.permission}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Add Share Form */}
        <form onSubmit={handleAddShareSubmit} className="space-y-3 pt-2 border-t border-line">
          <label className="block text-xs uppercase  text-muted font-semibold">
            Grant New Permission
          </label>
          <div className="grid grid-cols-3 gap-2">
            <select
              value={newPrincipalType}
              onChange={(e) => setNewPrincipalType(e.target.value)}
              className="bg-subtle border border-line-strong text-ink text-xs rounded px-2.5 py-1.5 focus:outline-none"
            >
              <option value="GROUP">GROUP</option>
              <option value="USER">USER</option>
            </select>
            <input
              type="text"
              placeholder="Principal ID"
              value={newPrincipalId}
              onChange={(e) => setNewPrincipalId(e.target.value)}
              className="bg-subtle border border-line-strong text-ink text-xs rounded px-2.5 py-1.5 focus:outline-none"
            />
            <select
              value={newPermission}
              onChange={(e) => setNewPermission(e.target.value as ViewPermissionLevel)}
              className="bg-subtle border border-line-strong text-ink text-xs rounded px-2.5 py-1.5 focus:outline-none"
            >
              <option value="VIEW">VIEW (Read-only)</option>
              <option value="EDIT">EDIT (Modify View)</option>
              <option value="DUPLICATE">DUPLICATE</option>
              <option value="MANAGE">MANAGE (Admin)</option>
            </select>
          </div>
          <button
            type="submit"
            className="w-full py-1.5 bg-subtle hover:bg-hover text-secondary rounded text-xs font-semibold transition-colors"
          >
            + Grant Share
          </button>
        </form>
      </div>
    </div>
  );
};
