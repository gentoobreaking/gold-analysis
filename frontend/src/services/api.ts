/**
 * Gold Analysis API 服務層 - MVP 版本
 */
import axios from 'axios';

const api = axios.create({
  baseURL: '',
  timeout: 10000,
});

// ── 價格 API ────────────────────────────────────────────────────────────────
export interface PriceResponse {
  sell: number;
  buy: number;
  sell_twd: number;
  buy_twd: number;
  timestamp: string;
  change: number;
  change_pct: number;
}

export interface HistoryPoint {
  timestamp: string;
  sell: number;
  buy: number;
}

export interface HistoryResponse {
  data: HistoryPoint[];
  count: number;
}

// ── 決策 API ────────────────────────────────────────────────────────────────
export interface DecisionResponse {
  action: 'buy' | 'sell' | 'hold';
  confidence: number;
  signal: string;
  reason: string[];
  price: number;
  timestamp: string;
}

export const fetchCurrentPrice = async (): Promise<PriceResponse> => {
  const resp = await api.get<PriceResponse>('/api/prices/current');
  return resp.data;
};

export const fetchHistory = async (days = 7): Promise<HistoryResponse> => {
  const resp = await api.get<HistoryResponse>(`/api/prices/history?days=${days}`);
  return resp.data;
};

export const fetchDecision = async (): Promise<DecisionResponse> => {
  const resp = await api.get<DecisionResponse>('/api/decisions/recommend');
  return resp.data;
};

// ── 技術分析 API ─────────────────────────────────────────────────────────────

export interface TechnicalIndicator {
  name: string;
  value: number | null;
  signal: 'buy' | 'sell' | 'hold';
  description: string;
}

export interface TechnicalSignal {
  type: string;
  action: 'buy' | 'sell' | 'hold';
  label: string;
  strength: number;
}

export interface TechnicalsResponse {
  symbol: string;
  timeframe: string;
  indicators: {
    rsi: TechnicalIndicator;
    macd: TechnicalIndicator;
    bollinger: TechnicalIndicator;
    ma_short: TechnicalIndicator;
    ma_long: TechnicalIndicator;
  };
  signals: TechnicalSignal[];
  trend_score: number;
  risk_level: 'low' | 'medium' | 'high';
  recommendation: string;
  support_resistance: Array<{ type: 'support' | 'resistance'; price: number }>;
  error?: string;
}

export const fetchTechnicals = async (
  symbol = 'TAIFEX-TGF1',
  timeframe = '1D'
): Promise<TechnicalsResponse> => {
  const resp = await api.get<TechnicalsResponse>(
    `/api/technicals?symbol=${encodeURIComponent(symbol)}&timeframe=${encodeURIComponent(timeframe)}`
  );
  return resp.data;
};
export { api };
