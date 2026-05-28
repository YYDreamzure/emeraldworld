import { useCallback, useEffect, useRef, useState } from "react";
import type { WorldSnapshot } from "../types";

export function useWorldSocket() {
  const [snapshot, setSnapshot] = useState<WorldSnapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host =
      import.meta.env.DEV ? "127.0.0.1:8765" : window.location.host;
    const ws = new WebSocket(`${proto}//${host}/ws`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "snapshot") setSnapshot(msg.data);
    };
  }, []);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  const send = useCallback((action: string, agent?: string) => {
    wsRef.current?.send(JSON.stringify({ action, agent }));
  }, []);

  return { snapshot, connected, send };
}
