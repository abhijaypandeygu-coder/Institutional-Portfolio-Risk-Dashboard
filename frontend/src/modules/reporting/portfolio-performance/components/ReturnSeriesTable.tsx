import React from "react";
import {
  ReturnObservationSchema,
  BenchmarkObservationSchema,
} from "../../../../types/performanceReport";

interface ReturnSeriesTableProps {
  returns: ReturnObservationSchema[];
  benchmarks: BenchmarkObservationSchema[];
  currency: string;
}

export const ReturnSeriesTable: React.FC<ReturnSeriesTableProps> = ({
  returns,
  benchmarks,
  currency,
}) => {
  const bmkMap = new Map<string, number>();
  benchmarks.forEach((b) => {
    bmkMap.set(b.observation_date, b.periodic_return ?? 0);
  });

  const fmtCurrency = (val: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "USD",
      maximumFractionDigits: 0,
    }).format(val);
  };

  const fmtPct = (val?: number) => {
    if (val === undefined || val === null) return "—";
    return `${(val * 100).toFixed(2)}%`;
  };

  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-lg">
      <div className="border-b border-line pb-3 mb-4">
        <h2 className="text-sm font-semibold text-secondary">
          Subperiod Return Series &amp; Benchmark Alignment
        </h2>
        <p className="text-xs text-muted">
          Time-weighted subperiod returns with isolated external cash flows and daily benchmark comparison
        </p>
      </div>

      <div className="overflow-x-auto max-h-96">
        <table className="w-full text-left text-xs border border-line rounded">
          <thead className="sticky top-0 bg-canvas text-muted font-sans border-b border-line z-10">
            <tr>
              <th className="py-2.5 px-3">Subperiod (Start - End)</th>
              <th className="py-2.5 px-3 text-right">Start NAV</th>
              <th className="py-2.5 px-3 text-right">End NAV</th>
              <th className="py-2.5 px-3 text-right">Net Flow</th>
              <th className="py-2.5 px-3 text-right">Portfolio Ret</th>
              <th className="py-2.5 px-3 text-right">Bmk Ret</th>
              <th className="py-2.5 px-3 text-right">Cum Ret</th>
              <th className="py-2.5 px-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80 font-sans text-[11px]">
            {returns.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-6 text-center text-muted italic">
                  No return observations recorded for this selection.
                </td>
              </tr>
            ) : (
              returns.map((r) => {
                const bmkRet = bmkMap.get(r.observation_end);
                const retColor = (r.periodic_return ?? 0) >= 0 ? "text-positive" : "text-negative";
                const cumColor = (r.cumulative_return ?? 0) >= 0 ? "text-positive" : "text-negative";
                const netFlow = r.external_contributions - r.external_withdrawals;

                return (
                  <tr key={r.id} className="hover:bg-subtle/40 transition-colors">
                    <td className="py-2 px-3 text-secondary">
                      {r.observation_start} → {r.observation_end}
                    </td>
                    <td className="py-2 px-3 text-right text-secondary">
                      {fmtCurrency(r.beginning_value)}
                    </td>
                    <td className="py-2 px-3 text-right text-ink font-semibold">
                      {fmtCurrency(r.ending_value)}
                    </td>
                    <td className="py-2 px-3 text-right text-muted">
                      {netFlow !== 0 ? fmtCurrency(netFlow) : "—"}
                    </td>
                    <td className={`py-2 px-3 text-right font-bold ${retColor}`}>
                      {fmtPct(r.periodic_return)}
                    </td>
                    <td className="py-2 px-3 text-right text-secondary">
                      {fmtPct(bmkRet)}
                    </td>
                    <td className={`py-2 px-3 text-right font-bold ${cumColor}`}>
                      {fmtPct(r.cumulative_return)}
                    </td>
                    <td className="py-2 px-3">
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-subtle text-secondary border border-line-strong">
                        {r.observation_status}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
