import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  HeatmapMetricRegistryResponse, 
  SectorHeatmapResponse, 
  SecurityHeatmapResponse, 
  HeatmapDrilldownResponse,
  HeatmapCell,
  HeatmapPositionSide,
  HeatmapGrouping
} from '../../../types/dashboard';
import { ColorScaleControls } from './components/ColorScaleControls';
import { SectorHeatmapView } from './components/SectorHeatmapView';
import { SecurityHeatmapView } from './components/SecurityHeatmapView';
import { HeatmapDetailDrawer } from './components/HeatmapDetailDrawer';

interface RiskHeatmapsPageProps {
  portfolioId: string;
}

export const RiskHeatmapsPage: React.FC<RiskHeatmapsPageProps> = ({ portfolioId }) => {
  const [registry, setRegistry] = useState<HeatmapMetricRegistryResponse | null>(null);
  const [selectedColorMetric, setSelectedColorMetric] = useState<string>('unrealized_pnl');
  const [selectedAreaMetric, setSelectedAreaMetric] = useState<string>('gross_market_value');
  const [viewMode, setViewMode] = useState<'SECTOR' | 'SECURITY'>('SECTOR');
  const [sideFilter, setSideFilter] = useState<HeatmapPositionSide>('ALL');
  const [grouping, setGrouping] = useState<HeatmapGrouping>('SECTOR');

  // Heatmap Data State
  const [sectorData, setSectorData] = useState<SectorHeatmapResponse | null>(null);
  const [securityData, setSecurityData] = useState<SecurityHeatmapResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Drill-through Drawer State
  const [selectedCell, setSelectedCell] = useState<HeatmapCell | null>(null);
  const [drilldownData, setDrilldownData] = useState<HeatmapDrilldownResponse | null>(null);
  const [isDrilldownLoading, setIsDrilldownLoading] = useState<boolean>(false);

  // 1. Fetch Metric Registry once
  useEffect(() => {
    const fetchRegistry = async () => {
      try {
        const res = await axios.get<HeatmapMetricRegistryResponse>(
          '/api/v1/dashboard/portfolios/risk-heatmaps/metrics'
        );
        setRegistry(res.data);
      } catch (err: unknown) {
        console.error('Failed to load metric registry:', err);
      }
    };
    fetchRegistry();
  }, []);

  // 2. Fetch Heatmap Data on Parameter Changes
  useEffect(() => {
    const fetchHeatmapData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        if (viewMode === 'SECTOR') {
          const res = await axios.get<SectorHeatmapResponse>(
            `/api/v1/dashboard/portfolios/${portfolioId}/risk-heatmaps/sectors`,
            {
              params: {
                color_metric: selectedColorMetric,
                area_metric: selectedAreaMetric,
              },
            }
          );
          setSectorData(res.data);
        } else {
          const res = await axios.get<SecurityHeatmapResponse>(
            `/api/v1/dashboard/portfolios/${portfolioId}/risk-heatmaps/securities`,
            {
              params: {
                color_metric: selectedColorMetric,
                area_metric: selectedAreaMetric,
                side_filter: sideFilter,
                grouping: grouping,
              },
            }
          );
          setSecurityData(res.data);
        }
      } catch (err: unknown) {
        console.error('Failed to load heatmap data:', err);
        setError('Unable to load authoritative heatmap data from backend.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchHeatmapData();
  }, [portfolioId, viewMode, selectedColorMetric, selectedAreaMetric, sideFilter, grouping]);

  // 3. Handle Cell Click Drilldown
  const handleCellClick = async (cell: HeatmapCell) => {
    setSelectedCell(cell);
    setIsDrilldownLoading(true);
    try {
      const entityType = viewMode === 'SECTOR' ? 'SECTOR' : 'SECURITY';
      const res = await axios.get<HeatmapDrilldownResponse>(
        `/api/v1/dashboard/portfolios/${portfolioId}/risk-heatmaps/drilldown`,
        {
          params: {
            entity_id: cell.entity_id,
            entity_type: entityType,
            color_metric: selectedColorMetric,
            area_metric: selectedAreaMetric,
          },
        }
      );
      setDrilldownData(res.data);
    } catch (err: unknown) {
      console.error('Failed to fetch drill-through details:', err);
    } finally {
      setIsDrilldownLoading(false);
    }
  };

  const handleCloseDrawer = () => {
    setSelectedCell(null);
    setDrilldownData(null);
  };

  const activeScaleConfig = viewMode === 'SECTOR' ? sectorData?.color_scale : securityData?.color_scale;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Page Title */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-ink ">
            M13.04 — Portfolio Risk Heatmaps
          </h1>
          <p className="text-xs text-muted mt-1">
            Visual representations of risk, performance clusters, and exposure concentrations across sectors and securities.
          </p>
        </div>
        <div className="text-xs text-muted">
          Portfolio: <strong className="text-secondary">{portfolioId}</strong>
        </div>
      </div>

      {/* Control Toolbar */}
      {registry && (
        <ColorScaleControls
          metrics={registry.metrics}
          selectedColorMetric={selectedColorMetric}
          onSelectColorMetric={setSelectedColorMetric}
          selectedAreaMetric={selectedAreaMetric}
          onSelectAreaMetric={setSelectedAreaMetric}
          scaleConfig={activeScaleConfig}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          sideFilter={sideFilter}
          onSideFilterChange={setSideFilter}
          grouping={grouping}
          onGroupingChange={setGrouping}
        />
      )}

      {/* Main Heatmap Content */}
      {isLoading ? (
        <div className="bg-surface border border-line rounded-lg p-16 flex flex-col items-center justify-center space-y-3">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
          <p className="text-xs text-muted">Loading risk heatmap calculations...</p>
        </div>
      ) : error ? (
        <div className="bg-negative-soft/40 border border-negative/20 rounded-lg p-6 text-center text-xs text-negative">
          {error}
        </div>
      ) : viewMode === 'SECTOR' && sectorData ? (
        <SectorHeatmapView
          data={sectorData}
          onCellClick={handleCellClick}
          selectedEntityId={selectedCell?.entity_id}
        />
      ) : viewMode === 'SECURITY' && securityData ? (
        <SecurityHeatmapView
          data={securityData}
          onCellClick={handleCellClick}
          selectedEntityId={selectedCell?.entity_id}
        />
      ) : null}

      {/* Drill-through Drawer */}
      <HeatmapDetailDrawer
        drilldown={drilldownData}
        isLoading={isDrilldownLoading}
        onClose={handleCloseDrawer}
      />
    </div>
  );
};

export default RiskHeatmapsPage;
