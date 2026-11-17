import React from 'react';
import { CorrelationClusteringResponse, ClusterSummaryNode } from '../../../../types/dashboard';

interface CorrelationClusterPanelProps {
  clusterData: CorrelationClusteringResponse | null;
  isLoading: boolean;
  onSelectCluster: (cluster: ClusterSummaryNode) => void;
}

export const CorrelationClusterPanel: React.FC<CorrelationClusterPanelProps> = ({
  clusterData,
  isLoading,
  onSelectCluster,
}) => {
  if (isLoading) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-8 flex items-center justify-center">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500" />
      </div>
    );
  }

  if (!clusterData || clusterData.clusters.length === 0) {
    return null;
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-800">
        <div>
          <h3 className="text-sm font-semibold text-slate-100 uppercase tracking-wide">
            Hierarchical Correlation Clusters ({clusterData.number_of_clusters} Clusters)
          </h3>
          <p className="text-[11px] text-slate-400 mt-0.5">
            Grouped using distance metric <span className="font-mono text-slate-300">d = √(2·(1 - ρ))</span> with {clusterData.linkage} linkage.
          </p>
        </div>
        <div className="text-xs text-slate-400">
          Total Clustered Assets: <strong className="text-slate-200">{clusterData.total_instruments}</strong>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {clusterData.clusters.map((c) => (
          <div
            key={c.cluster_id}
            onClick={() => onSelectCluster(c)}
            className="bg-slate-800/60 border border-slate-700/70 hover:border-blue-500 rounded-lg p-3.5 cursor-pointer transition-colors shadow-sm"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-slate-200">{c.cluster_name}</span>
              <span className="text-[10px] px-1.5 py-0.5 bg-blue-950 text-blue-300 border border-blue-800 rounded font-semibold">
                {c.member_count} Assets
              </span>
            </div>

            <div className="text-xs text-slate-400 space-y-1 mb-2.5">
              <div className="flex justify-between">
                <span>Avg Correlation:</span>
                <strong className="text-slate-200">{Number(c.average_within_correlation).toFixed(2)}</strong>
              </div>
              <div className="flex justify-between">
                <span>Range [Min, Max]:</span>
                <span className="text-slate-300">[{Number(c.min_within_correlation).toFixed(2)}, {Number(c.max_within_correlation).toFixed(2)}]</span>
              </div>
            </div>

            <div className="flex flex-wrap gap-1 pt-2 border-t border-slate-700/40">
              {c.member_symbols.map((sym) => (
                <span
                  key={sym}
                  className="px-1.5 py-0.5 text-[10px] bg-slate-900 border border-slate-700 text-slate-300 rounded font-medium"
                >
                  {sym}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
