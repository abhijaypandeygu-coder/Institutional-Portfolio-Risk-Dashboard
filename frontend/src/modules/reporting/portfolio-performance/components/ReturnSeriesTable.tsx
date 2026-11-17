import React from "react";
import {
  ReturnObservationSchema,
  BenchmarkObservationSchema,
} from "../../../types/performanceReport";

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
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg">
      <div className="border-b border-slate-800 pb-3 mb-4">
        <h2 className="text-sm font-semibold text-slate-200">
          Subperiod Return Series &amp; Benchmark Alignment
        </h2>
        <p className="text-xs text-slate-500">
          Time-weighted subperiod returns with isolated external cash flows and daily benchmark comparison
        </p>
      </div>

      <div className="overflow-x-auto max-h-96">
        <table className="w-full text-left text-xs border border-slate-800 rounded">
          <thead className="sticky top-0 bg-slate-950 text-slate-400 font-mono border-b border-slate-800 z-10">
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
          <tbody className="divide-y divide-slate-800/80 font-mono text-[11px]">
            {returns.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-6 text-center text-slate-500 italic">
                  No return observations recorded for this selection.
                </td>
              </tr>
            ) : (
              returns.map((r) => {
                const bmkRet = bmkMap.get(r.observation_end);
                const retColor = (r.periodic_return ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400";
                const cumColor = (r.cumulative_return ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400";
                const netFlow = r.external_contributions - r.external_withdrawals;

                return (
                  <tr key={r.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-2 px-3 text-slate-200">
                      {r.observation_start} → {r.observation_end}
                    </td>
                    <td className="py-2 px-3 text-right text-slate-300">
                      {fmtCurrency(r.beginning_value)}
                    </td>
                    <td className="py-2 px-3 text-right text-slate-100 font-semibold">
                      {fmtCurrency(r.ending_value)}
                    </td>
                    <td className="py-2 px-3 text-right text-slate-400">
                      {netFlow !== 0 ? fmtCurrency(netFlow) : "—"}
                    </td>
                    <td className={`py-2 px-3 text-right font-bold ${retColor}`}>
                      {fmtPct(r.periodic_return)}
                    </td>
                    <td className="py-2 px-3 text-right text-slate-300">
                      {fmtPct(bmkRet)}
                    </td>
                    <td className={`py-2 px-3 text-right font-bold ${cumColor}`}>
                      {fmtPct(r.cumulative_return)}
                    </td>
                    <td className="py-2 px-3">
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 border border-slate-700">
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
