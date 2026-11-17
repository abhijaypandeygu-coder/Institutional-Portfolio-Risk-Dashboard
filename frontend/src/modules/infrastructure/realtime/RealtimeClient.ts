export type RealtimeChannelType = 'market' | 'portfolio' | 'risk' | 'alerts';

export type ConnectionState =
  | 'DISCONNECTED'
  | 'CONNECTING'
  | 'CONNECTED'
  | 'RECONNECTING'
  | 'RESYNC_REQUIRED'
  | 'FAILED';

export interface RealtimeEventEnvelope<T = any> {
  event_id: string;
  event_type: string;
  channel: RealtimeChannelType;
  schema_version: number;
  stream_id: string;
  sequence: number;
  occurred_at: string;
  published_at: string;
  producer_module: string;
  resource_id: string;
  quality_status: string;
  payload: T;
}

export type RealtimeEventHandler<T = any> = (event: RealtimeEventEnvelope<T>) => void;

export class RealtimeClient {
  private ws: WebSocket | null = null;
  private url: string;
  private state: ConnectionState = 'DISCONNECTED';
  private connectionId: string | null = null;
  private listeners: Map<string, Set<RealtimeEventHandler>> = new Map();
  private stateListeners: Set<(state: ConnectionState) => void> = new Set();
  private streamSequences: Map<string, number> = new Map();
  private pingIntervalId: any = null;

  constructor(url: string = `ws://${window.location.host}/api/v1/ws`) {
    this.url = url;
  }

  public connect(token?: string) {
    if (this.state === 'CONNECTING' || this.state === 'CONNECTED') return;

    this.setState('CONNECTING');
    const wsUrl = token ? `${this.url}?token=${encodeURIComponent(token)}` : this.url;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.setState('CONNECTED');
      this.startHeartbeat();
    };

    this.ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        this.handleMessage(msg);
      } catch (e) {
        console.error('Failed to parse realtime WebSocket message', e);
      }
    };

    this.ws.onclose = () => {
      this.setState('DISCONNECTED');
      this.stopHeartbeat();
    };

    this.ws.onerror = (err) => {
      console.error('Realtime WebSocket error', err);
      this.setState('FAILED');
    };
  }

  public subscribe(
    channel: RealtimeChannelType,
    resourceIds: string[] = [],
    eventTypes: string[] = [],
    options: Record<string, any> = {}
  ) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const subReq = {
        type: 'subscribe',
        request_id: `req-${Date.now()}`,
        channel,
        resource_ids: resourceIds,
        event_types: eventTypes,
        options,
      };
      this.ws.send(JSON.stringify(subReq));
    }
  }

  public on(channel: RealtimeChannelType, eventType: string, handler: RealtimeEventHandler) {
    const key = `${channel}:${eventType}`;
    if (!this.listeners.has(key)) {
      this.listeners.set(key, new Set());
    }
    this.listeners.get(key)!.add(handler);
  }

  public off(channel: RealtimeChannelType, eventType: string, handler: RealtimeEventHandler) {
    const key = `${channel}:${eventType}`;
    if (this.listeners.has(key)) {
      this.listeners.get(key)!.delete(handler);
    }
  }

  public onStateChange(listener: (state: ConnectionState) => void) {
    this.stateListeners.add(listener);
    listener(this.state);
  }

  private setState(state: ConnectionState) {
    this.state = state;
    this.stateListeners.forEach((l) => l(state));
  }

  private handleMessage(msg: any) {
    if (msg.type === 'connection.ack') {
      this.connectionId = msg.connection_id;
    } else if (msg.type === 'event' && msg.event) {
      const event: RealtimeEventEnvelope = msg.event;
      // Sequence gap detection
      const prevSeq = this.streamSequences.get(event.stream_id);
      if (prevSeq !== undefined && event.sequence > prevSeq + 1) {
        console.warn(
          `Sequence gap detected in stream ${event.stream_id}: expected ${prevSeq + 1}, received ${event.sequence}. Requesting resync.`
        );
        this.requestResync(event.stream_id, prevSeq + 1);
      }
      this.streamSequences.set(event.stream_id, event.sequence);

      // Dispatch to handlers
      const key = `${event.channel}:${event.event_type}`;
      const channelKey = `${event.channel}:*`;
      this.listeners.get(key)?.forEach((fn) => fn(event));
      this.listeners.get(channelKey)?.forEach((fn) => fn(event));
    } else if (msg.type === 'resync.required') {
      this.setState('RESYNC_REQUIRED');
    }
  }

  private requestResync(streamId: string, fromSequence: number) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          type: 'resync.request',
          request_id: `resync-${Date.now()}`,
          stream_id: streamId,
          from_sequence: fromSequence,
        })
      );
    }
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.pingIntervalId = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
      }
    }, 25000);
  }

  private stopHeartbeat() {
    if (this.pingIntervalId) {
      clearInterval(this.pingIntervalId);
      this.pingIntervalId = null;
    }
  }
}

export const realtimeClient = new RealtimeClient();
