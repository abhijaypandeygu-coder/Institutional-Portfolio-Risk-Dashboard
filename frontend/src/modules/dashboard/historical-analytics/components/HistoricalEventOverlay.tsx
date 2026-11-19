import React from 'react';
import { EventOverlayItem } from '../../../../types/dashboard';

interface HistoricalEventOverlayProps {
  events: EventOverlayItem[];
  selectedCategory: string;
  onSelectCategory: (cat: string) => void;
  onSelectEvent?: (event: EventOverlayItem) => void;
}

export const HistoricalEventOverlay: React.FC<HistoricalEventOverlayProps> = ({
  events,
  selectedCategory,
  onSelectCategory,
  onSelectEvent,
}) => {
  const filteredEvents =
    selectedCategory === 'ALL'
      ? events
      : events.filter((e) => e.event_category === selectedCategory);

  const getBadgeColor = (cat: string, sev?: string | null) => {
    if (sev === 'CRITICAL' || sev === 'EMERGENCY') return 'bg-negative-soft text-negative border-negative/20';
    if (cat === 'BREACH') return 'bg-orange-950 text-orange-300 border-orange-800';
    if (cat === 'ALERT') return 'bg-warning-soft text-warning border-warning/20';
    if (cat === 'TRADE') return 'bg-brand-soft text-brand border-brand/20';
    return 'bg-subtle text-secondary border-line-strong';
  };

  return (
    <div className="bg-surface border border-line rounded-lg p-5 shadow-sm text-ink">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4 border-b border-line pb-3">
        <div>
          <h3 className="text-base font-semibold text-ink flex items-center gap-2">
            Material Historical Event Timeline
            <span className="text-xs font-normal px-2 py-0.5 rounded bg-subtle text-secondary">
              {filteredEvents.length} Events
            </span>
          </h3>
          <p className="text-xs text-muted mt-0.5">
            Synchronized events (Alerts, Breaches, Executions) overlaying portfolio timeline
          </p>
        </div>

        {/* Filter categories */}
        <div className="flex bg-subtle border border-line-strong rounded overflow-hidden text-xs">
          {['ALL', 'ALERT', 'BREACH', 'TRADE'].map((cat) => (
            <button
              key={cat}
              onClick={() => onSelectCategory(cat)}
              className={`px-3 py-1 font-medium transition-colors ${
                selectedCategory === cat
                  ? 'bg-brand text-white'
                  : 'text-muted hover:text-secondary'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {filteredEvents.length === 0 ? (
        <div className="py-8 text-center text-muted text-xs">
          No material events recorded for this category in the selected horizon.
        </div>
      ) : (
        <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
          {filteredEvents.map((evt) => (
            <div
              key={evt.event_id}
              onClick={() => onSelectEvent?.(evt)}
              className="p-3 bg-canvas/60 border border-line/80 hover:border-line-strong rounded-md cursor-pointer transition-opacity flex items-start justify-between gap-4"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span
                    className={`text-[10px] uppercase font-bold  px-2 py-0.5 rounded border ${getBadgeColor(
                      evt.event_category,
                      evt.severity
                    )}`}
                  >
                    {evt.event_category}
                  </span>
                  <span className="text-xs font-medium text-secondary">{evt.event_title}</span>
                  {evt.instrument_id && (
                    <span className="text-xs font-sans text-brand px-1.5 py-0.2 bg-brand-soft/50 rounded">
                      {evt.instrument_id}
                    </span>
                  )}
                </div>
                {evt.event_description && (
                  <p className="text-xs text-muted">{evt.event_description}</p>
                )}
                <div className="text-[11px] text-muted font-sans">
                  Source: {evt.source_module} | Record: {evt.source_record_id}
                </div>
              </div>

              <div className="text-right whitespace-nowrap">
                <div className="text-xs font-sans text-secondary">
                  {new Date(evt.occurrence_time).toLocaleString()}
                </div>
                {evt.severity && (
                  <span className="text-[10px] font-semibold text-negative block mt-0.5">
                    {evt.severity}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
