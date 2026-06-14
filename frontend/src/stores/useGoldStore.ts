/**
 * 黃金價格狀態管理 - Zustand Store
 */
import { create } from 'zustand';
import type { PricePoint, Decision, MarketData } from '@types';

interface GoldState {
  // 市場數據
  currentPrice: number;
  priceHistory: PricePoint[];
  marketData: MarketData;
  
  // 決策相關
  currentDecision: Decision | null;
  decisionHistory: Decision[];
  
  // 載入狀態
  isLoading: boolean;
  error: string | null;
  
  // Actions
  updatePrice: (price: number) => void;
  setMarketData: (data: MarketData) => void;
  setDecision: (decision: Decision) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearHistory: () => void;
}

export const useGoldStore = create<GoldState>((set) => ({
  // 初始狀態
  currentPrice: 0,
  priceHistory: [],
  marketData: {
    gold: [],
    dxy: [],
    rates: []
  },
  currentDecision: null,
  decisionHistory: [],
  isLoading: false,
  error: null,
  
  // Actions
  updatePrice: (price) => 
    set((state) => ({
      currentPrice: price,
      priceHistory: [
        ...state.priceHistory.slice(-999),  // 保留最近 1000 筆
        { price, timestamp: Date.now() }
      ]
    })),
    
  setMarketData: (data) => 
    set((state) => ({
      marketData: {
        ...state.marketData,
        ...data
      }
    })),
    
  setDecision: (decision) =>
    set((state) => ({
      currentDecision: decision,
      decisionHistory: [
        ...state.decisionHistory.slice(-49),  // 保留最近 50 筆
        decision
      ]
    })),
    
  setLoading: (isLoading) => set({ isLoading }),
  
  setError: (error) => set({ error }),
  
  clearHistory: () => set({
    priceHistory: [],
    decisionHistory: [],
    currentDecision: null
  })
}));
