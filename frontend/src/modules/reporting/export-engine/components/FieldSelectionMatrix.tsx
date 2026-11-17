import React from 'react';
import { DatasetFieldDefinition } from '../../../../types/exportEngine';

interface Props {
  fields: DatasetFieldDefinition[];
  selectedFields: string[];
  onToggleField: (fieldName: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
}

export const FieldSelectionMatrix: React.FC<Props> = ({
  fields,
  selectedFields,
  onToggleField,
  onSelectAll,
  onDeselectAll,
}) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 mb-6 text-slate-100 shadow-xl">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            Column & Field Selection Matrix
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Mandatory columns are automatically preserved to maintain auditability and mathematical integrity.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onSelectAll}
            className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700"
          >
            Select All
          </button>
          <button
            onClick={onDeselectAll}
            className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700"
          >
            Reset to Mandatory
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {fields.map((f) => {
          const isSelected = selectedFields.includes(f.field_name);
          const isMandatory = f.is_required;

          return (
            <div
              key={f.field_name}
              onClick={() => {
                if (!isMandatory) onToggleField(f.field_name);
              }}
              className={`p-3 rounded-lg border transition-all flex items-start gap-3 select-none ${
                isMandatory
                  ? 'bg-slate-950/60 border-slate-700/60 cursor-not-allowed opacity-90'
                  : isSelected
                  ? 'bg-emerald-950/20 border-emerald-500/40 cursor-pointer hover:border-emerald-500'
                  : 'bg-slate-950/30 border-slate-800 cursor-pointer hover:border-slate-700'
              }`}
            >
              <input
                type="checkbox"
                checked={isSelected}
                disabled={isMandatory}
                readOnly
                className="mt-1 accent-emerald-500 rounded"
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-white truncate">{f.display_name}</span>
                  {isMandatory && (
                    <span className="px-1.5 py-0.2 text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded">
                      REQUIRED
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-slate-400 font-mono mt-0.5">{f.field_name}</div>
                <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-400">
                  <span className="bg-slate-800 px-1.5 py-0.5 rounded">{f.data_type}</span>
                  {f.unit && <span className="text-slate-400">{f.unit}</span>}
                  <span
                    className={`px-1 rounded ${
                      f.sensitivity_level === 'PUBLIC'
                        ? 'text-emerald-400 bg-emerald-950/40'
                        : f.sensitivity_level === 'INTERNAL'
                        ? 'text-sky-400 bg-sky-950/40'
                        : 'text-rose-400 bg-rose-950/40'
                    }`}
                  >
                    {f.sensitivity_level}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
