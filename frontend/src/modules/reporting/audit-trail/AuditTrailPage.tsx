import React, { useState, useEffect } from 'react';
import { AuditEventItem } from '../../../types/auditTrail';
import { AuditFilterBar } from './components/AuditFilterBar';
import { AuditEventList } from './components/AuditEventList';
import { AuditEventDetailsDrawer } from './components/AuditEventDetailsDrawer';

export const AuditTrailPage: React.FC = () => {
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [selectedModule, setSelectedModule] = useState<string>('');
  const [searchCorrelation, setSearchCorrelation] = useState<string>('');
  const [selectedEvent, setSelectedEvent] = useState<AuditEventItem | null>(null);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);

  useEffect(() => {
    fetchEvents();
  }, [selectedCategory, selectedModule, searchCorrelation]);

  const fetchEvents = async () => {
    try {
      const params = new URLSearchParams();
      if (selectedCategory) params.append('event_category', selectedCategory);
      if (selectedModule) params.append('source_module', selectedModule);
      if (searchCorrelation) params.append('correlation_id', searchCorrelation);
      params.append('page', '1');
      params.append('page_size', '50');

      const res = await fetch(`/api/v1/audit/events?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setEvents(data.items);
      }
    } catch (e) {
      console.error('Failed to fetch audit events', e);
    }
  };

  const handleVerifyIntegrity = async () => {
    setIsVerifying(true);
    try {
      const res = await fetch('/api/v1/audit/integrity/verify', { method: 'POST' });
      if (res.ok) {
        await fetchEvents();
      }
    } catch (e) {
      console.error('Verification failed', e);
    } finally {
      setIsVerifying(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <AuditFilterBar
        selectedCategory={selectedCategory}
        onSelectCategory={setSelectedCategory}
        selectedModule={selectedModule}
        onSelectModule={setSelectedModule}
        searchCorrelation={searchCorrelation}
        onCorrelationChange={setSearchCorrelation}
        onVerifyIntegrity={handleVerifyIntegrity}
        isVerifying={isVerifying}
        onRefresh={fetchEvents}
      />

      <AuditEventList
        events={events}
        selectedEvent={selectedEvent}
        onSelectEvent={setSelectedEvent}
      />

      {selectedEvent && (
        <AuditEventDetailsDrawer
          event={selectedEvent}
          onClose={() => setSelectedEvent(null)}
        />
      )}
    </div>
  );
};

export default AuditTrailPage;
