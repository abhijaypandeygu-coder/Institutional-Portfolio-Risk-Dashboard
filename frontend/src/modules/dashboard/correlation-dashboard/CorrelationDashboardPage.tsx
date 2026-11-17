import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  CorrelationUniverseType,
  CorrelationSamplingFrequency,
  CorrelationEstimatorType,
  CorrelationMatrixSortOrder,
  CorrelationMatrixViewResponse,
  MatrixComparisonResponse,
  CorrelationClusteringResponse,
  CorrelationOutliersResponse,
  CorrelationPairDetailResponse,
  CorrelationOutlierItem,
  ClusterSummaryNode,
} from '../../../types/dashboard';
import { CorrelationConfigurationToolbar } from './components/CorrelationConfigurationToolbar';
import { CorrelationMatrixHeatmap } from './components/CorrelationMatrixHeatmap';
import { CorrelationClusterPanel } from './components/CorrelationClusterPanel';
import { CorrelationOutlierPanel } from './components/CorrelationOutlierPanel';
import { CorrelationPairDetailDrawer } from './components/CorrelationPairDetailDrawer';

interface CorrelationDashboardPageProps {
  portfolioId: string;
}

export const CorrelationDashboardPage: React.FC<CorrelationDashboardPageProps> = ({ portfolioId }) => {
  // Configuration State
  const [universeType, setUniverseType] = useState<CorrelationUniverseType>('PORTFOLIO_HOLDINGS');
  const [lookbackDays, setLookbackDays] = useState<number>(60);
  const [frequency, setFrequency] = useState<CorrelationSamplingFrequency>('DAILY');
  const [estimator, setEstimator] = useState<CorrelationEstimatorType>('PEARSON');
  const [sortOrder, setSortOrder] = useState<CorrelationMatrixSortOrder>('ORIGINAL');
  const [isCompareMode, setIsCompareMode] = useState<boolean>(false);

  // Analytics Data State
  const [matrixData, setMatrixData] = useState<CorrelationMatrixViewResponse | null>(null);
  const [comparisonData, setComparisonData] = useState<MatrixComparisonResponse | null>(null);
  const [clusterData, setClusterData] = useState<CorrelationClusteringResponse | null>(null);
  const [outlierData, setOutlierData] = useState<CorrelationOutliersResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Pair Detail Drawer State
  const [selectedPair, setSelectedPair] = useState<{ assetAId: string; assetBId: string } | null>(null);
  const [pairDetail, setPairDetail] = useState<CorrelationPairDetailResponse | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState<boolean>(false);

  // Fetch Matrix, Clusters & Outliers
  const fetchDashboardData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      // 1. Authoritative Matrix
      const matrixRes = await axios.post<CorrelationMatrixViewResponse>(
        '/api/v1/dashboard/correlation/matrix',
        {
          portfolio_id: portfolioId,
          lookback_days: lookbackDays,
          frequency: frequency,
          estimator: estimator,
          sort_order: sortOrder,
        }
      );
      setMatrixData(matrixRes.data);

      // 2. Clusters (Run asynchronously)
      try {
        const clusterRes = await axios.post<CorrelationClusteringResponse>(
          '/api/v1/dashboard/correlation/clusters',
          {
            portfolio_id: portfolioId,
            lookback_days: lookbackDays,
            estimator: estimator,
            target_clusters: 3,
          }
        );
        setClusterData(clusterRes.data);
      } catch (e) {
        console.warn('Clustering not available for current universe:', e);
      }

      // 3. Outlier Scan
      try {
        const outlierRes = await axios.post<CorrelationOutliersResponse>(
          '/api/v1/dashboard/correlation/outliers',
          {
            portfolio_id: portfolioId,
            lookback_days: lookbackDays,
            estimator: estimator,
          }
        );
        setOutlierData(outlierRes.data);
      } catch (e) {
        console.warn('Outliers scan failed:', e);
      }

      // 4. Compare mode if active
      if (isCompareMode) {
        const compRes = await axios.post<MatrixComparisonResponse>(
          '/api/v1/dashboard/correlation/compare',
          {
            portfolio_id: portfolioId,
            current_lookback_days: lookbackDays,
            comparison_lookback_days: Math.max(15, lookbackDays // 2),
            estimator: estimator,
          }
        );
        setComparisonData(compRes.data);
      }
    } catch (err: unknown) {
      console.error('Failed to load correlation dashboard data:', err);
      setError('Unable to load authoritative correlation matrix from backend.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, [portfolioId, universeType, lookbackDays, frequency, estimator, sortOrder, isCompareMode]);

  // Handle Cell Click for Detail Drawer
  const handleCellClick = async (symA: string, symB: string, idA: string, idB: string) => {
    setSelectedPair({ assetAId: idA, assetBId: idB });
    setIsDetailLoading(true);
    try {
      const res = await axios.get<CorrelationPairDetailResponse>(
        `/api/v1/dashboard/correlation/pair/${idA}/${idB}`,
        {
          params: {
            portfolio_id: portfolioId,
            lookback_days: lookbackDays,
            estimator: estimator,
          },
        }
      );
      setPairDetail(res.data);
    } catch (err) {
      console.error('Failed to fetch pair detail:', err);
    } finally {
      setIsDetailLoading(false);
    }
  };

  const handleSelectOutlierPair = (item: CorrelationOutlierItem) => {
    handleCellClick(
      item.instrument_a_symbol,
      item.instrument_b_symbol,
      item.instrument_a_id,
      item.instrument_b_id
    );
  };

  const handleSelectCluster = (cluster: ClusterSummaryNode) => {
    // Optionally focus matrix or filter universe
    console.log('Selected Cluster:', cluster.cluster_name);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100 tracking-tight">
            M13.05 — Correlation Dashboard
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Pairwise return correlations, statistical clusters, lookback comparisons, and relationship outlier inspection.
          </p>
        </div>
        <div className="text-xs text-slate-400">
          Portfolio: <strong className="text-slate-200">{portfolioId}</strong>
        </div>
      </div>

      {/* Toolbar */}
      <CorrelationConfigurationToolbar
        portfolioId={portfolioId}
        universeType={universeType}
        onUniverseTypeChange={setUniverseType}
        lookbackDays={lookbackDays}
        onLookbackDaysChange={setLookbackDays}
        frequency={frequency}
        onFrequencyChange={setFrequency}
        estimator={estimator}
        onEstimatorChange={setEstimator}
        sortOrder={sortOrder}
        onSortOrderChange={setSortOrder}
        isCompareMode={isCompareMode}
        onToggleCompareMode={() => setIsCompareMode(!isCompareMode)}
        onRefresh={fetchDashboardData}
        isLoading={isLoading}
      />

      {/* Main Matrix */}
      {isLoading ? (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-16 flex flex-col items-center justify-center space-y-3">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
          <p className="text-xs text-slate-400">Loading authoritative correlation matrix from M07.05...</p>
        </div>
      ) : error ? (
        <div className="bg-red-950/40 border border-red-800/80 rounded-lg p-6 text-center text-xs text-red-200">
          {error}
        </div>
      ) : matrixData ? (
        <CorrelationMatrixHeatmap
          matrixData={matrixData}
          onCellClick={handleCellClick}
          selectedPair={selectedPair}
        />
      ) : null}

      {/* Hierarchical Clusters Panel */}
      <CorrelationClusterPanel
        clusterData={clusterData}
        isLoading={isLoading}
        onSelectCluster={handleSelectCluster}
      />

      {/* Outliers & Changing Relationships Panel */}
      <CorrelationOutlierPanel
        outliers={outlierData}
        isLoading={isLoading}
        onSelectPair={handleSelectOutlierPair}
      />

      {/* Pair Detail Drawer */}
      <CorrelationPairDetailDrawer
        detail={pairDetail}
        isLoading={isDetailLoading}
        portfolioId={portfolioId}
        onClose={() => {
          setSelectedPair(null);
          setPairDetail(null);
        }}
      />
    </div>
  );
};

export default CorrelationDashboardPage;
