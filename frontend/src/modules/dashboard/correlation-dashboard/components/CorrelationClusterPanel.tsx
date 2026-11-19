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
      <div className="bg-surface border border-line rounded-lg p-8 flex items-center justify-center">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500" />
      </div>
    );
  }

  if (!clusterData || clusterData.clusters.length === 0) {
    return null;
  }

  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-line">
        <div>
          <h3 className="text-sm font-semibold text-ink uppercase ">
            Hierarchical Correlation Clusters ({clusterData.number_of_clusters} Clusters)
          </h3>
          <p className="text-[11px] text-muted mt-0.5">
            Grouped using distance metric <span className="font-sans text-secondary">d = √(2·(1 - ρ))</span> with {clusterData.linkage} linkage.
          </p>
        </div>
        <div className="text-xs text-muted">
          Total Clustered Assets: <strong className="text-secondary">{clusterData.total_instruments}</strong>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {clusterData.clusters.map((c) => (
          <div
            key={c.cluster_id}
            onClick={() => onSelectCluster(c)}
            className="bg-subtle/60 border border-line-strong/70 hover:border-blue-500 rounded-lg p-3.5 cursor-pointer transition-colors shadow-sm"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-secondary">{c.cluster_name}</span>
              <span className="text-[10px] px-1.5 py-0.5 bg-brand-soft text-brand border border-brand/20 rounded font-semibold">
                {c.member_count} Assets
              </span>
            </div>

            <div className="text-xs text-muted space-y-1 mb-2.5">
              <div className="flex justify-between">
                <span>Avg Correlation:</span>
                <strong className="text-secondary">{Number(c.average_within_correlation).toFixed(2)}</strong>
              </div>
              <div className="flex justify-between">
                <span>Range [Min, Max]:</span>
                <span className="text-secondary">[{Number(c.min_within_correlation).toFixed(2)}, {Number(c.max_within_correlation).toFixed(2)}]</span>
              </div>
            </div>

            <div className="flex flex-wrap gap-1 pt-2 border-t border-line-strong/40">
              {c.member_symbols.map((sym) => (
                <span
                  key={sym}
                  className="px-1.5 py-0.5 text-[10px] bg-surface border border-line-strong text-secondary rounded font-medium"
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
