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
    <div className="bg-surface border border-line rounded-lg p-5 shadow-lg">
      <div className="flex items-center justify-between border-b border-line pb-3 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-secondary">
            As-Of Metadata &amp; Source Freshness Watermarks
          </h2>
          <p className="text-xs text-muted">
            Audit trail of upstream module data latencies, timestamps, and pipeline quality certifications
          </p>
        </div>
        <div className="text-right">
          <span className="text-xs font-sans text-muted">
            Report Date: <span className="text-brand">{metadata.report_date}</span>
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4 text-xs font-sans">
        <div className="bg-canvas p-2.5 rounded border border-line/80">
          <span className="text-muted block">Report Valuation Timestamp</span>
          <span className="text-secondary font-semibold mt-0.5 block">
            {metadata.valuation_timestamp ? new Date(metadata.valuation_timestamp).toUTCString() : "PENDING"}
          </span>
        </div>
        <div className="bg-canvas p-2.5 rounded border border-line/80">
          <span className="text-muted block">Report Generation Timestamp</span>
          <span className="text-secondary font-semibold mt-0.5 block">
            {new Date(metadata.generated_at).toUTCString()}
          </span>
        </div>
        <div className="bg-canvas p-2.5 rounded border border-line/80">
          <span className="text-muted block">Pipeline Freshness Classification</span>
          <span className={`font-semibold mt-0.5 block ${
            metadata.overall_freshness === "FRESH" ? "text-positive" : "text-warning"
          }`}>
            {metadata.overall_freshness} {metadata.data_stale_flag && "(STALENESS DETECTED)"}
          </span>
        </div>
      </div>

      {metadata.stale_reasons && metadata.stale_reasons.length > 0 && (
        <div className="bg-warning-soft/40 border border-warning/20 rounded p-3 mb-4 text-xs font-sans text-warning">
          <span className="font-bold">Staleness Warnings:</span>
          <ul className="list-disc list-inside mt-1 text-[11px] text-warning">
            {metadata.stale_reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {watermarks.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border border-line rounded">
            <thead>
              <tr className="bg-canvas/80 text-muted font-sans border-b border-line">
                <th className="py-2 px-3">Upstream Module</th>
                <th className="py-2 px-3">Last Watermark (UTC)</th>
                <th className="py-2 px-3 text-right">Latency</th>
                <th className="py-2 px-3">Quality Status</th>
                <th className="py-2 px-3">Freshness</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80 font-sans text-[11px]">
              {watermarks.map((w, idx) => (
                <tr key={idx} className="hover:bg-subtle/30">
                  <td className="py-2 px-3 font-semibold text-secondary">{w.source_module}</td>
                  <td className="py-2 px-3 text-secondary">
                    {w.last_watermark ? new Date(w.last_watermark).toISOString() : "N/A"}
                  </td>
                  <td className="py-2 px-3 text-right text-muted">
                    {w.latency_minutes !== undefined ? `${w.latency_minutes.toFixed(0)}m` : "N/A"}
                  </td>
                  <td className="py-2 px-3 text-muted">
                    <span className="px-1.5 py-0.5 rounded bg-subtle border border-line-strong">
                      {w.quality_status || "HIGH"}
                    </span>
                  </td>
                  <td className="py-2 px-3">
                    <span className={`px-1.5 py-0.5 rounded font-bold ${
                      w.status === "FRESH"
                        ? "bg-positive-soft text-positive border border-positive/20"
                        : "bg-warning-soft text-warning border border-warning/20"
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
