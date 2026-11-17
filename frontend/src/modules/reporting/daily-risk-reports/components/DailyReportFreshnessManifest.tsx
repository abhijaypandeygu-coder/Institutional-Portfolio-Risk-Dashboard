import React from "react";
import { ReportAsOfMetadata } from "../../../../types/dailyReport";

interface DailyReportFreshnessManifestProps {
  metadata?: ReportAsOfMetadata;
}

export const DailyReportFreshnessManifest: React.FC<DailyReportFreshnessManifestProps> = ({
  metadata,
}) => {
  if (!metadata) {
    return null;
  }

  const watermarks = Object.values(metadata.source_watermarks || {});

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">
            As-Of Metadata &amp; Source Freshness Watermarks
          </h2>
          <p className="text-xs text-slate-500">
            Audit trail of upstream module data latencies, timestamps, and pipeline quality certifications
          </p>
        </div>
        <div className="text-right">
          <span className="text-xs font-mono text-slate-400">
            Report Date: <span className="text-cyan-400">{metadata.report_date}</span>
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4 text-xs font-mono">
        <div className="bg-slate-950 p-2.5 rounded border border-slate-800/80">
          <span className="text-slate-500 block">Report Valuation Timestamp</span>
          <span className="text-slate-200 font-semibold mt-0.5 block">
            {metadata.valuation_timestamp ? new Date(metadata.valuation_timestamp).toUTCString() : "PENDING"}
          </span>
        </div>
        <div className="bg-slate-950 p-2.5 rounded border border-slate-800/80">
          <span className="text-slate-500 block">Report Generation Timestamp</span>
          <span className="text-slate-200 font-semibold mt-0.5 block">
            {new Date(metadata.generated_at).toUTCString()}
          </span>
        </div>
        <div className="bg-slate-950 p-2.5 rounded border border-slate-800/80">
          <span className="text-slate-500 block">Pipeline Freshness Classification</span>
          <span className={`font-semibold mt-0.5 block ${
            metadata.overall_freshness === "FRESH" ? "text-emerald-400" : "text-amber-400"
          }`}>
            {metadata.overall_freshness} {metadata.data_stale_flag && "(STALENESS DETECTED)"}
          </span>
        </div>
      </div>

      {metadata.stale_reasons && metadata.stale_reasons.length > 0 && (
        <div className="bg-amber-950/40 border border-amber-900/60 rounded p-3 mb-4 text-xs font-mono text-amber-300">
          <span className="font-bold">Staleness Warnings:</span>
          <ul className="list-disc list-inside mt-1 text-[11px] text-amber-400">
            {metadata.stale_reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {watermarks.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border border-slate-800 rounded">
            <thead>
              <tr className="bg-slate-950/80 text-slate-400 font-mono border-b border-slate-800">
                <th className="py-2 px-3">Upstream Module</th>
                <th className="py-2 px-3">Last Watermark (UTC)</th>
                <th className="py-2 px-3 text-right">Latency</th>
                <th className="py-2 px-3">Quality Status</th>
                <th className="py-2 px-3">Freshness</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80 font-mono text-[11px]">
              {watermarks.map((w, idx) => (
                <tr key={idx} className="hover:bg-slate-800/30">
                  <td className="py-2 px-3 font-semibold text-slate-200">{w.source_module}</td>
                  <td className="py-2 px-3 text-slate-300">
                    {w.last_watermark ? new Date(w.last_watermark).toISOString() : "N/A"}
                  </td>
                  <td className="py-2 px-3 text-right text-slate-400">
                    {w.latency_minutes !== undefined ? `${w.latency_minutes.toFixed(0)}m` : "N/A"}
                  </td>
                  <td className="py-2 px-3 text-slate-400">
                    <span className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700">
                      {w.quality_status || "HIGH"}
                    </span>
                  </td>
                  <td className="py-2 px-3">
                    <span className={`px-1.5 py-0.5 rounded font-bold ${
                      w.status === "FRESH"
                        ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                        : "bg-amber-950 text-amber-400 border border-amber-800"
                    }`}>
                      {w.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
