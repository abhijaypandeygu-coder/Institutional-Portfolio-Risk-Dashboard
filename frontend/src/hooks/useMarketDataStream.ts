import { useEffect, useRef, useState, useCallback } from 'react';
import { CurrentQuoteItem, OrderBookDepthLadder } from '../types/dashboard';

interface UseMarketDataStreamOptions {
  instrumentId: string | null;
  symbol?: string;
  levelsCount?: number;
  enabled?: boolean;
}

interface UseMarketDataStreamResult {
  isConnected: boolean;
  lastMessageTime: string | null;
  streamingQuote: CurrentQuoteItem | null;
  streamingDepth: OrderBookDepthLadder | null;
}

export function useMarketDataStream({
  instrumentId,
  symbol,
  levelsCount = 5,
  enabled = true,
}: UseMarketDataStreamOptions): UseMarketDataStreamResult {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessageTime, setLastMessageTime] = useState<string | null>(null);
  const [streamingQuote, setStreamingQuote] = useState<CurrentQuoteItem | null>(null);
  const [streamingDepth, setStreamingDepth] = useState<OrderBookDepthLadder | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<any>(null);
  const reconnectTimeoutRef = useRef<any>(null);

  const activeTarget = symbol || instrumentId;

  // Clear streaming state when instrument changes
  useEffect(() => {
    setStreamingQuote(null);
    setStreamingDepth(null);
  }, [activeTarget]);

  const connect = useCallback(() => {
    if (!enabled || !activeTarget) return;

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/v1/ws`;
      
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        // Subscribe to market events for active symbol/instrument
        const subMsg = {
          type: 'subscribe',
          request_id: `sub-${Date.now()}`,
          channel: 'market',
          resource_ids: [activeTarget],
          event_types: ['market.orderbook.depth', 'market.quote'],
          options: { depth: levelsCount },
        };
        ws.send(JSON.stringify(subMsg));

        // Start heartbeat ping every 20 seconds
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
          }
        }, 20000);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'event' && data.event) {
            const evt = data.event;
            const payload = evt.payload;
            if (evt.event_type === 'market.orderbook.depth' && payload) {
              setStreamingDepth(payload as OrderBookDepthLadder);
              setLastMessageTime(new Date().toLocaleTimeString());
            } else if (evt.event_type === 'market.quote' && payload) {
              setStreamingQuote(payload as CurrentQuoteItem);
              setLastMessageTime(new Date().toLocaleTimeString());
            }
          }
        } catch {
          // ignore parsing error
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
        // Attempt reconnect after 3 seconds if still enabled
        if (enabled && activeTarget) {
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, 3000);
        }
      };

      ws.onerror = () => {
        setIsConnected(false);
      };
    } catch {
      setIsConnected(false);
    }
  }, [enabled, activeTarget, levelsCount]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      setIsConnected(false);
    };
  }, [connect]);

  return {
    isConnected,
    lastMessageTime,
    streamingQuote,
    streamingDepth,
  };
}
