/**
 * useRealtimeData.ts — 即時數據 Hook
 *
 * 包含：
 * - useRealtimePrice    即時價格自動刷新
 * - useChartInteraction 圖表交互相關（十字準線、縮放）
 * - useWebSocket        WebSocket 連接（預留接口，現用 mock）
 */
import { useEffect, useRef, useState, useCallback } from 'react';

// ── 基礎類型 ────────────────────────────────────────────────────────────────

export interface PriceTick {
  sell: number;
  buy: number;
  timestamp: string;
}

export interface CrosshairState {
  time: string;
  price: number;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
}

// ── Mock 價格工廠 ────────────────────────────────────────────────────────────

let _mockBase = 8200;
const _mockSellBuy = (base: number): { sell: number; buy: number } => {
  const spread = 5 + Math.random() * 5;
  const half = spread / 2;
  return { sell: base + half, buy: base - half };
};

const nextMockTick = (): PriceTick => {
  _mockBase += (Math.random() - 0.48) * 8; // 輕微漂移
  const { sell, buy } = _mockSellBuy(_mockBase);
  return { sell, buy, timestamp: new Date().toISOString() };
};

// ── useRealtimePrice ────────────────────────────────────────────────────────

/**
 * 即時價格自動刷新。
 * @param fetchFn   真實 API（或 mock）
 * @param interval  刷新間隔（ms），預設 5 秒
 * @param enabled   是否啟用，預設 true
 */
export function useRealtimePrice(
  fetchFn: () => Promise<PriceTick>,
  interval = 5_000,
  enabled = true,
) {
  const [tick, setTick] = useState<PriceTick | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  const fetch = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchFn();
      if (mountedRef.current) {
        setTick(data);
        setLastUpdated(new Date());
      }
    } catch (e: any) {
      if (mountedRef.current) setError(e?.message ?? '更新失敗');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, [fetchFn, enabled]);

  // 首次掛載主動抓一次
  useEffect(() => {
    mountedRef.current = true;
    if (enabled) fetch();
    return () => { mountedRef.current = false; };
  }, [enabled]); // eslint-disable-line react-hooks/exhaustive-deps

  // 計時器自動刷新
  useEffect(() => {
    if (!enabled) return;
    timerRef.current = setInterval(fetch, interval);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [enabled, interval, fetch]);

  /** 手動立即刷新 */
  const refresh = useCallback(() => fetch(), [fetch]);

  return { tick, loading, error, lastUpdated, refresh };
}

// ── useRealtimePrice.mock 工廠 ─────────────────────────────────────────────

/** 快速取得一個 mock fetchFn（用於開發 / 未接 API 時） */
export function makeMockPriceFetch(days = 30): () => Promise<PriceTick> {
  return async () => {
    await new Promise((r) => setTimeout(r, 100 + Math.random() * 200));
    return nextMockTick();
  };
}

// ── useChartInteraction ────────────────────────────────────────────────────

/**
 * 圖表交互相關狀態（十字準線顯示、縮放系數）。
 * 可搭配 TradingView Lightweight Charts 的 crosshair.move 事件使用。
 *
 * 用法：
 *   const { crosshair, zoom, onCrosshairMove, onZoom } = useChartInteraction();
 *
 *   chart.subscribeCrosshairMove((param) => {
 *     onCrosshairMove(param);
 *   });
 */
export function useChartInteraction() {
  const [crosshair, setCrosshair] = useState<CrosshairState | null>(null);
  const [zoom, setZoom] = useState(1); // 1 = 原始大小
  const containerRef = useRef<HTMLDivElement | null>(null);

  /** 十字準線移動 callback（給 chart.subscribeCrosshairMove 用） */
  const onCrosshairMove = useCallback(
    (param: { time?: number; point?: { x: number; y: number } }) => {
      if (!param.time) { setCrosshair(null); return; }
      const d = new Date((param.time as number) * 1000);
      setCrosshair({
        time: d.toLocaleString('zh-TW', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }),
        price: 0, // 需由調用方透過 param.seriesData 填入
      });
    },
    [],
  );

  /** 縮放（滾輪 / 雙擊） */
  const onZoom = useCallback((delta: number) => {
    setZoom((z) => Math.max(0.5, Math.min(3, z + delta * 0.1)));
  }, []);

  /** 綁定圖表容器 DOM ref */
  const bindContainer = useCallback((el: HTMLDivElement | null) => {
    containerRef.current = el;
    if (el) {
      el.addEventListener('wheel', (e: WheelEvent) => {
        e.preventDefault();
        onZoom(e.deltaY < 0 ? 1 : -1);
      }, { passive: false });
    }
  }, [onZoom]);

  /** 重置縮放 */
  const resetZoom = useCallback(() => setZoom(1), []);

  return {
    crosshair,
    zoom,
    containerRef,
    onCrosshairMove,
    onZoom,
    bindContainer,
    resetZoom,
  };
}

// ── useWebSocket ───────────────────────────────────────────────────────────

export type WsStatus = 'idle' | 'connecting' | 'connected' | 'disconnected' | 'error';

export interface WebSocketOptions {
  /** WebSocket 伺服器 URL，例如 ws://localhost:8080/stream */
  url?: string;
  /** 自動連線，預設 true */
  autoConnect?: boolean;
  /** 重連間隔（ms），預設 5 秒 */
  reconnectInterval?: number;
  /** 最大重連次數，-1 = 無限，預設 -1 */
  maxReconnect?: number;
  /** 訊息處理 callback */
  onMessage?: (data: unknown) => void;
  /** 連線狀態變化 callback */
  onStatusChange?: (status: WsStatus) => void;
  /** 錯誤 callback */
  onError?: (err: Event) => void;
}

/**
 * WebSocket 連接 hook。
 * 預留接口：url 為空時自動使用 mock 定時推送，
 * 替換真實 URL 即可切換到實際 WebSocket 服務。
 */
export function useWebSocket(options: WebSocketOptions = {}) {
  const {
    url,
    autoConnect = true,
    reconnectInterval = 5_000,
    maxReconnect = -1,
    onMessage,
    onStatusChange,
    onError,
  } = options;

  const [status, setStatus] = useState<WsStatus>(url ? 'idle' : 'idle');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectCountRef = useRef(0);
  const mountedRef = useRef(true);

  const setStatus_ = useCallback((s: WsStatus) => {
    if (!mountedRef.current) return;
    setStatus(s);
    onStatusChange?.(s);
  }, [onStatusChange]);

  const connect = useCallback(() => {
    // 沒有 URL → 使用 mock 模式
    if (!url) {
      setStatus_('connecting');
      // 模擬 500ms 連線延遲
      const t = setTimeout(() => {
        if (!mountedRef.current) return;
        setStatus_('connected');
        // mock 推送：每 3 秒一筆 tick
        const mockInterval = setInterval(() => {
          if (!mountedRef.current || !wsRef.current) return;
          const tick = nextMockTick();
          wsRef.current.dispatchEvent(new MessageEvent('message', { data: JSON.stringify(tick) }));
        }, 3_000);
        // 把 mock interval 存在自訂屬性
        (wsRef.current as any).__mockInterval = mockInterval;
      }, 500);
      // mock ws 對象
      wsRef.current = {
        close: () => {
          clearTimeout(t);
          clearInterval((wsRef.current as any)?.__mockInterval);
          if (mountedRef.current) setStatus_('disconnected');
        },
        dispatchEvent: (e: Event) => {
          if (e instanceof MessageEvent) onMessage?.(e.data);
          return true;
        },
      } as unknown as WebSocket;
      return;
    }

    // 真實 WebSocket
    setStatus_('connecting');
    try {
      const ws = new WebSocket(url);
      ws.onopen = () => {
        if (!mountedRef.current) { ws.close(); return; }
        reconnectCountRef.current = 0;
        setStatus_('connected');
      };
      ws.onmessage = (evt) => {
        try { onMessage?.(JSON.parse(evt.data)); } catch { onMessage?.(evt.data); }
      };
      ws.onerror = (err) => { onError?.(err); setStatus_('error'); };
      ws.onclose = () => {
        if (!mountedRef.current) return;
        setStatus_('disconnected');
        // 重連邏輯
        if (maxReconnect === -1 || reconnectCountRef.current < maxReconnect) {
          reconnectCountRef.current++;
          reconnectTimerRef.current = setTimeout(connect, reconnectInterval);
        }
      };
      wsRef.current = ws;
    } catch {
      setStatus_('error');
    }
  }, [url, maxReconnect, reconnectInterval, onMessage, onError, setStatus_]);

  const disconnect = useCallback(() => {
    reconnectCountRef.current = maxReconnect; // 阻止重連
    if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    wsRef.current?.close();
    wsRef.current = null;
    setStatus_('disconnected');
  }, [maxReconnect, setStatus_]);

  // 自動連線
  useEffect(() => {
    mountedRef.current = true;
    if (autoConnect) connect();
    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return { status, connect, disconnect };
}

// ── 整合導出（統一入口） ────────────────────────────────────────────────────

/**
 * 整合式即時數據 hook。
 * 同時提供價格刷新 + 圖表交互 + WebSocket 狀態。
 *
 * 使用方式：
 *   const { tick, loading, error, lastUpdated, refresh,
 *           crosshair, zoom, bindContainer, resetZoom,
 *           wsStatus } = useRealtimeData({
 *     fetchFn: fetchCurrentPrice,  // 替換為你的 API
 *     interval: 5000,
 *     wsUrl: 'ws://localhost:8080/stream', // 可選
 *   });
 */
export interface UseRealtimeDataOptions {
  /** 價格取得函式 */
  fetchFn?: () => Promise<PriceTick>;
  /** 刷新間隔（ms），預設 5 秒 */
  interval?: number;
  /** WebSocket URL，若不提供則用 mock */
  wsUrl?: string;
  /** 自動啟用，預設 true */
  enabled?: boolean;
  /** 訊息處理 */
  onMessage?: (data: unknown) => void;
}

export function useRealtimeData(options: UseRealtimeDataOptions = {}) {
  const { fetchFn, interval = 5_000, wsUrl, enabled = true, onMessage } = options;

  const effectiveFetch = useCallback(
    () => fetchFn?.() ?? nextMockTick() as unknown as Promise<PriceTick>,
    [fetchFn],
  );

  const price = useRealtimePrice(effectiveFetch, interval, enabled);
  const interaction = useChartInteraction();
  const ws = useWebSocket({
    url: wsUrl,
    autoConnect: !!wsUrl,
    onMessage,
  });

  return {
    // 即時價格
    tick: price.tick,
    loading: price.loading,
    error: price.error,
    lastUpdated: price.lastUpdated,
    refresh: price.refresh,
    // 圖表交互
    crosshair: interaction.crosshair,
    zoom: interaction.zoom,
    bindContainer: interaction.bindContainer,
    resetZoom: interaction.resetZoom,
    onCrosshairMove: interaction.onCrosshairMove,
    onZoom: interaction.onZoom,
    // WebSocket
    wsStatus: ws.status,
    wsConnect: ws.connect,
    wsDisconnect: ws.disconnect,
  };
}
