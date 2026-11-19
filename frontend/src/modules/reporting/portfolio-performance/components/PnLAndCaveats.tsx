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
        return <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-negative-soft text-negative border border-negative/20">CRITICAL</span>;
      case "WARNING":
        return <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-warning-soft text-warning border border-warning/20">WARNING</span>;
      default:
        return <span className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-subtle text-secondary border border-line-strong">INFO</span>;
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
      {/* P&L Components Attribution */}
      <div className="bg-surface border border-line rounded-lg p-5 shadow-lg">
        <div className="flex items-center justify-between border-b border-line pb-3 mb-4">
          <div>
            <h2 className="text-sm font-semibold text-secondary">
              P&amp;L Breakdown &amp; Attribution (M05.03)
            </h2>
            <p className="text-xs text-muted">
              Authoritative realized vs. unrealized profit &amp; loss classification
            </p>
          </div>
          <span className="text-xs font-sans text-positive">
            {pnl?.reconciliation_status || "RECONCILED"}
          </span>
        </div>

        <div className="space-y-3 font-sans text-xs">
          <div className="flex justify-between items-center p-2.5 rounded bg-canvas border border-line">
            <span className="text-muted">Total Profit &amp; Loss</span>
            <span className={`font-bold ${(pnl?.total_pnl ?? 0) >= 0 ? "text-positive" : "text-negative"}`}>
              {fmtCurrency(pnl?.total_pnl)}
            </span>
          </div>

          <div className="flex justify-between items-center p-2.5 rounded bg-canvas/70 border border-line">
            <span className="text-muted">Realized P&amp;L</span>
            <span className={`font-semibold ${(pnl?.realized_pnl ?? 0) >= 0 ? "text-positive" : "text-negative"}`}>
              {fmtCurrency(pnl?.realized_pnl)}
            </span>
          </div>

          <div className="flex justify-between items-center p-2.5 rounded bg-canvas/70 border border-line">
            <span className="text-muted">Unrealized (Mark-to-Market) P&amp;L</span>
            <span className={`font-semibold ${(pnl?.unrealized_pnl ?? 0) >= 0 ? "text-positive" : "text-negative"}`}>
              {fmtCurrency(pnl?.unrealized_pnl)}
            </span>
          </div>

          <div className="flex justify-between items-center p-2.5 rounded bg-canvas/40 border border-line">
            <span className="text-muted">Fees &amp; Financing Charges</span>
            <span className="text-secondary">{fmtCurrency(pnl?.fees)}</span>
          </div>

          <div className="flex justify-between items-center p-2.5 rounded bg-canvas/40 border border-line">
            <span className="text-muted">Dividends &amp; Corporate Distributions</span>
            <span className="text-secondary">{fmtCurrency(pnl?.dividends)}</span>
          </div>
        </div>
      </div>

      {/* Performance Caveats & Limitations */}
      <div className="bg-surface border border-line rounded-lg p-5 shadow-lg">
        <div className="border-b border-line pb-3 mb-4">
          <h2 className="text-sm font-semibold text-secondary">
            Performance Caveats &amp; Data Completeness
          </h2>
          <p className="text-xs text-muted">
            Auditable disclosures regarding data gaps, approximations, or holiday calendar misalignments
          </p>
        </div>

        {caveats.length === 0 ? (
          <div className="bg-canvas/60 border border-positive/20 rounded p-4 text-center">
            <span className="text-xs font-sans text-positive font-medium">
              ✓ ZERO PERFORMANCE CAVEATS — All valuations and return subperiods certified complete
            </span>
          </div>
        ) : (
          <div className="space-y-2.5 max-h-72 overflow-y-auto">
            {caveats.map((c) => (
              <div key={c.id} className="p-3 rounded bg-canvas/80 border border-line text-xs font-sans">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    {getCaveatSeverityBadge(c.severity)}
                    <span className="font-semibold text-secondary">{c.caveat_category}</span>
                  </div>
                  <span className="text-[10px] text-muted">{c.affected_metric}</span>
                </div>
                <p className="text-muted text-[11px] font-sans leading-relaxed">{c.explanation}</p>
                {c.source_references && c.source_references.length > 0 && (
                  <div className="mt-2 text-[10px] text-muted truncate">
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
