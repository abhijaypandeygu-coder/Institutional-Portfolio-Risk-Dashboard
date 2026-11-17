import React from "react";
import { ReportRiskMetricsData } from "../../../../types/dailyReport";

interface DailyReportRiskSummaryProps {
  metrics?: ReportRiskMetricsData;
  reportingCurrency: string;
}

export const DailyReportRiskSummary: React.FC<DailyReportRiskSummaryProps> = ({
  metrics,
  reportingCurrency,
}) => {
  if (!metrics) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-2">Quantitative Risk Measures (M07)</h2>
        <p className="text-xs text-slate-500 italic">No quantitative risk records available for this date.</p>
      </div>
    );
  }

  const formatCurrency = (val?: number) => {
    if (val === undefined || val === null) return "UNAVAILABLE";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: reportingCurrency || "USD",
      maximumFractionDigits: 0,
    }).format(val);
  };

  const formatPct = (val?: number) => {
    if (val === undefined || val === null) return "UNAVAILABLE";
    return `${(val * 100).toFixed(2)}%`;
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">
            Authoritative Quantitative Risk Metrics
          </h2>
          <p className="text-xs text-slate-500">
            Certified risk calculations from M07 (Value at Risk, Expected Shortfall, Volatility, Drawdown)
          </p>
        </div>
        <div className="text-right">
          <span className="text-xs font-mono text-slate-400">
            Models:{" "}
            <span className="text-cyan-400">
              {metrics.model_versions ? Object.keys(metrics.model_versions).length : 4} Active
            </span>
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        {/* VaR Card */}
        <div className="bg-slate-950/70 p-3.5 rounded border border-slate-800 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-mono text-slate-400 uppercase">Value at Risk (99%)</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                metrics.var?.status === "FRESH" ? "bg-emerald-950 text-emerald-400" : "bg-slate-800 text-slate-400"
              }`}>
                {metrics.var?.status || "UNAVAILABLE"}
              </span>
            </div>
            <div className="text-xl font-bold font-mono text-slate-100 mt-2">
              {formatCurrency(metrics.var?.value)}
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-slate-800/80 text-[11px] text-slate-500 font-mono">
            {metrics.var?.methodology || "HISTORICAL"} | {metrics.var?.horizon_days || 1}d Horizon
          </div>
        </div>

        {/* Expected Shortfall Card */}
        <div className="bg-slate-950/70 p-3.5 rounded border border-slate-800 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-mono text-slate-400 uppercase">Expected Shortfall (99%)</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                metrics.expected_shortfall?.status === "FRESH" ? "bg-emerald-950 text-emerald-400" : "bg-slate-800 text-slate-400"
              }`}>
                {metrics.expected_shortfall?.status || "UNAVAILABLE"}
              </span>
            </div>
            <div className="text-xl font-bold font-mono text-amber-400 mt-2">
              {formatCurrency(metrics.expected_shortfall?.value)}
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-slate-800/80 text-[11px] text-slate-500 font-mono">
            {metrics.expected_shortfall?.methodology || "HISTORICAL_SIMULATION"} | Tail Mean
          </div>
        </div>

        {/* Volatility Card */}
        <div className="bg-slate-950/70 p-3.5 rounded border border-slate-800 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-mono text-slate-400 uppercase">Annualized Volatility</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                metrics.volatility?.status === "FRESH" ? "bg-emerald-950 text-emerald-400" : "bg-slate-800 text-slate-400"
              }`}>
                {metrics.volatility?.status || "UNAVAILABLE"}
              </span>
            </div>
            <div className="text-xl font-bold font-mono text-slate-100 mt-2">
              {formatPct(metrics.volatility?.value)}
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-slate-800/80 text-[11px] text-slate-500 font-mono">
            Lookback: {metrics.volatility?.lookback_window || 30}d | Factor: {metrics.volatility?.annualization_factor || 252}
          </div>
        </div>

        {/* Drawdown Card */}
        <div className="bg-slate-950/70 p-3.5 rounded border border-slate-800 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-mono text-slate-400 uppercase">Maximum Drawdown</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                metrics.drawdown?.status === "FRESH" ? "bg-emerald-950 text-emerald-400" : "bg-slate-800 text-slate-400"
              }`}>
                {metrics.drawdown?.status || "UNAVAILABLE"}
              </span>
            </div>
            <div className="text-xl font-bold font-mono text-rose-400 mt-2">
              {formatPct(metrics.drawdown?.maximum_drawdown)}
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-slate-800/80 text-[11px] text-slate-500 font-mono">
            Current: {formatPct(metrics.drawdown?.current_drawdown)}
          </div>
        </div>
      </div>
    </div>
  );
};
