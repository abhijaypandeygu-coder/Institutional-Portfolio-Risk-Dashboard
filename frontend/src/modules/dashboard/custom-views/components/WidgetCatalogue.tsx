import React from 'react';
import { WidgetDefinition } from '../../../../types/dashboard';

interface WidgetCatalogueProps {
  widgets: WidgetDefinition[];
  onAddWidget: (widgetId: string) => void;
  isOpen: boolean;
  onClose: () => void;
}

export const WidgetCatalogue: React.FC<WidgetCatalogueProps> = ({
  widgets,
  onAddWidget,
  isOpen,
  onClose,
}) => {
  if (!isOpen) return null;

  const categories = Array.from(new Set(widgets.map((w) => w.category)));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70  p-4">
      <div className="bg-surface border border-line rounded-xl shadow-2xl max-w-4xl w-full max-h-[85vh] flex flex-col overflow-hidden text-ink">
        {/* Header */}
        <div className="px-6 py-4 border-b border-line flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-ink flex items-center gap-2">
              Widget Catalogue
              <span className="text-xs px-2 py-0.5 rounded bg-brand-soft text-brand border border-brand/20 font-semibold">
                M13.01–M13.09
              </span>
            </h2>
            <p className="text-xs text-muted mt-0.5">
              Select verified analytical widgets to add to your personalized layout
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-muted hover:text-ink p-1 rounded-md hover:bg-subtle transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6">
          {categories.map((category) => (
            <div key={category} className="space-y-3">
              <h3 className="text-xs uppercase font-bold  text-muted border-b border-line/80 pb-1">
                {category}
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {widgets
                  .filter((w) => w.category === category)
                  .map((widget) => (
                    <div
                      key={widget.widget_id}
                      className="p-4 bg-canvas/70 border border-line hover:border-brand/20 rounded-lg flex flex-col justify-between transition-opacity group"
                    >
                      <div>
                        <div className="flex items-center justify-between mb-1.5">
                          <h4 className="text-sm font-semibold text-ink group-hover:text-brand transition-colors">
                            {widget.name}
                          </h4>
                          <span className="text-[10px] font-sans px-1.5 py-0.5 rounded bg-subtle text-secondary">
                            {widget.owning_module}
                          </span>
                        </div>
                        <p className="text-xs text-muted leading-relaxed mb-3">
                          {widget.description}
                        </p>
                        <div className="flex flex-wrap gap-1 mb-3">
                          {widget.supported_metrics.slice(0, 4).map((m) => (
                            <span
                              key={m}
                              className="text-[10px] px-1.5 py-0.5 rounded bg-surface border border-line text-muted font-sans"
                            >
                              {m}
                            </span>
                          ))}
                          {widget.supported_metrics.length > 4 && (
                            <span className="text-[10px] px-1 py-0.5 text-muted">
                              +{widget.supported_metrics.length - 4} more
                            </span>
                          )}
                        </div>
                      </div>

                      <button
                        onClick={() => {
                          onAddWidget(widget.widget_id);
                          onClose();
                        }}
                        className="w-full py-1.5 px-3 bg-brand/90 hover:bg-brand-hover text-white rounded text-xs font-semibold shadow transition-colors flex items-center justify-center gap-1.5"
                      >
                        + Add Widget
                      </button>
                    </div>
                  ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
