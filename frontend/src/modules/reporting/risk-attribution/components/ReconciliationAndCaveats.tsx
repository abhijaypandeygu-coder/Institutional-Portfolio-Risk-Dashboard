import React from 'react';
import {
  Scale,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  Info,
  ShieldAlert,
} from 'lucide-react';
import {
  ReconciliationRecord,
  AttributionCaveat,
} from '../../../../types/riskAttribution';

interface ReconciliationAndCaveatsProps {
  reconciliations: ReconciliationRecord[];
  caveats: AttributionCaveat[];
}

export const ReconciliationAndCaveats: React.FC<ReconciliationAndCaveatsProps> = ({
  reconciliations,
  caveats,
}) => {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* 1. Audit Reconciliation Panel */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden flex flex-col">
        <div className="p-5 border-b border-slate-800">
          <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <Scale className="w-4 h-4 text-emerald-400" />
            Audit Reconciliations
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Mathematical verification of granular components against authoritative risk measure
          </p>
        </div>

        <div className="p-5 space-y-4 flex-1">
          {reconciliations.map((rec) => {
            const isExact =
              rec.reconciliation_status === 'EXACT_RECONCILIATION' ||
              rec.reconciliation_status === 'ROUNDING_DIFFERENCE';
            return (
              <div
                key={rec.attribution_level}
                className="bg-slate-950 border border-slate-800/80 rounded-lg p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-200">
                      {rec.attribution_level} LEVEL
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      {rec.risk_measure}
                    </span>
                  </div>
                  <span
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${
                      isExact
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                    }`}
                  >
                    {isExact ? (
                      <CheckCircle2 className="w-3 h-3" />
                    ) : (
                      <AlertTriangle className="w-3 h-3" />
                    )}
                    {rec.reconciliation_status}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-xs font-mono py-2 border-y border-slate-800/60 my-2">
                  <div>
                    <span className="text-[10px] text-slate-500 block font-sans">Authoritative</span>
                    <span className="text-slate-300">{(rec.authoritative_value * 100).toFixed(4)}%</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 block font-sans">Sum of Contribs</span>
                    <span className="text-slate-300">{(rec.contribution_sum * 100).toFixed(4)}%</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 block font-sans">Residual</span>
                    <span className={rec.residual === 0 ? 'text-slate-400' : 'text-amber-400'}>
                      {(rec.residual * 100).toFixed(5)}%
                    </span>
                  </div>
                </div>

                <p className="text-[11px] text-slate-400 leading-relaxed mt-1">
                  {rec.explanation}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* 2. Auditable Caveats & Limitations */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden flex flex-col">
        <div className="p-5 border-b border-slate-800">
          <h2 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-amber-400" />
            Audit Caveats & Data Quality
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Transparent disclosure of assumptions, classifications, and non-additive properties
          </p>
        </div>

        <div className="p-5 space-y-3 flex-1 overflow-y-auto max-h-[460px]">
          {caveats.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-xs">
              No caveats or quality warnings detected for this report run.
            </div>
          ) : (
            caveats.map((cav, idx) => (
              <div
                key={idx}
                className="bg-slate-950 border border-slate-800 rounded-lg p-3.5 flex items-start gap-3"
              >
                <div className="mt-0.5">
                  {cav.severity === 'CRITICAL' ? (
                    <AlertCircle className="w-4 h-4 text-rose-400" />
                  ) : cav.severity === 'WARNING' ? (
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                  ) : (
                    <Info className="w-4 h-4 text-blue-400" />
                  )}
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-slate-200">
                      {cav.caveat_category}
                    </span>
                    <span className="text-[10px] font-mono text-slate-500">
                      {cav.source_reference}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    {cav.explanation}
                  </p>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
