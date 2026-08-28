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
export interface DecisionExplanationRuleFactor {
  factor: string;
  label?: string;
  score: number;
  weight?: number;
  tilt: number;
  direction: 'bullish' | 'bearish' | 'neutral';
}

export interface DecisionExplanationMlFeature {
  feature: string;
  contribution: number;
  direction: 'positive' | 'negative' | 'neutral';
  value?: number | null;
}

// 決策可解釋性（T062）：規則決策給 top_factors + triggered_rules；ML 決策給 top_features
export interface DecisionExplanation {
  method?: string;
  model_type?: string;
  top_factors?: DecisionExplanationRuleFactor[];
  triggered_rules?: string[];
  top_features?: DecisionExplanationMlFeature[];
}

export interface DecisionResponse {
  action: 'buy' | 'sell' | 'hold';
  confidence: number;
  signal: string;
  reason: string[];
  price: number;
  timestamp: string;
  explanation?: DecisionExplanation;
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

// ── ML 運維 API ────────────────────────────────────────────────────────────────
export interface MLOperationsMonitorResponse {
  alerts: unknown[];
  drift: unknown;
  health: unknown;
}

export interface MLOperationsRetrainResponse {
  retrained: boolean;
  reason?: string;
}

export interface MLOperationsABAssignResponse {
  experiment_id: string;
  variant: string;
  user_id: string;
  symbol: string;
}

export interface MLOperationsExecuteResponse {
  executed: boolean;
  success: boolean;
  response?: unknown;
  event?: unknown;
}

export const fetchMLMonitor = async (prices: unknown[]): Promise<MLOperationsMonitorResponse> => {
  const { data } = await api.post('/api/ml/monitor', { prices });
  return data;
};

export const fetchMLRetrain = async (prices: unknown[], trigger?: string, min_samples = 200): Promise<MLOperationsRetrainResponse> => {
  const { data } = await api.post('/api/ml/retrain', { prices, trigger, min_samples });
  return data;
};

export const fetchMLABAssign = async (user_id: string, symbol = 'XAUUSD', experiment_id = 'default'): Promise<MLOperationsABAssignResponse> => {
  const { data } = await api.post('/api/ml/ab/assign', { user_id, symbol, experiment_id });
  return data;
};

export const fetchMLExecute = async (decision: unknown): Promise<MLOperationsExecuteResponse> => {
  const { data } = await api.post('/api/trading/execute', decision);
  return data;
};

// ── 回測 / 策略比較 API (T063) ───────────────────────────────────────────────

export interface PriceSeriesResponse {
  asset: string;
  dates: string[];
  prices: number[];
  count: number;
}

export interface StrategyComparisonItem {
  final_equity: number;
  total_return: number;
  annualized_return: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  win_rate: number;
  n_trades: number;
  equity_curve?: number[];
  errors?: string[];
}

export interface StrategyComparisonResponse {
  results: Record<string, StrategyComparisonItem>;
}

export const fetchBacktestPrices = async (
  asset = 'GOLD',
  limit = 400,
): Promise<PriceSeriesResponse> => {
  const { data } = await api.get<PriceSeriesResponse>(
    `/api/backtest/prices?asset=${encodeURIComponent(asset)}&limit=${limit}`,
  );
  return data;
};

export const runBacktestCompare = async (
  prices: number[],
  strategies: string[] = ['ma_crossover', 'rsi', 'macd', 'combined'],
): Promise<StrategyComparisonResponse> => {
  const { data } = await api.post<StrategyComparisonResponse>('/api/backtest/compare', {
    prices,
    strategies,
  });
  return data;
};

// ─── T064: 投資組合級風險 ───────────────────────────────────────────────
export interface CorrelationMatrix {
  assets: string[];
  matrix: number[][];
  valid: boolean;
}

export interface RiskSampleResponse {
  assets: string[];
  correlation: CorrelationMatrix;
  factor_exposure: Record<string, number>;
  note: string;
}

export interface PortfolioRiskRequest {
  weights: number[];
  returns: Record<string, number[]>;
  factor_returns?: Record<string, number[]>;
  confidence?: number;
  portfolio_value?: number;
  method?: 'parametric' | 'cornish_fisher';
}

export interface PortfolioRiskResponse {
  correlation: CorrelationMatrix;
  portfolio_var: number;
  portfolio_cvar: number;
  portfolio_vol: number;
  factor_exposure: Record<string, number>;
  warnings: string[];
}

export const fetchRiskSample = async (): Promise<RiskSampleResponse> => {
  const { data } = await api.get<RiskSampleResponse>('/api/risk/sample');
  return data;
};

export const runPortfolioRisk = async (
  body: PortfolioRiskRequest,
): Promise<PortfolioRiskResponse> => {
  const { data } = await api.post<PortfolioRiskResponse>('/api/risk/portfolio', body);
  return data;
};

export { api };