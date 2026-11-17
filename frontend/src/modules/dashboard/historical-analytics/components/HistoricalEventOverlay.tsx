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
    if (sev === 'CRITICAL' || sev === 'EMERGENCY') return 'bg-rose-950 text-rose-300 border-rose-800';
    if (cat === 'BREACH') return 'bg-orange-950 text-orange-300 border-orange-800';
    if (cat === 'ALERT') return 'bg-amber-950 text-amber-300 border-amber-800';
    if (cat === 'TRADE') return 'bg-blue-950 text-blue-300 border-blue-800';
    return 'bg-slate-800 text-slate-300 border-slate-700';
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 shadow-sm text-slate-100">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4 border-b border-slate-800 pb-3">
        <div>
          <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            Material Historical Event Timeline
            <span className="text-xs font-normal px-2 py-0.5 rounded bg-slate-800 text-slate-300">
              {filteredEvents.length} Events
            </span>
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Synchronized events (Alerts, Breaches, Executions) overlaying portfolio timeline
          </p>
        </div>

        {/* Filter categories */}
        <div className="flex bg-slate-800 border border-slate-700 rounded overflow-hidden text-xs">
          {['ALL', 'ALERT', 'BREACH', 'TRADE'].map((cat) => (
            <button
              key={cat}
              onClick={() => onSelectCategory(cat)}
              className={`px-3 py-1 font-medium transition-colors ${
                selectedCategory === cat
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {filteredEvents.length === 0 ? (
        <div className="py-8 text-center text-slate-400 text-xs">
          No material events recorded for this category in the selected horizon.
        </div>
      ) : (
        <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
          {filteredEvents.map((evt) => (
            <div
              key={evt.event_id}
              onClick={() => onSelectEvent?.(evt)}
              className="p-3 bg-slate-950/60 border border-slate-800/80 hover:border-slate-700 rounded-md cursor-pointer transition-all flex items-start justify-between gap-4"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span
                    className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded border ${getBadgeColor(
                      evt.event_category,
                      evt.severity
                    )}`}
                  >
                    {evt.event_category}
                  </span>
                  <span className="text-xs font-medium text-slate-200">{evt.event_title}</span>
                  {evt.instrument_id && (
                    <span className="text-xs font-mono text-indigo-400 px-1.5 py-0.2 bg-indigo-950/50 rounded">
                      {evt.instrument_id}
                    </span>
                  )}
                </div>
                {evt.event_description && (
                  <p className="text-xs text-slate-400">{evt.event_description}</p>
                )}
                <div className="text-[11px] text-slate-500 font-mono">
                  Source: {evt.source_module} | Record: {evt.source_record_id}
                </div>
              </div>

              <div className="text-right whitespace-nowrap">
                <div className="text-xs font-mono text-slate-300">
                  {new Date(evt.occurrence_time).toLocaleString()}
                </div>
                {evt.severity && (
                  <span className="text-[10px] font-semibold text-rose-400 block mt-0.5">
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
