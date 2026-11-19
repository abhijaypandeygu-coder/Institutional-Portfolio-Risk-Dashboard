import React, { useState, useEffect, useCallback } from 'react';
import {
  CustomViewResponse,
  WidgetDefinition,
  WidgetInstanceConfig,
  LayoutConfig,
  ViewVisibility,
  ViewShareResponse,
  ViewPermissionLevel,
} from '../../../types/dashboard';
import { WidgetCatalogue } from './components/WidgetCatalogue';
import { WidgetConfigurationPanel } from './components/WidgetConfigurationPanel';
import { ViewSharingDialog } from './components/ViewSharingDialog';

export const CustomViewsPage: React.FC = () => {
  const [views, setViews] = useState<CustomViewResponse[]>([]);
  const [activeView, setActiveView] = useState<CustomViewResponse | null>(null);
  const [widgets, setWidgets] = useState<WidgetDefinition[]>([]);
  const [selectedInstance, setSelectedInstance] = useState<WidgetInstanceConfig | null>(null);
  const [shares, setShares] = useState<ViewShareResponse[]>([]);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isCatalogueOpen, setIsCatalogueOpen] = useState<boolean>(false);
  const [isSharingOpen, setIsSharingOpen] = useState<boolean>(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);
  const [userId] = useState<string>('DEFAULT_ANALYST');

  // Load registered widgets catalogue
  const loadWidgets = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/dashboard/custom-views/widgets');
      if (res.ok) {
        const data = await res.json();
        setWidgets(data);
      }
    } catch (err) {
      console.error('Failed to load widgets', err);
    }
  }, []);

  // Load custom views list
  const loadViews = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`/api/v1/dashboard/custom-views/views?user_id=${userId}`);
      if (res.ok) {
        const data = await res.json();
        setViews(data.views || []);
        if (data.views && data.views.length > 0 && !activeView) {
          // Select default or first view
          const def = data.views.find((v: CustomViewResponse) => v.is_default) || data.views[0];
          setActiveView(def);
        }
      }
    } catch (err) {
      console.error('Failed to load custom views', err);
    } finally {
      setIsLoading(false);
    }
  }, [userId, activeView]);

  useEffect(() => {
    loadWidgets();
    loadViews();
  }, [loadWidgets, loadViews]);

  // Handle Add Widget from Catalogue
  const handleAddWidget = (widgetId: string) => {
    if (!activeView) return;
    const def = widgets.find((w) => w.widget_id === widgetId);
    if (!def) return;

    const newInstance: WidgetInstanceConfig = {
      instance_id: `inst_${Date.now()}`,
      widget_id: widgetId,
      widget_version: def.version,
      title_override: def.name,
      position: {
        x: 0,
        y: activeView.layout_config.widgets.length * 4,
        width: def.dimension_bounds.default_width,
        height: def.dimension_bounds.default_height,
      },
      is_visible: true,
      visualization_type: def.default_visualization_type,
      settings: def.default_configuration,
    };

    const updatedLayout: LayoutConfig = {
      ...activeView.layout_config,
      widgets: [...activeView.layout_config.widgets, newInstance],
    };

    setActiveView({
      ...activeView,
      layout_config: updatedLayout,
    });
    setHasUnsavedChanges(true);
  };

  // Handle Remove Widget Instance
  const handleRemoveWidget = (instanceId: string) => {
    if (!activeView) return;
    const updatedWidgets = activeView.layout_config.widgets.filter((w) => w.instance_id !== instanceId);
    setActiveView({
      ...activeView,
      layout_config: {
        ...activeView.layout_config,
        widgets: updatedWidgets,
      },
    });
    if (selectedInstance?.instance_id === instanceId) {
      setSelectedInstance(null);
    }
    setHasUnsavedChanges(true);
  };

  // Handle Save Layout Changes
  const handleSaveLayout = async () => {
    if (!activeView) return;
    try {
      const payload = {
        name: activeView.name,
        layout_config: activeView.layout_config,
        expected_version: activeView.version,
      };
      const res = await fetch(`/api/v1/dashboard/custom-views/views/${activeView.view_id}?user_id=${userId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const saved = await res.json();
        setActiveView(saved);
        setHasUnsavedChanges(false);
        loadViews();
      } else if (res.status === 409) {
        alert('Version conflict detected: Another user or session updated this view. Please reload.');
      }
    } catch (err) {
      console.error('Failed to save layout', err);
    }
  };

  // Create New View Preset
  const handleCreateNewView = async (templateType?: string) => {
    try {
      const payload = {
        name: templateType ? `New ${templateType} View` : 'New Custom View',
        visibility: 'PERSONAL',
        template_type: templateType,
      };
      const res = await fetch(`/api/v1/dashboard/custom-views/views?user_id=${userId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const created = await res.json();
        setActiveView(created);
        loadViews();
      }
    } catch (err) {
      console.error('Failed to create view', err);
    }
  };

  return (
    <div className="p-6 bg-canvas min-h-screen text-ink space-y-6">
      {/* Top Header & View Selector */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-4">
        <div>
          <h1 className="text-2xl font-bold  text-ink flex items-center gap-2">
            Custom Views & Layout Workspace
            <span className="text-xs px-2.5 py-1 bg-brand-soft text-brand border border-brand/20 rounded font-semibold">
              M13.10
            </span>
          </h1>
          <p className="text-xs text-muted mt-1">
            Personalize, arrange, and share institutional analytics workspaces across M13 widgets
          </p>
        </div>

        {/* View Switcher Dropdown & Actions */}
        <div className="flex items-center gap-3">
          <select
            value={activeView?.view_id || ''}
            onChange={(e) => {
              const selected = views.find((v) => v.view_id === e.target.value);
              if (selected) {
                setActiveView(selected);
                setSelectedInstance(null);
                setHasUnsavedChanges(false);
              }
            }}
            className="bg-subtle border border-line-strong text-ink text-xs rounded px-3 py-2 font-medium focus:ring-1 focus:ring-indigo-500"
          >
            {views.map((v) => (
              <option key={v.view_id} value={v.view_id}>
                {v.name} {v.visibility === 'GROUP' ? '👥 (Shared)' : '🔒 (Personal)'} (v{v.version})
              </option>
            ))}
          </select>

          {/* New View Button */}
          <div className="relative group">
            <button className="px-3 py-2 bg-subtle hover:bg-hover text-secondary text-xs font-semibold rounded border border-line-strong transition-colors">
              + New View
            </button>
            <div className="hidden group-hover:block absolute right-0 mt-1 w-48 bg-surface border border-line rounded shadow-xl z-20 py-1 text-xs">
              <button
                onClick={() => handleCreateNewView('PORTFOLIO_MONITORING')}
                className="w-full text-left px-3 py-1.5 hover:bg-subtle text-secondary"
              >
                Portfolio Monitoring Template
              </button>
              <button
                onClick={() => handleCreateNewView('RISK_MONITORING')}
                className="w-full text-left px-3 py-1.5 hover:bg-subtle text-secondary"
              >
                Risk Monitoring Template
              </button>
              <button
                onClick={() => handleCreateNewView(undefined)}
                className="w-full text-left px-3 py-1.5 hover:bg-subtle text-secondary border-t border-line mt-1 pt-1"
              >
                Blank Dashboard
              </button>
            </div>
          </div>

          {/* Add Widget Button */}
          <button
            onClick={() => setIsCatalogueOpen(true)}
            className="px-3 py-2 bg-brand hover:bg-brand-hover text-white text-xs font-semibold rounded shadow transition-colors flex items-center gap-1.5"
          >
            + Add Widget
          </button>

          {/* Sharing Button */}
          {activeView && (
            <button
              onClick={() => setIsSharingOpen(true)}
              className="px-3 py-2 bg-subtle hover:bg-hover text-secondary text-xs font-semibold rounded border border-line-strong transition-colors"
            >
              👥 Share
            </button>
          )}

          {/* Save Button */}
          {hasUnsavedChanges && (
            <button
              onClick={handleSaveLayout}
              className="px-4 py-2 bg-brand hover:bg-brand-hover text-white text-xs font-bold rounded shadow transition-colors "
            >
              Save Layout
            </button>
          )}
        </div>
      </div>

      {/* Widget Settings Drawer */}
      {selectedInstance && (
        <WidgetConfigurationPanel
          instance={selectedInstance}
          definition={widgets.find((w) => w.widget_id === selectedInstance.widget_id)}
          onUpdateInstance={(updated) => {
            if (!activeView) return;
            const updatedWidgets = activeView.layout_config.widgets.map((w) =>
              w.instance_id === updated.instance_id ? updated : w
            );
            setActiveView({
              ...activeView,
              layout_config: {
                ...activeView.layout_config,
                widgets: updatedWidgets,
              },
            });
            setSelectedInstance(updated);
            setHasUnsavedChanges(true);
          }}
          onClose={() => setSelectedInstance(null)}
        />
      )}

      {/* Dashboard Canvas Grid (12-column layout) */}
      {!activeView || activeView.layout_config.widgets.length === 0 ? (
        <div className="py-24 text-center border-2 border-dashed border-line rounded-xl">
          <p className="text-sm text-muted mb-3">
            No widgets configured in this view canvas.
          </p>
          <button
            onClick={() => setIsCatalogueOpen(true)}
            className="px-4 py-2 bg-brand text-white text-xs font-semibold rounded shadow hover:bg-brand-hover transition-colors"
          >
            Browse Widget Catalogue
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-12 gap-5">
          {activeView.layout_config.widgets.map((w) => {
            const def = widgets.find((d) => d.widget_id === w.widget_id);
            const colSpan = `col-span-${Math.min(12, Math.max(1, w.position.width))}`;

            return (
              <div
                key={w.instance_id}
                style={{ gridColumn: `span ${w.position.width} / span ${w.position.width}` }}
                className="bg-surface border border-line hover:border-line-strong rounded-lg p-4 shadow-sm flex flex-col justify-between transition-opacity"
              >
                {/* Widget Header */}
                <div className="flex items-center justify-between border-b border-line/80 pb-2 mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-ink">
                      {w.title_override || def?.name || w.widget_id}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-subtle text-muted font-sans">
                      {def?.owning_module}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => setSelectedInstance(w)}
                      className="text-xs p-1 text-muted hover:text-secondary hover:bg-subtle rounded transition-colors"
                      title="Configure Widget"
                    >
                      ⚙️
                    </button>
                    <button
                      onClick={() => handleRemoveWidget(w.instance_id)}
                      className="text-xs p-1 text-muted hover:text-negative hover:bg-subtle rounded transition-colors"
                      title="Remove Widget"
                    >
                      ✕
                    </button>
                  </div>
                </div>

                {/* Widget Content Placeholder / Live Embed */}
                <div className="py-8 text-center text-xs text-muted bg-canvas/40 rounded border border-line/50 flex flex-col items-center justify-center space-y-1">
                  <span className="font-semibold text-secondary">
                    {w.visualization_type?.replace(/_/g, ' ').toUpperCase() || 'STANDARD VIEW'}
                  </span>
                  <span className="text-[11px] text-muted">
                    Authoritative calculation linked to {def?.owning_module}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Widget Catalogue Modal */}
      <WidgetCatalogue
        widgets={widgets}
        onAddWidget={handleAddWidget}
        isOpen={isCatalogueOpen}
        onClose={() => setIsCatalogueOpen(false)}
      />

      {/* Sharing Controls Modal */}
      {activeView && (
        <ViewSharingDialog
          view={activeView}
          shares={shares}
          onUpdateVisibility={async (vis, grpId) => {
            const res = await fetch(
              `/api/v1/dashboard/custom-views/views/${activeView.view_id}?user_id=${userId}`,
              {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ visibility: vis, owner_group_id: grpId }),
              }
            );
            if (res.ok) {
              const updated = await res.json();
              setActiveView(updated);
              setIsSharingOpen(false);
            }
          }}
          onAddShare={async (pType, pId, perm) => {
            const updatedShares = [
              ...shares.map((s) => ({
                principal_type: s.principal_type,
                principal_id: s.principal_id,
                permission: s.permission,
              })),
              { principal_type: pType, principal_id: pId, permission: perm },
            ];
            const res = await fetch(
              `/api/v1/dashboard/custom-views/views/${activeView.view_id}/sharing?user_id=${userId}`,
              {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updatedShares),
              }
            );
            if (res.ok) {
              const newSharesList = await res.json();
              setShares(newSharesList);
            }
          }}
          isOpen={isSharingOpen}
          onClose={() => setIsSharingOpen(false)}
        />
      )}
    </div>
  );
};

export default CustomViewsPage;
