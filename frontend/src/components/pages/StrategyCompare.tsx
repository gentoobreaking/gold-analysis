import type React from 'react';
import { useEffect, useState, useCallback } from 'react';
import { fetchBacktestPrices, runBacktestCompare, type StrategyComparisonResponse } from '@services/api';

type StrategyRow = {
  final_equity: number;
  total_return: number;
  annualized_return: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  win_rate: number;
  n_trades: number;
};

const STRATEGY_LABELS: Record<string, string> = {
  ma_crossover: 'MA 交叉',
  rsi: 'RSI',
  macd: 'MACD',
  combined: '綜合(多數決)',
};

const METRIC_COLS: { key: keyof StrategyRow; label: string; pct?: boolean; fmt?: (v: number) => string }[] = [
  { key: 'total_return', label: '總報酬 %', pct: true },
  { key: 'annualized_return', label: '年化 %', pct: true },
  { key: 'sharpe_ratio', label: 'Sharpe' },
  { key: 'sortino_ratio', label: 'Sortino' },
  { key: 'max_drawdown', label: '最大回撤 %', pct: true },
  { key: 'win_rate', label: '勝率 %', pct: true },
  { key: 'n_trades', label: '交易數' },
];

const StrategyCompare: React.FC = () => {
  const [prices, setPrices] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<StrategyComparisonResponse | null>(null);

  const loadPrices = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchBacktestPrices('GOLD', 400);
      setPrices(data.prices);
    } catch (e: any) {
      setError(e?.message || '載入價格失敗');
      setPrices([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPrices();
  }, [loadPrices]);

  const runCompare = useCallback(async () => {
    if (prices.length < 30) {
      setError('價格資料不足，無法比較');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await runBacktestCompare(prices, ['ma_crossover', 'rsi', 'macd', 'combined']);
      setResult(data);
    } catch (e: any) {
      setError(e?.message || '回測比較失敗');
    } finally {
      setLoading(false);
    }
  }, [prices]);

  const rows = result ? (Object.entries(result.results) as [string, StrategyRow][]) : [];

  return (
    <div className="p-6 text-white">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">策略比較視圖</h1>
        <div className="flex gap-2">
          <button
            onClick={loadPrices}
            disabled={loading}
            className="px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-sm disabled:opacity-50"
          >
            重新載入價格
          </button>
          <button
            onClick={runCompare}
            disabled={loading || prices.length < 30}
            className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-sm disabled:opacity-50"
          >
            {loading ? '運算中…' : '執行比較'}
          </button>
        </div>
      </div>

      <p className="text-sm text-gray-400 mb-4">
        使用真實歷史收盤價（price_history），對 {prices.length} 筆資料並排比較多策略績效（向量化回測引擎 T063）。
      </p>

      {error && <div className="mb-4 px-3 py-2 rounded bg-red-900/50 text-red-300 text-sm">{error}</div>}

      {rows.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-slate-700">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-800 text-gray-300">
                <th className="text-left px-4 py-2">策略</th>
                {METRIC_COLS.map((c) => (
                  <th key={c.key} className="text-right px-4 py-2">{c.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(([name, row]) => (
                <tr key={name} className="border-t border-slate-700 hover:bg-slate-800/50">
                  <td className="px-4 py-2 font-medium">{STRATEGY_LABELS[name] || name}</td>
                  {METRIC_COLS.map((c) => {
                    const v = row[c.key] as number;
                    const color =
                      c.key === 'total_return' || c.key === 'sharpe_ratio'
                        ? v >= 0 ? 'text-green-400' : 'text-red-400'
                        : c.key === 'max_drawdown'
                        ? 'text-red-400'
                        : 'text-gray-200';
                    const text = c.pct ? `${v.toFixed(2)}%` : v.toFixed(2);
                    return (
                      <td key={c.key} className={`text-right px-4 py-2 ${color}`}>{text}</td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        !loading && (
          <div className="text-gray-500 text-sm">尚無比較結果。點擊「執行比較」以對多策略進行回測對比。</div>
        )
      )}
    </div>
  );
};

export default StrategyCompare;
