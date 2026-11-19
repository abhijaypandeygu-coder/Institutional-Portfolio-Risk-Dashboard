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
    <div className="bg-surface border border-line rounded-xl p-5 mb-6 text-ink shadow-xl">
      <div className="flex items-center justify-between border-b border-line pb-3 mb-4">
        <div>
          <h3 className="text-sm font-semibold uppercase  text-secondary">
            Column & Field Selection Matrix
          </h3>
          <p className="text-xs text-muted mt-0.5">
            Mandatory columns are automatically preserved to maintain auditability and mathematical integrity.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onSelectAll}
            className="px-2.5 py-1 text-xs bg-subtle hover:bg-hover text-secondary rounded border border-line-strong"
          >
            Select All
          </button>
          <button
            onClick={onDeselectAll}
            className="px-2.5 py-1 text-xs bg-subtle hover:bg-hover text-secondary rounded border border-line-strong"
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
              className={`p-3 rounded-lg border transition-opacity flex items-start gap-3 select-none ${
                isMandatory
                  ? 'bg-canvas/60 border-line-strong/60 cursor-not-allowed opacity-90'
                  : isSelected
                  ? 'bg-positive-soft/20 border-emerald-500/40 cursor-pointer hover:border-emerald-500'
                  : 'bg-canvas/30 border-line cursor-pointer hover:border-line-strong'
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
                  <span className="text-xs font-bold text-ink truncate">{f.display_name}</span>
                  {isMandatory && (
                    <span className="px-1.5 py-0.2 text-[10px] font-semibold bg-amber-500/20 text-warning border border-amber-500/30 rounded">
                      REQUIRED
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-muted font-sans mt-0.5">{f.field_name}</div>
                <div className="flex items-center gap-2 mt-1 text-[10px] text-muted">
                  <span className="bg-subtle px-1.5 py-0.5 rounded">{f.data_type}</span>
                  {f.unit && <span className="text-muted">{f.unit}</span>}
                  <span
                    className={`px-1 rounded ${
                      f.sensitivity_level === 'PUBLIC'
                        ? 'text-positive bg-positive-soft/40'
                        : f.sensitivity_level === 'INTERNAL'
                        ? 'text-sky-400 bg-sky-950/40'
                        : 'text-negative bg-negative-soft/40'
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
