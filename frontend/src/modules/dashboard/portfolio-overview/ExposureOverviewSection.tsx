import React from 'react';
import { ExposureSummaryDetail } from '../../types/dashboard.ts';
import { MetricCard } from '../shared/MetricCard.tsx';

interface ExposureOverviewSectionProps {
  exposure: ExposureSummaryDetail;
  onNavigateDetail?: (target: string) => void;
}

export const ExposureOverviewSection: React.FC<ExposureOverviewSectionProps> = ({
  exposure,
  onNavigateDetail,
}) => {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-sm mb-6">
      <div className="flex items-center justify-between mb-4 border-b border-slate-100 pb-3">
        <div>
          <h3 className="text-base font-semibold text-slate-900">
            Portfolio Market Exposures (M06)
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {exposure.directional_description}
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold px-2.5 py-1 rounded bg-slate-100 text-slate-700 border border-slate-200">
            {exposure.directional_status}
          </span>
          {onNavigateDetail && (
            <button
              onClick={() => onNavigateDetail('exposures')}
              className="text-xs font-medium text-blue-600 hover:text-blue-800"
            >
              Detailed Breakdown &rarr;
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          metric={exposure.gross_exposure}
          secondaryComparison={
            exposure.gross_exposure_pct_nav
              ? `${exposure.gross_exposure_pct_nav.value_display} of NAV`
              : undefined
          }
        />
        <MetricCard
          metric={exposure.net_exposure}
          secondaryComparison={
            exposure.net_exposure_pct_nav
              ? `${exposure.net_exposure_pct_nav.value_display} of NAV`
              : undefined
          }
        />
        <MetricCard metric={exposure.long_exposure} />
        <MetricCard metric={exposure.short_exposure} />
      </div>
    </div>
  );
};
