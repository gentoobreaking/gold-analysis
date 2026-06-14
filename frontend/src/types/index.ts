/**
 * 核心類型定義 - Gold Analysis System
 */

// ============ 市場數據 ============

/** 價格數據點 */
export interface PricePoint {
  timestamp: number;
  price: number;
  volume?: number;
}

/** 市場數據結構 */
export interface MarketData {
  gold: PricePoint[];
  dxy: PricePoint[];
  rates: PricePoint[];
}

/** K線數據 */
export interface CandlestickData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

// ============ 交易決策 ============

/** 交易決策類型 */
export type DecisionType = 'buy' | 'sell' | 'hold';

/** 交易決策 */
export interface Decision {
  id: string;
  type: DecisionType;
  confidence: number;  // 0-100
  reason: string;
  timestamp: number;
  price?: number;
}

/** 決策信號 */
export interface DecisionSignal {
  buySignals: string[];
  sellSignals: string[];
  holdSignals: string[];
}

// ============ 技術指標 ============

/** 移動平均線 */
export interface MovingAverage {
  period: number;
  values: number[];
}

/** MACD */
export interface MACD {
  macd: number;
  signal: number;
  histogram: number;
}

/** RSI */
export interface RSI {
  value: number;
  overbought: boolean;
  oversold: boolean;
}

// ============ 图表配置 ============

/** 圖表配置 */
export interface ChartConfig {
  width: number;
  height: number;
  theme: 'dark' | 'light';
  showVolume: boolean;
  timeframes: string[];
}

// ============ 狀態管理 ============

/** 載入狀態 */
export interface LoadingState {
  isLoading: boolean;
  error: string | null;
}

/** API 回應 */
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}
