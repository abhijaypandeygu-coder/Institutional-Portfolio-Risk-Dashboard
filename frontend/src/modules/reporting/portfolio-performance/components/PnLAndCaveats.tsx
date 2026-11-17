import React from "react";
import {
  PnLBreakdownSchema,
  PerformanceCaveatSchema,
} from "../../../../types/performanceReport";

interface PnLAndCaveatsProps {
  pnl?: PnLBreakdownSchema;
  caveats: PerformanceCaveatSchema[];
  currency: string;
}

export const PnLAndCaveats: React.FC<PnLAndCaveatsProps> = ({
  pnl,
  caveats,
  currency,
}) => {
  const fmtCurrency = (val?: number) => {
    if (val === undefined || val === null) return "—";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "USD",
      maximumFractionDigits: 0,
    }).format(val);
  };

  const getCaveatSeverityBadge = (sev: string) => {
    switch (sev) {
      case "CRITICAL":
        return <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-rose-950 text-rose-400 border border-rose-800">CRITICAL</span>;
      case "WARNING":
        return <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-amber-950 text-amber-400 border border-amber-800">WARNING</span>;
      default:
        return <span className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-slate-800 text-slate-300 border border-slate-700">INFO</span>;
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
      {/* P&L Components Attribution */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-200">
              P&amp;L Breakdown &amp; Attribution (M05.03)
            </h2>
            <p className="text-xs text-slate-500">
              Authoritative realized vs. unrealized profit &amp; loss classification
            </p>
          </div>
          <span className="text-xs font-mono text-emerald-400">
            {pnl?.reconciliation_status || "RECONCILED"}
          </span>
        </div>

        <div className="space-y-3 font-mono text-xs">
          <div className="flex justify-between items-center p-2.5 rounded bg-slate-950 border border-slate-800">
            <span className="text-slate-400">Total Profit &amp; Loss</span>
            <span className={`font-bold ${(pnl?.total_pnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {fmtCurrency(pnl?.total_pnl)}
            </span>
          </div>

          <div className="flex justify-between items-center p-2.5 rounded bg-slate-950/70 border border-slate-800">
            <span className="text-slate-400">Realized P&amp;L</span>
            <span className={`font-semibold ${(pnl?.realized_pnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {fmtCurrency(pnl?.realized_pnl)}
            </span>
          </div>

          <div className="flex justify-between items-center p-2.5 rounded bg-slate-950/70 border border-slate-800">
            <span className="text-slate-400">Unrealized (Mark-to-Market) P&amp;L</span>
            <span className={`font-semibold ${(pnl?.unrealized_pnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {fmtCurrency(pnl?.unrealized_pnl)}
            </span>
          </div>

          <div className="flex justify-between items-center p-2.5 rounded bg-slate-950/40 border border-slate-800">
            <span className="text-slate-500">Fees &amp; Financing Charges</span>
            <span className="text-slate-300">{fmtCurrency(pnl?.fees)}</span>
          </div>

          <div className="flex justify-between items-center p-2.5 rounded bg-slate-950/40 border border-slate-800">
            <span className="text-slate-500">Dividends &amp; Corporate Distributions</span>
            <span className="text-slate-300">{fmtCurrency(pnl?.dividends)}</span>
          </div>
        </div>
      </div>

      {/* Performance Caveats & Limitations */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg">
        <div className="border-b border-slate-800 pb-3 mb-4">
          <h2 className="text-sm font-semibold text-slate-200">
            Performance Caveats &amp; Data Completeness
          </h2>
          <p className="text-xs text-slate-500">
            Auditable disclosures regarding data gaps, approximations, or holiday calendar misalignments
          </p>
        </div>

        {caveats.length === 0 ? (
          <div className="bg-slate-950/60 border border-emerald-900/40 rounded p-4 text-center">
            <span className="text-xs font-mono text-emerald-400 font-medium">
              ✓ ZERO PERFORMANCE CAVEATS — All valuations and return subperiods certified complete
            </span>
          </div>
        ) : (
          <div className="space-y-2.5 max-h-72 overflow-y-auto">
            {caveats.map((c) => (
              <div key={c.id} className="p-3 rounded bg-slate-950/80 border border-slate-800 text-xs font-mono">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    {getCaveatSeverityBadge(c.severity)}
                    <span className="font-semibold text-slate-200">{c.caveat_category}</span>
                  </div>
                  <span className="text-[10px] text-slate-500">{c.affected_metric}</span>
                </div>
                <p className="text-slate-400 text-[11px] font-sans leading-relaxed">{c.explanation}</p>
                {c.source_references && c.source_references.length > 0 && (
                  <div className="mt-2 text-[10px] text-slate-500 truncate">
                    Sources: {c.source_references.join(", ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
