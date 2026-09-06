"use client";

import { useEffect, useRef, useState } from "react";
import { WebSocketMessage } from "@/types";
import { getWebSocketUrl } from "@/utils/apiConfig";

export function useKaraokeSocket(onMessageReceived?: (msg: WebSocketMessage) => void) {
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const onMessageRef = useRef(onMessageReceived);

  useEffect(() => {
    onMessageRef.current = onMessageReceived;
  }, [onMessageReceived]);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: NodeJS.Timeout | null = null;
    let isUnmounted = false;

    const connect = () => {
      if (isUnmounted) return;

      const wsUrl = getWebSocketUrl();

      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          if (!isUnmounted) {
            setIsConnected(true);
          }
        };

        ws.onmessage = (event) => {
          if (isUnmounted) return;
          try {
            const data: WebSocketMessage = JSON.parse(event.data);
            setLastMessage(data);
            if (onMessageRef.current) {
              onMessageRef.current(data);
            }
          } catch {
            // ignore non-json
          }
        };

        ws.onclose = () => {
          if (!isUnmounted) {
            setIsConnected(false);
            timer = setTimeout(connect, 3000);
          }
        };

        ws.onerror = () => {
          if (!isUnmounted) {
            setIsConnected(false);
            ws?.close();
          }
        };
      } catch {
        if (!isUnmounted) {
          setIsConnected(false);
          timer = setTimeout(connect, 3000);
        }
      }
    };

    connect();

    return () => {
      isUnmounted = true;
      if (timer) clearTimeout(timer);
      if (ws) ws.close();
    };
  }, []);

  return { isConnected, lastMessage };
}
