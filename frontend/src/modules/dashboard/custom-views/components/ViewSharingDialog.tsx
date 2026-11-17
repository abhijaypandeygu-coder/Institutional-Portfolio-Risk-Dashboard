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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-2xl max-w-xl w-full p-6 text-slate-100 space-y-6">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <h2 className="text-base font-bold text-slate-50 flex items-center gap-2">
              Sharing & Access Controls
              <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                {view.view_id}
              </span>
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Control personal privacy or grant group access without modifying financial data
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white p-1 rounded">
            ✕
          </button>
        </div>

        {/* Visibility Setting */}
        <div className="space-y-3 bg-slate-950/60 p-4 rounded-lg border border-slate-800">
          <label className="block text-xs uppercase tracking-wider text-slate-400 font-semibold">
            Workspace Visibility
          </label>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setVisibility('PERSONAL')}
              className={`p-3 rounded border text-left transition-all ${
                visibility === 'PERSONAL'
                  ? 'border-indigo-500 bg-indigo-950/40 text-slate-100'
                  : 'border-slate-800 bg-slate-900/50 text-slate-400 hover:border-slate-700'
              }`}
            >
              <div className="text-xs font-bold text-slate-200">Personal (Private)</div>
              <div className="text-[11px] text-slate-400 mt-0.5">Only you and platform admins can access</div>
            </button>
            <button
              type="button"
              onClick={() => setVisibility('GROUP')}
              className={`p-3 rounded border text-left transition-all ${
                visibility === 'GROUP'
                  ? 'border-indigo-500 bg-indigo-950/40 text-slate-100'
                  : 'border-slate-800 bg-slate-900/50 text-slate-400 hover:border-slate-700'
              }`}
            >
              <div className="text-xs font-bold text-slate-200">Group Shared</div>
              <div className="text-[11px] text-slate-400 mt-0.5">Available to authorized desk/group members</div>
            </button>
          </div>

          {visibility === 'GROUP' && (
            <div className="pt-2">
              <label className="block text-[11px] text-slate-400 font-semibold mb-1">
                Owner Group Identifier
              </label>
              <select
                value={groupId}
                onChange={(e) => setGroupId(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 text-slate-100 text-xs rounded px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-indigo-500"
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
              className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-semibold shadow transition-colors"
            >
              Save Visibility
            </button>
          </div>
        </div>

        {/* Existing Shares */}
        <div className="space-y-3">
          <label className="block text-xs uppercase tracking-wider text-slate-400 font-semibold">
            Active Group & User Shares ({shares.length})
          </label>
          {shares.length === 0 ? (
            <div className="text-xs text-slate-500 p-3 bg-slate-950/40 rounded border border-slate-800 text-center">
              No additional explicit user or group shares granted.
            </div>
          ) : (
            <div className="space-y-2 max-h-40 overflow-y-auto">
              {shares.map((s) => (
                <div
                  key={s.share_id}
                  className="flex items-center justify-between p-2.5 bg-slate-950/60 rounded border border-slate-800 text-xs font-mono"
                >
                  <div>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-semibold mr-2">
                      {s.principal_type}
                    </span>
                    <span className="text-slate-200">{s.principal_id}</span>
                  </div>
                  <span className="text-xs px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800 font-semibold">
                    {s.permission}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Add Share Form */}
        <form onSubmit={handleAddShareSubmit} className="space-y-3 pt-2 border-t border-slate-800">
          <label className="block text-xs uppercase tracking-wider text-slate-400 font-semibold">
            Grant New Permission
          </label>
          <div className="grid grid-cols-3 gap-2">
            <select
              value={newPrincipalType}
              onChange={(e) => setNewPrincipalType(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-slate-100 text-xs rounded px-2.5 py-1.5 focus:outline-none"
            >
              <option value="GROUP">GROUP</option>
              <option value="USER">USER</option>
            </select>
            <input
              type="text"
              placeholder="Principal ID"
              value={newPrincipalId}
              onChange={(e) => setNewPrincipalId(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-slate-100 text-xs rounded px-2.5 py-1.5 focus:outline-none"
            />
            <select
              value={newPermission}
              onChange={(e) => setNewPermission(e.target.value as ViewPermissionLevel)}
              className="bg-slate-800 border border-slate-700 text-slate-100 text-xs rounded px-2.5 py-1.5 focus:outline-none"
            >
              <option value="VIEW">VIEW (Read-only)</option>
              <option value="EDIT">EDIT (Modify View)</option>
              <option value="DUPLICATE">DUPLICATE</option>
              <option value="MANAGE">MANAGE (Admin)</option>
            </select>
          </div>
          <button
            type="submit"
            className="w-full py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs font-semibold transition-colors"
          >
            + Grant Share
          </button>
        </form>
      </div>
    </div>
  );
};
