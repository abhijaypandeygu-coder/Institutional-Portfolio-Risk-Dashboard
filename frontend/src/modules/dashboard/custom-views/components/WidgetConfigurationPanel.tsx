import React from 'react';
import {
  WidgetInstanceConfig,
  WidgetDefinition,
} from '../../../../types/dashboard';

interface WidgetConfigurationPanelProps {
  instance: WidgetInstanceConfig;
  definition?: WidgetDefinition;
  onUpdateInstance: (updated: WidgetInstanceConfig) => void;
  onClose: () => void;
}

export const WidgetConfigurationPanel: React.FC<WidgetConfigurationPanelProps> = ({
  instance,
  definition,
  onUpdateInstance,
  onClose,
}) => {
  if (!definition) return null;

  const handleTitleChange = (newTitle: string) => {
    onUpdateInstance({
      ...instance,
      title_override: newTitle || undefined,
    });
  };

  const handleVisualizationChange = (viz: string) => {
    onUpdateInstance({
      ...instance,
      visualization_type: viz,
    });
  };

  const handleWidthChange = (w: number) => {
    onUpdateInstance({
      ...instance,
      position: {
        ...instance.position,
        width: w,
      },
    });
  };

  const handleHeightChange = (h: number) => {
    onUpdateInstance({
      ...instance,
      position: {
        ...instance.position,
        height: h,
      },
    });
  };

  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-lg text-ink mb-6">
      <div className="flex items-center justify-between border-b border-line pb-3 mb-4">
        <div>
          <h3 className="text-sm font-bold text-ink flex items-center gap-2">
            Widget Settings: {instance.title_override || definition.name}
            <span className="text-[10px] font-sans px-2 py-0.5 rounded bg-subtle text-muted">
              {instance.instance_id}
            </span>
          </h3>
          <p className="text-xs text-muted mt-0.5">
            Configure display dimensions, visualization formats, and presentation options
          </p>
        </div>
        <button
          onClick={onClose}
          className="text-xs px-2.5 py-1 bg-subtle hover:bg-hover text-secondary rounded transition-colors"
        >
          Close Settings
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Title Override */}
        <div>
          <label className="block text-xs uppercase  text-muted font-semibold mb-1.5">
            Card Title Override
          </label>
          <input
            type="text"
            placeholder={definition.name}
            value={instance.title_override || ''}
            onChange={(e) => handleTitleChange(e.target.value)}
            className="w-full bg-subtle border border-line-strong text-ink text-xs rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        {/* Visualization Type */}
        <div>
          <label className="block text-xs uppercase  text-muted font-semibold mb-1.5">
            Visualization Format
          </label>
          <select
            value={instance.visualization_type || definition.default_visualization_type}
            onChange={(e) => handleVisualizationChange(e.target.value)}
            className="w-full bg-subtle border border-line-strong text-ink text-xs rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            {definition.supported_visualization_types.map((v) => (
              <option key={v} value={v}>
                {v.replace(/_/g, ' ').toUpperCase()}
              </option>
            ))}
          </select>
        </div>

        {/* Dimensions */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs uppercase  text-muted font-semibold mb-1.5">
              Columns ({instance.position.width}/12)
            </label>
            <input
              type="number"
              min={definition.dimension_bounds.min_width}
              max={definition.dimension_bounds.max_width}
              value={instance.position.width}
              onChange={(e) => handleWidthChange(parseInt(e.target.value) || 6)}
              className="w-full bg-subtle border border-line-strong text-ink text-xs rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs uppercase  text-muted font-semibold mb-1.5">
              Height (Rows)
            </label>
            <input
              type="number"
              min={definition.dimension_bounds.min_height}
              max={definition.dimension_bounds.max_height}
              value={instance.position.height}
              onChange={(e) => handleHeightChange(parseInt(e.target.value) || 4)}
              className="w-full bg-subtle border border-line-strong text-ink text-xs rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
        </div>
      </div>
    </div>
  );
};
