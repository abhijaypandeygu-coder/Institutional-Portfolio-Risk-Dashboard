import React from 'react';
import { CorrelationMatrixViewResponse } from '../../../../types/dashboard';

interface CorrelationMatrixHeatmapProps {
  matrixData: CorrelationMatrixViewResponse;
  onCellClick: (symbolA: string, symbolB: string, assetAId: string, assetBId: string) => void;
  selectedPair: { assetAId: string; assetBId: string } | null;
}

export const CorrelationMatrixHeatmap: React.FC<CorrelationMatrixHeatmapProps> = ({
  matrixData,
  onCellClick,
  selectedPair,
}) => {
  const symbols = matrixData.asset_symbols;
  const assetIds = matrixData.asset_ids;
  const matrix = matrixData.matrix;
  const dim = matrixData.dimension;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-sm overflow-hidden">
      {/* Title & Diagnostic Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-800 text-xs">
        <div>
          <h3 className="text-sm font-semibold text-slate-100 uppercase tracking-wide">
            Pairwise Correlation Matrix ({dim} × {dim})
          </h3>
          <p className="text-[11px] text-slate-400 mt-0.5">
            Method: <strong className="text-slate-200">{matrixData.estimator}</strong> | Lookback:{' '}
            <strong className="text-slate-200">{matrixData.lookback_days} Trading Days</strong> | Freq:{' '}
            <strong className="text-slate-200">{matrixData.frequency}</strong>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-slate-400">
            Avg Corr: <strong className="text-slate-200">{Number(matrixData.average_correlation).toFixed(2)}</strong>
          </span>
          <span className="text-slate-400">
            Median: <strong className="text-slate-200">{Number(matrixData.median_correlation).toFixed(2)}</strong>
          </span>
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
            matrixData.psd_status === 'POSITIVE_SEMIDEFINITE' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-amber-950 text-amber-400 border border-amber-800'
          }`}>
            PSD: {matrixData.psd_status}
          </span>
        </div>
      </div>

      {/* Matrix Table */}
      <div className="overflow-x-auto max-h-[580px] overflow-y-auto">
        <table className="border-collapse text-xs select-none">
          <thead>
            <tr>
              <th className="p-2 sticky left-0 top-0 bg-slate-950 text-slate-400 font-semibold border-b border-r border-slate-800 z-20">
                Asset
              </th>
              {symbols.map((sym, j) => (
                <th
                  key={`col_${j}`}
                  className="p-2 sticky top-0 bg-slate-950 text-slate-300 font-bold border-b border-slate-800 min-w-[56px] text-center z-10"
                >
                  {sym}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {symbols.map((rowSym, i) => (
              <tr key={`row_${i}`}>
                <td className="p-2 sticky left-0 bg-slate-950 text-slate-200 font-bold border-r border-slate-800 z-10 whitespace-nowrap">
                  {rowSym}
                </td>
                {symbols.map((colSym, j) => {
                  const val = matrix[i][j];
                  const isDiagonal = i === j;
                  const isSelected = selectedPair && (
                    (selectedPair.assetAId === assetIds[i] && selectedPair.assetBId === assetIds[j]) ||
                    (selectedPair.assetAId === assetIds[j] && selectedPair.assetBId === assetIds[i])
                  );

                  const hexColor = getCellColor(val);
                  const textColor = getCellTextColor(val);

                  return (
                    <td
                      key={`cell_${i}_${j}`}
                      onClick={() => onCellClick(rowSym, colSym, assetIds[i], assetIds[j])}
                      style={{ backgroundColor: hexColor }}
                      className={`p-2 text-center cursor-pointer transition-all border border-slate-900/60 font-semibold min-w-[56px] ${
                        isSelected ? 'ring-2 ring-blue-400 font-black' : 'hover:opacity-85'
                      }`}
                      title={`${rowSym} vs ${colSym}: ${val !== null && val !== undefined ? Number(val).toFixed(4) : 'N/A'}`}
                    >
                      <span style={{ color: textColor }}>
                        {val !== null && val !== undefined ? Number(val).toFixed(2) : '—'}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Diverging Color Legend Bar */}
      <div className="flex items-center justify-between pt-4 mt-2 border-t border-slate-800 text-xs text-slate-400">
        <span>Click cell to inspect scatter observations & rolling trend</span>
        <div className="flex items-center gap-2">
          <span>-1.0</span>
          <div className="h-3 w-44 rounded overflow-hidden flex shadow-inner">
            <div className="h-full flex-1 bg-red-700" title="-1.0 to -0.5" />
            <div className="h-full flex-1 bg-red-400" title="-0.5 to -0.2" />
            <div className="h-full flex-1 bg-slate-100" title="-0.2 to +0.2" />
            <div className="h-full flex-1 bg-emerald-400" title="+0.2 to +0.5" />
            <div className="h-full flex-1 bg-emerald-700" title="+0.5 to +1.0" />
          </div>
          <span>+1.0</span>
        </div>
      </div>
    </div>
  );
};

function getCellColor(val: number | null | undefined): string {
  if (val === null || val === undefined) return '#1e293b';
  const v = Number(val);
  if (v > 0.8) return '#14532d'; // Deep green
  if (v > 0.5) return '#16a34a'; // Green
  if (v > 0.2) return '#86efac'; // Light green
  if (v >= -0.2) return '#f8fafc'; // Neutral off-white
  if (v >= -0.5) return '#fca5a5'; // Light red
  if (v >= -0.8) return '#dc2626'; // Red
  return '#7f1d1d'; // Deep red
}

function getCellTextColor(val: number | null | undefined): string {
  if (val === null || val === undefined) return '#94a3b8';
  const v = Number(val);
  if (v >= -0.2 && v <= 0.2) return '#0f172a';
  if (v > 0.2 && v <= 0.5) return '#064e3b';
  return '#ffffff';
}
