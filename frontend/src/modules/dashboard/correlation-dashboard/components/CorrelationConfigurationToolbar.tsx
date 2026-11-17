import React from 'react';
import { 
  CorrelationUniverseType, 
  CorrelationSamplingFrequency, 
  CorrelationEstimatorType, 
  CorrelationMatrixSortOrder 
} from '../../../../types/dashboard';

interface CorrelationConfigurationToolbarProps {
  portfolioId: string;
  universeType: CorrelationUniverseType;
  onUniverseTypeChange: (ut: CorrelationUniverseType) => void;
  lookbackDays: number;
  onLookbackDaysChange: (lb: number) => void;
  frequency: CorrelationSamplingFrequency;
  onFrequencyChange: (freq: CorrelationSamplingFrequency) => void;
  estimator: CorrelationEstimatorType;
  onEstimatorChange: (est: CorrelationEstimatorType) => void;
  sortOrder: CorrelationMatrixSortOrder;
  onSortOrderChange: (so: CorrelationMatrixSortOrder) => void;
  isCompareMode: boolean;
  onToggleCompareMode: () => void;
  onRefresh: () => void;
  isLoading: boolean;
}

export const CorrelationConfigurationToolbar: React.FC<CorrelationConfigurationToolbarProps> = ({
  portfolioId,
  universeType,
  onUniverseTypeChange,
  lookbackDays,
  onLookbackDaysChange,
  frequency,
  onFrequencyChange,
  estimator,
  onEstimatorChange,
  sortOrder,
  onSortOrderChange,
  isCompareMode,
  onToggleCompareMode,
  onRefresh,
  isLoading,
}) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 mb-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Left: Universe, Lookback, Frequency */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-400 font-semibold uppercase">Universe:</label>
            <select
              value={universeType}
              onChange={(e) => onUniverseTypeChange(e.target.value as CorrelationUniverseType)}
              className="bg-slate-800 border border-slate-700 text-xs rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 font-medium"
            >
              <option value="PORTFOLIO_HOLDINGS">Portfolio Open Holdings</option>
              <option value="CUSTOM_SECURITIES">Selected Custom Securities</option>
              <option value="SECTOR_GROUP">Sector Group Filter</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-400 font-semibold uppercase">Lookback:</label>
            <select
              value={lookbackDays}
              onChange={(e) => onLookbackDaysChange(Number(e.target.value))}
              className="bg-slate-800 border border-slate-700 text-xs rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 font-medium"
            >
              <option value={15}>15 Trading Days (Short)</option>
              <option value={30}>30 Trading Days (1 Mo)</option>
              <option value={60}>60 Trading Days (Quarter)</option>
              <option value={90}>90 Trading Days</option>
              <option value={180}>180 Trading Days (Half-Year)</option>
              <option value={252}>252 Trading Days (1 Year)</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-400 font-semibold uppercase">Freq:</label>
            <select
              value={frequency}
              onChange={(e) => onFrequencyChange(e.target.value as CorrelationSamplingFrequency)}
              className="bg-slate-800 border border-slate-700 text-xs rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 font-medium"
            >
              <option value="DAILY">Daily Close</option>
              <option value="WEEKLY">Weekly Close</option>
              <option value="HOURLY">Hourly (Intraday)</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-400 font-semibold uppercase">Method:</label>
            <select
              value={estimator}
              onChange={(e) => onEstimatorChange(e.target.value as CorrelationEstimatorType)}
              className="bg-slate-800 border border-slate-700 text-xs rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 font-medium"
            >
              <option value="PEARSON">Pearson (Standard Linear)</option>
              <option value="SPEARMAN">Spearman (Rank Correlation)</option>
              <option value="KENDALL_TAU_B">Kendall Tau-b (Robust)</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-400 font-semibold uppercase">Order:</label>
            <select
              value={sortOrder}
              onChange={(e) => onSortOrderChange(e.target.value as CorrelationMatrixSortOrder)}
              className="bg-slate-800 border border-slate-700 text-xs rounded px-2.5 py-1.5 text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 font-medium"
            >
              <option value="ORIGINAL">Original Universe Order</option>
              <option value="ALPHABETICAL">Alphabetical</option>
              <option value="AVERAGE_CORRELATION">Highest Average Correlation</option>
              <option value="CLUSTER">Cluster Dendrogram Order</option>
            </select>
          </div>
        </div>

        {/* Right: Compare Mode & Refresh Action */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onToggleCompareMode}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg border transition-colors ${
              isCompareMode
                ? 'bg-amber-600 text-white border-amber-500 shadow-sm'
                : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'
            }`}
          >
            {isCompareMode ? 'Exit Period Comparison' : 'Compare Previous Period'}
          </button>

          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading}
            className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <div className="animate-spin rounded-full h-3.5 w-3.5 border-b-2 border-white" />
                <span>Calculating...</span>
              </>
            ) : (
              <span>Refresh Matrix</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
