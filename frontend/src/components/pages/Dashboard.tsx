/**
 * Dashboard 頁面 - MVP 版（串接真實 API）
 */
import React, { useEffect, useState } from 'react';
import { fetchCurrentPrice, fetchDecision, fetchHistory, type PriceResponse, type DecisionResponse } from '@services/api';

const Dashboard: React.FC = () => {
  const [price, setPrice] = useState<PriceResponse | null>(null);
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [history, setHistory] = useState<Array<{timestamp: string; sell: number; buy: number}>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [priceData, decisionData, historyData] = await Promise.all([
        fetchCurrentPrice(),
        fetchDecision(),
        fetchHistory(3),
      ]);
      setPrice(priceData);
      setDecision(decisionData);
      setHistory(historyData.data.slice(-20));
    } catch (e: any) {
      setError(e?.message ?? '無法載入數據');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 60_000); // 每分鐘更新
    return () => clearInterval(interval);
  }, []);

  const actionColor = (action: string) => {
    if (action === 'buy') return 'text-green-400';
    if (action === 'sell') return 'text-red-400';
    return 'text-yellow-400';
  };

  const formatTs = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleString('zh-TW', { hour: '2-digit', minute: '2-digit', month: 'numeric', day: 'numeric' });
    } catch { return ts; }
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">🥇 黃金分析系統</h1>
          <p className="text-sm text-gray-400 mt-0.5">台銀黃金存折 · 即時報價 · AI 決策建議</p>
        </div>
        <button onClick={loadData} className="px-3 py-1.5 bg-yellow-500 hover:bg-yellow-400 text-slate-900 rounded-lg text-sm font-medium transition-colors">
          🔄 重新整理
        </button>
      </div>

      {loading && <div className="text-gray-400 text-sm">載入中...</div>}
      {error && <div className="bg-red-900/30 text-red-400 p-3 rounded">⚠️ {error}</div>}

      {/* 價格卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-800 rounded-lg p-4">
          <div className="text-gray-400 text-xs mb-1">台灣銀行賣出</div>
          <div className="text-2xl font-bold text-white">{price?.sell ?? '--'}</div>
          <div className="text-xs text-gray-500">NT/克</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-4">
          <div className="text-gray-400 text-xs mb-1">台灣銀行買進</div>
          <div className="text-2xl font-bold text-white">{price?.buy ?? '--'}</div>
          <div className="text-xs text-gray-500">NT/克</div>
        </div>
        <div className="bg-slate-800 rounded-lg p-4">
          <div className="text-gray-400 text-xs mb-1">日內變動</div>
          <div className={`text-2xl font-bold ${(price?.change ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {price ? `${(price.change ?? 0) >= 0 ? '+' : ''}${price.change?.toFixed(1)}` : '--'}
          </div>
          <div className={`text-xs ${(price?.change_pct ?? 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {price ? `${(price.change_pct ?? 0) >= 0 ? '+' : ''}${price.change_pct?.toFixed(2)}%` : '--'}
          </div>
        </div>
        <div className="bg-slate-800 rounded-lg p-4">
          <div className="text-gray-400 text-xs mb-1">更新時間</div>
          <div className="text-lg font-semibold text-white">{price ? formatTs(price.timestamp) : '--'}</div>
        </div>
      </div>

      {/* 決策卡片 */}
      {decision && (
        <div className={`rounded-lg p-4 border ${decision.action === 'buy' ? 'bg-green-900/20 border-green-700' : decision.action === 'sell' ? 'bg-red-900/20 border-red-700' : 'bg-yellow-900/20 border-yellow-700'}`}>
          <div className="flex items-center gap-3 mb-2">
            <span className="text-3xl">{decision.action === 'buy' ? '💰' : decision.action === 'sell' ? '⚠️' : '➡️'}</span>
            <div>
              <div className={`text-2xl font-bold ${actionColor(decision.action)}`}>{decision.signal}</div>
              <div className="text-sm text-gray-400">信心度 {Math.round(decision.confidence * 100)}%</div>
            </div>
          </div>
          <div className="text-sm text-gray-300 space-y-1">
            {decision.reason.map((r, i) => <div key={i}>• {r}</div>)}
          </div>
        </div>
      )}

      {/* 迷你歷史圖（文字版） */}
      <div className="bg-slate-800 rounded-lg p-4">
        <div className="text-white font-semibold mb-3">📊 近三日趨勢（賣出價）</div>
        <div className="flex items-end gap-1 h-24">
          {history.length === 0 && <div className="text-gray-500">暫無數據</div>}
          {history.map((h, i) => {
            const min = Math.min(...history.map(x => x.sell));
            const max = Math.max(...history.map(x => x.sell));
            const range = max - min || 1;
            const height = ((h.sell - min) / range) * 80 + 10;
            return (
              <div key={i} className="flex-1 flex flex-col items-center gap-1" title={`${formatTs(h.timestamp)} ${h.sell}`}>
                <div className="text-xs text-gray-400">{h.sell}</div>
                <div className="w-full bg-blue-500 rounded-t" style={{ height: `${height}px` }} />
                <div className="text-xs text-gray-600">{new Date(h.timestamp).toLocaleDateString('zh-TW', {month:'numeric',day:'numeric'})}</div>
              </div>
            );
          })}
        </div>
        <div className="flex justify-between text-xs text-gray-500 mt-2">
          <span>數據來源：台灣銀行黃金存摺</span>
          <span>{history.length} 筆</span>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
