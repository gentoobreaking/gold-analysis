/**
 * Summary 頁面 - 概要分頁
 * 深色主題，顯示即時報價、技術指標摘要、決策建議
 */
import React, { useEffect, useState } from 'react';
import { fetchCurrentPrice, fetchDecision, fetchHistory, type PriceResponse, type DecisionResponse } from '@services/api';

const Summary: React.FC = () => {
  const [price, setPrice] = useState<PriceResponse | null>(null);
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [history, setHistory] = useState<Array<{ timestamp: string; sell: number; buy: number }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [priceData, decisionData, historyData] = await Promise.all([
        fetchCurrentPrice(),
        fetchDecision(),
        fetchHistory(7),
      ]);
      setPrice(priceData);
      setDecision(decisionData);
      setHistory(historyData.data);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err?.message ?? '無法載入數據');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // 計算技術指標（參考 Analysis.tsx）
  const calcSMA = (arr: number[], period: number) => {
    if (arr.length < period) return null;
    const slice = arr.slice(-period);
    return slice.reduce((s, v) => s + v, 0) / period;
  };

  const calcRSI = (arr: number[], period = 14) => {
    if (arr.length < period + 1) return null;
    let gains = 0,
      losses = 0;
    for (let i = arr.length - period; i < arr.length; i++) {
      const diff = arr[i] - arr[i - 1];
      if (diff > 0) gains += diff;
      else losses += Math.abs(diff);
    }
    const avgGain = gains / period;
    const avgLoss = losses / period;
    if (avgLoss === 0) return 100;
    const rs = avgGain / avgLoss;
    return 100 - 100 / (1 + rs);
  };

  const prices = history.map((h) => h.sell);
  const ma5 = calcSMA(prices, Math.min(5, prices.length));
  const ma20 = calcSMA(prices, Math.min(20, prices.length));
  const rsi = calcRSI(prices);
  const currentSell = price?.sell ?? 0;

  // 趨勢判斷
  const trend = ma5 && ma20 ? (ma5 > ma20 ? '上升' : ma5 < ma20 ? '下降' : '震盪') : '資料不足';
  const trendColor = trend === '上升' ? 'text-green-400' : trend === '下降' ? 'text-red-400' : 'text-yellow-400';

  // RSI 判斷
  const rsiValue = rsi ?? 0;
  const rsiDesc = rsiValue > 70 ? '超買' : rsiValue < 30 ? '超賣' : '中性';
  const rsiColor = rsiValue > 70 ? 'text-red-400' : rsiValue < 30 ? 'text-green-400' : 'text-yellow-400';

  // 決策顏色
  const decisionColor =
    decision?.action === 'buy'
      ? 'text-green-400'
      : decision?.action === 'sell'
      ? 'text-red-400'
      : 'text-yellow-400';

  const formatTimestamp = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleString('zh-TW', {
        month: 'numeric',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return ts;
    }
  };

  return (
    <div className="space-y-6 p-4 bg-slate-800 text-white min-h-screen">
      {/* 頁首 */}
      <div>
        <h1 className="text-xl font-bold text-white">📊 市場概要</h1>
        <p className="text-gray-400 text-sm mt-0.5">黃金現貨報價 · 日內波動 · 市場情緒追蹤</p>
      </div>

      {loading && <div className="text-gray-400 text-sm animate-pulse">載入中...</div>}
      {error && <div className="bg-red-900/30 text-red-400 p-3 rounded">⚠️ {error}</div>}

      {/* 即時報價卡片 */}
      <div className="bg-slate-700/50 rounded-lg p-4">
        <h3 className="text-lg font-semibold mb-3 text-white">💹 即時報價</h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-slate-800 rounded-lg p-3">
            <div className="text-gray-400 text-xs mb-1">賣出價</div>
            <div className="text-2xl font-bold text-white">
              {price ? price.sell.toLocaleString() : '--'}
            </div>
            <div className="text-xs text-gray-500">NT/克</div>
          </div>
          <div className="bg-slate-800 rounded-lg p-3">
            <div className="text-gray-400 text-xs mb-1">買入價</div>
            <div className="text-2xl font-bold text-white">
              {price ? price.buy.toLocaleString() : '--'}
            </div>
            <div className="text-xs text-gray-500">NT/克</div>
          </div>
          <div className="bg-slate-800 rounded-lg p-3">
            <div className="text-gray-400 text-xs mb-1">漲跌幅</div>
            <div
              className={`text-2xl font-bold ${
                (price?.change ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
              }`}
            >
              {price
                ? `${(price.change ?? 0) >= 0 ? '+' : ''}${price.change.toFixed(1)} (${(price.change_pct ?? 0).toFixed(2)}%)`
                : '--'}
            </div>
          </div>
        </div>
      </div>

      {/* 技術指標摘要卡片 */}
      <div className="bg-slate-700/50 rounded-lg p-4">
        <h3 className="text-lg font-semibold mb-3 text-white">📈 技術指標摘要</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-slate-800 rounded-lg p-3">
            <div className="text-gray-400 text-xs mb-1">RSI</div>
            <div className={`text-xl font-bold ${rsiColor}`}>
              {rsi ? rsi.toFixed(1) : '--'}
            </div>
            <div className="text-xs text-gray-500">{rsi ? rsiDesc : ''}</div>
          </div>
          <div className="bg-slate-800 rounded-lg p-3">
            <div className="text-gray-400 text-xs mb-1">MA5</div>
            <div className="text-xl font-bold text-white">
              {ma5 ? ma5.toFixed(1) : '--'}
            </div>
            <div className="text-xs text-gray-500">NT/克</div>
          </div>
          <div className="bg-slate-800 rounded-lg p-3">
            <div className="text-gray-400 text-xs mb-1">MA20</div>
            <div className="text-xl font-bold text-white">
              {ma20 ? ma20.toFixed(1) : '--'}
            </div>
            <div className="text-xs text-gray-500">NT/克</div>
          </div>
          <div className="bg-slate-800 rounded-lg p-3">
            <div className="text-gray-400 text-xs mb-1">趨勢判斷</div>
            <div className={`text-xl font-bold ${trendColor}`}>{trend}</div>
            <div className="text-xs text-gray-500">MA5 vs MA20</div>
          </div>
        </div>
      </div>

      {/* 決策建議卡片 */}
      {decision && (
        <div
          className={`rounded-lg p-4 border ${
            decision.action === 'buy'
              ? 'bg-green-900/20 border-green-700'
              : decision.action === 'sell'
              ? 'bg-red-900/20 border-red-700'
              : 'bg-yellow-900/20 border-yellow-700'
          }`}
        >
          <h3 className="text-lg font-semibold mb-3 text-white">🎯 決策建議</h3>
          <div className="flex items-center gap-3 mb-3">
            <span className="text-3xl">
              {decision.action === 'buy' ? '💰' : decision.action === 'sell' ? '⚠️' : '➡️'}
            </span>
            <div>
              <div className={`text-2xl font-bold ${decisionColor}`}>{decision.signal}</div>
              <div className="text-sm text-gray-400">信心度 {Math.round(decision.confidence * 100)}%</div>
            </div>
          </div>
          <div className="text-sm text-gray-300 space-y-1">
            {decision.reason.map((r, i) => (
              <div key={i}>• {r}</div>
            ))}
          </div>
          {decision.timestamp && (
            <div className="text-xs text-gray-500 mt-3">
              更新時間：{formatTimestamp(decision.timestamp)}
            </div>
          )}
        </div>
      )}

      {/* 重新整理按鈕 */}
      <button
        onClick={loadData}
        className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm transition"
      >
        🔄 重新整理
      </button>
    </div>
  );
};

export default Summary;
