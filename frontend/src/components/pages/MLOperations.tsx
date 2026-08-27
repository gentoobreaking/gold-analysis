/**
 * ML Operations 頁面 - 監控、重訓、A/B 分流、交易執行
 */
import React, { useEffect, useState } from 'react';
import {
  fetchMLMonitor,
  fetchMLRetrain,
  fetchMLABAssign,
  fetchMLExecute,
  fetchDecision,
  fetchHistory,
  type MLOperationsMonitorResponse,
  type MLOperationsRetrainResponse,
  type MLOperationsABAssignResponse,
  type MLOperationsExecuteResponse,
  type DecisionResponse,
} from '@services/api';

const MLOperations: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // 監控狀態
  const [monitorData, setMonitorData] = useState<MLOperationsMonitorResponse | null>(null);
  // 重訓結果
  const [retrainResult, setRetrainResult] = useState<{ retrained: boolean; reason?: string } | null>(null);
  // A/B 分流結果
  const [abResult, setAbResult] = useState<{ variant: string; experiment_id: string } | null>(null);
  // 交易執行結果
  const [executeResult, setExecuteResult] = useState<{ executed: boolean; success: boolean; response?: any; event?: any } | null>(null);

  // 決策數據（用於交易執行）
  const [decision, setDecision] = useState<{ action: string; confidence: number; signal: string; reason: string[]; price: number; timestamp: string } | null>(null);

  // 歷史價格數據（用於監控/重訓）
  const [historyPrices, setHistoryPrices] = useState<Array<{ timestamp: string; sell: number; buy: number }>>([]);

  const clearMessages = () => {
    setError(null);
    setSuccess(null);
  };

  const handleError = (e: any, context: string) => {
    setError(`${context}: ${e?.response?.data?.detail ?? e?.message ?? '未知錯誤'}`);
  };

  // 載入歷史價格（用於監控/重訓輸入）
  const loadHistory = async () => {
    try {
      const resp = await fetchHistory(30);
      const prices = resp.data.map(p => ({ timestamp: p.timestamp, sell: p.sell, buy: p.buy }));
      setHistoryPrices(prices);
    } catch (e) {
      handleError(e, '載入歷史價格失敗');
    }
  };

  // 載入決策（用於交易執行）
  const loadDecision = async () => {
    try {
      const d = await fetchDecision();
      setDecision(d);
    } catch (e) {
      handleError(e, '載入決策失敗');
    }
  };

  useEffect(() => {
    loadHistory();
    loadDecision();
  }, []);

  // 觸發監控
  const handleMonitor = async () => {
    clearMessages();
    if (!historyPrices.length) {
      setError('無歷史價格數據，請先載入');
      return;
    }
    setLoading(true);
    try {
      // 轉換格式：需要 open, high, low, close, volume
      const prices = historyPrices.map(p => ({
        timestamp: p.timestamp,
        open: p.buy,
        high: p.buy * 1.002,
        low: p.buy * 0.998,
        close: p.buy,
        volume: 10000,
      }));
      const result = await fetchMLMonitor(prices);
      setMonitorData(result);
      setSuccess('監控快照完成');
    } catch (e) {
      handleError(e, '監控失敗');
    } finally {
      setLoading(false);
    }
  };

  // 觸發重訓
  const handleRetrain = async () => {
    clearMessages();
    if (!historyPrices.length) {
      setError('無歷史價格數據，請先載入');
      return;
    }
    setLoading(true);
    try {
      const prices = historyPrices.map(p => ({
        timestamp: p.timestamp,
        open: p.buy,
        high: p.buy * 1.002,
        low: p.buy * 0.998,
        close: p.buy,
        volume: 10000,
      }));
      const result = await fetchMLRetrain(prices, 'manual');
      setRetrainResult(result);
      setSuccess(result.retrained ? '重訓完成' : `未觸發重訓: ${result.reason ?? '未知原因'}`);
    } catch (e) {
      handleError(e, '重訓失敗');
    } finally {
      setLoading(false);
    }
  };

  // A/B 分流測試
  const handleABAssign = async () => {
    clearMessages();
    setLoading(true);
    try {
      const result = await fetchMLABAssign('test_user_123', 'XAUUSD');
      setAbResult({ variant: result.variant, experiment_id: result.experiment_id });
      setSuccess(`A/B 分流完成: ${result.variant}`);
    } catch (e) {
      handleError(e, 'A/B 分流失敗');
    } finally {
      setLoading(false);
    }
  };

  // 執行交易
  const handleExecute = async () => {
    clearMessages();
    if (!decision) {
      setError('無決策數據，請先載入決策');
      return;
    }
    setLoading(true);
    try {
      // 轉換決策格式給執行端點
      const executePayload = {
        action: decision.action.toUpperCase(),
        signal: decision.action === 'buy' ? 1 : decision.action === 'sell' ? -1 : 0,
        probability: decision.confidence,
        confidence: decision.confidence,
        suggested_position_pct: decision.confidence * 100,
        model_version: 'v1',
        model_type: 'ml',
        symbol: 'XAUUSD',
        quantity: 0.1,
      };
      const result = await fetchMLExecute(executePayload);
      setExecuteResult(result);
      setSuccess(result.executed ? '交易執行成功' : '交易未執行');
    } catch (e) {
      handleError(e, '交易執行失敗');
    } finally {
      setLoading(false);
    }
  };

  const formatJson = (obj: any) => JSON.stringify(obj, null, 2);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">ML 運維面板</h1>
        <div className="flex gap-2">
          <button onClick={loadHistory} disabled={loading} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-white">
            重新載入數據
          </button>
        </div>
      </div>

      {loading && <div className="text-blue-400 text-sm">處理中...</div>}
      {error && <div className="bg-red-900/30 text-red-400 p-3 rounded">⚠️ {error}</div>}
      {success && <div className="bg-green-900/30 text-green-400 p-3 rounded">✅ {success}</div>}

      {/* 監控區塊 */}
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-white">模型監控</h2>
          <button onClick={handleMonitor} disabled={loading || !historyPrices.length} className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded text-white text-sm">
            觸發監控快照
          </button>
        </div>
        {monitorData && (
          <div className="bg-slate-900 rounded p-3 text-sm text-green-400 font-mono max-h-64 overflow-auto">
            <pre>{formatJson(monitorData)}</pre>
          </div>
        )}
      </div>

      {/* 重訓區塊 */}
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-white">模型重訓</h2>
          <button onClick={handleRetrain} disabled={loading || !historyPrices.length} className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 rounded text-white text-sm">
            觸發手動重訓
          </button>
        </div>
        {retrainResult && (
          <div className={`bg-slate-900 rounded p-3 text-sm ${retrainResult.retrained ? 'text-green-400' : 'text-yellow-400'} font-mono`}>
            <pre>{formatJson(retrainResult)}</pre>
          </div>
        )}
      </div>

      {/* A/B 分流區塊 */}
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-white">A/B 分流測試</h2>
          <button onClick={handleABAssign} disabled={loading} className="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded text-white text-sm">
            觸發 A/B 分流
          </button>
        </div>
        {abResult && (
          <div className="bg-slate-900 rounded p-3 text-sm text-purple-400 font-mono">
            <pre>{formatJson(abResult)}</pre>
          </div>
        )}
      </div>

      {/* 交易執行區塊 */}
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-white">交易執行</h2>
          <button onClick={handleExecute} disabled={loading || !decision} className="px-4 py-2 bg-red-600 hover:bg-red-700 rounded text-white text-sm">
            執行交易
          </button>
        </div>
        {decision && (
          <div className="mb-3 p-3 bg-slate-900 rounded text-sm font-mono text-white">
            <strong>當前決策:</strong> {decision.action.toUpperCase()} | 信心度: {decision.confidence} | 價格: {decision.price}
          </div>
        )}
        {executeResult && (
          <div className={`bg-slate-900 rounded p-3 text-sm ${executeResult.success ? 'text-green-400' : 'text-red-400'} font-mono max-h-64 overflow-auto`}>
            <pre>{formatJson(executeResult)}</pre>
          </div>
        )}
      </div>
    </div>
  );
};

const formatJson = (obj: any) => JSON.stringify(obj, null, 2);

export default MLOperations;