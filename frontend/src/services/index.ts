/**
 * API 服務層
 */
import axios from 'axios';
import type { MarketData, Decision, ApiResponse } from '@types';

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
});

/**
 * 獲取市場數據
 */
export const fetchMarketData = async (): Promise<ApiResponse<MarketData>> => {
  try {
    const response = await api.get('/market');
    return { success: true, data: response.data };
  } catch (error) {
    return { 
      success: false, 
      error: error instanceof Error ? error.message : 'Failed to fetch market data' 
    };
  }
};

/**
 * 獲取交易決策
 */
export const fetchDecision = async (): Promise<ApiResponse<Decision>> => {
  try {
    const response = await api.get('/decision');
    return { success: true, data: response.data };
  } catch (error) {
    return { 
      success: false, 
      error: error instanceof Error ? error.message : 'Failed to fetch decision' 
    };
  }
};

/**
 * 獲取實時價格
 */
export const fetchPrice = async (): Promise<ApiResponse<{ price: number }>> => {
  try {
    const response = await api.get('/price');
    return { success: true, data: response.data };
  } catch (error) {
    return { 
      success: false, 
      error: error instanceof Error ? error.message : 'Failed to fetch price' 
    };
  }
};

export default api;
