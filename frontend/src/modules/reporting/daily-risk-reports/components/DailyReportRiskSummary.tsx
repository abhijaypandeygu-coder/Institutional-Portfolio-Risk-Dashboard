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
      <div className="bg-surface border border-line rounded-lg p-5">
        <h2 className="text-sm font-semibold text-secondary mb-2">Quantitative Risk Measures (M07)</h2>
        <p className="text-xs text-muted italic">No quantitative risk records available for this date.</p>
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
    <div className="bg-surface border border-line rounded-lg p-5 shadow-lg">
      <div className="flex items-center justify-between border-b border-line pb-3 mb-4">
        <div>
          <h2 className="text-sm font-semibold text-secondary">
            Authoritative Quantitative Risk Metrics
          </h2>
          <p className="text-xs text-muted">
            Certified risk calculations from M07 (Value at Risk, Expected Shortfall, Volatility, Drawdown)
          </p>
        </div>
        <div className="text-right">
          <span className="text-xs font-sans text-muted">
            Models:{" "}
            <span className="text-brand">
              {metrics.model_versions ? Object.keys(metrics.model_versions).length : 4} Active
            </span>
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        {/* VaR Card */}
        <div className="bg-canvas/70 p-3.5 rounded border border-line flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-sans text-muted uppercase">Value at Risk (99%)</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-sans ${
                metrics.var?.status === "FRESH" ? "bg-positive-soft text-positive" : "bg-subtle text-muted"
              }`}>
                {metrics.var?.status || "UNAVAILABLE"}
              </span>
            </div>
            <div className="text-xl font-bold font-sans text-ink mt-2">
              {formatCurrency(metrics.var?.value)}
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-line/80 text-[11px] text-muted font-sans">
            {metrics.var?.methodology || "HISTORICAL"} | {metrics.var?.horizon_days || 1}d Horizon
          </div>
        </div>

        {/* Expected Shortfall Card */}
        <div className="bg-canvas/70 p-3.5 rounded border border-line flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-sans text-muted uppercase">Expected Shortfall (99%)</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-sans ${
                metrics.expected_shortfall?.status === "FRESH" ? "bg-positive-soft text-positive" : "bg-subtle text-muted"
              }`}>
                {metrics.expected_shortfall?.status || "UNAVAILABLE"}
              </span>
            </div>
            <div className="text-xl font-bold font-sans text-warning mt-2">
              {formatCurrency(metrics.expected_shortfall?.value)}
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-line/80 text-[11px] text-muted font-sans">
            {metrics.expected_shortfall?.methodology || "HISTORICAL_SIMULATION"} | Tail Mean
          </div>
        </div>

        {/* Volatility Card */}
        <div className="bg-canvas/70 p-3.5 rounded border border-line flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-sans text-muted uppercase">Annualized Volatility</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-sans ${
                metrics.volatility?.status === "FRESH" ? "bg-positive-soft text-positive" : "bg-subtle text-muted"
              }`}>
                {metrics.volatility?.status || "UNAVAILABLE"}
              </span>
            </div>
            <div className="text-xl font-bold font-sans text-ink mt-2">
              {formatPct(metrics.volatility?.value)}
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-line/80 text-[11px] text-muted font-sans">
            Lookback: {metrics.volatility?.lookback_window || 30}d | Factor: {metrics.volatility?.annualization_factor || 252}
          </div>
        </div>

        {/* Drawdown Card */}
        <div className="bg-canvas/70 p-3.5 rounded border border-line flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-sans text-muted uppercase">Maximum Drawdown</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-sans ${
                metrics.drawdown?.status === "FRESH" ? "bg-positive-soft text-positive" : "bg-subtle text-muted"
              }`}>
                {metrics.drawdown?.status || "UNAVAILABLE"}
              </span>
            </div>
            <div className="text-xl font-bold font-sans text-negative mt-2">
              {formatPct(metrics.drawdown?.maximum_drawdown)}
            </div>
          </div>
          <div className="mt-3 pt-2 border-t border-line/80 text-[11px] text-muted font-sans">
            Current: {formatPct(metrics.drawdown?.current_drawdown)}
          </div>
        </div>
      </div>
    </div>
  );
};
