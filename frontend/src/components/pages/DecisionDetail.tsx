/**
 * 決策詳情頁 - 信號強度儀表、決策歷史表格
 * 與 Dashboard.tsx 決策卡片風格一致
 */
import React, { useEffect, useState, useCallback } from 'react';
import { fetchDecision, fetchHistory, type DecisionResponse } from '@services/api';

interface HistoryRow {
  timestamp: string;
  sell: number;
  buy: number;
  action: 'buy' | 'sell' | 'hold';
  confidence?: number;
  signal?: string;
}

// ── 信號強度儀表 ─────────────────────────────────────────────────────────────

const SignalGauge: React.FC<{ decision: DecisionResponse }> = ({ decision }) => {
  const pct = Math.round(decision.confidence * 100);
  const action = decision.action;

  const gaugeColor = action === 'buy' ? '#22c55e' : action === 'sell' ? '#ef4444' : '#f59e0b';
  const bgTrack = 'bg-slate-700';

  const labelText = action === 'buy' ? '買入信號' : action === 'sell' ? '賣出信號' : '持有觀望';
  const emoji = action === 'buy' ? '💰' : action === 'sell' ? '⚠️' : '➡️';
  const borderColor = action === 'buy' ? 'border-green-600' : action === 'sell' ? 'border-red-600' : 'border-yellow-600';

  return (
    <div className={`rounded-xl p-5 border ${borderColor} bg-slate-800`}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="text-xs text-gray-400 mb-1">信號強度</div>
          <div className="flex items-baseline gap-2">
            <span className="text-4xl">{emoji}</span>
            <span className="text-3xl font-bold text-white">{decision.signal}</span>
          </div>
          <div className="text-sm text-gray-400 mt-1">{labelText}</div>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold" style={{ color: gaugeColor }}>{pct}%</div>
          <div className="text-xs text-gray-500">信心度</div>
        </div>
      </div>

      {/* 信心度進度條 */}
      <div className={`h-2.5 rounded-full ${bgTrack} overflow-hidden`}>
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, backgroundColor: gaugeColor }}
        />
      </div>

      {/* 決策理由 */}
      <div className="mt-4 space-y-1.5">
        <div className="text-xs text-gray-500 font-medium">決策依據</div>
        {decision.reason.map((r, i) => (
          <div key={i} className="flex gap-2 text-sm text-gray-300">
            <span className="text-gray-500 mt-0.5">•</span>
            <span>{r}</span>
          </div>
        ))}
      </div>

      {/* 關聯價格 */}
      <div className="mt-4 pt-3 border-t border-slate-700 flex justify-between items-center">
        <div className="text-xs text-gray-500">參考價格</div>
        <div className="text-white font-semibold">${decision.price.toLocaleString()} NT/克</div>
      </div>
    </div>
  );
};

// ── 信號列表 ─────────────────────────────────────────────────────────────────

type SignalTab = 'buy' | 'sell' | 'hold';

const SignalList: React.FC<{ signals: HistoryRow[] }> = ({ signals }) => {
  const [tab, setTab] = useState<SignalTab>('buy');

  const filtered = signals.filter((s) => s.action === tab);

  const tabCls = (t: SignalTab) =>
    `px-4 py-1.5 rounded text-sm font-medium transition-colors ${
      tab === t ? (t === 'buy' ? 'bg-green-600 text-white' : t === 'sell' ? 'bg-red-600 text-white' : 'bg-yellow-600 text-white') : 'bg-slate-700 text-gray-400'
    }`;

  const actionColor = (a?: string) =>
    a === 'buy' ? 'text-green-400' : a === 'sell' ? 'text-red-400' : 'text-yellow-400';

  const formatTs = (ts: string) => {
    try {
      return new Date(ts).toLocaleString('zh-TW', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch { return ts; }
  };

  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-semibold">📋 信號列表</h3>
        <div className="flex gap-1">
          {(['buy', 'sell', 'hold'] as SignalTab[]).map((t) => (
            <button key={t} onClick={() => setTab(t)} className={tabCls(t)}>
              {tab === 'buy' ? '買入' : tab === 'sell' ? '賣出' : '持有'}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-8 text-gray-500 text-sm">暫無{tab === 'buy' ? '買入' : tab === 'sell' ? '賣出' : '持有'}信號</div>
      ) : (
        <div className="space-y-2">
          {filtered.map((s, i) => (
            <div key={i} className="flex items-center justify-between bg-slate-700/50 rounded-lg px-4 py-3">
              <div>
                <div className={`text-sm font-semibold ${actionColor(s.action)}`}>
                  {s.signal ?? (s.action === 'buy' ? '買入' : s.action === 'sell' ? '賣出' : '持有')}
                </div>
                <div className="text-xs text-gray-500 mt-0.5">{formatTs(s.timestamp)}</div>
              </div>
              <div className="text-right">
                <div className="text-white font-mono text-sm">${s.sell.toLocaleString()}</div>
                {s.confidence !== undefined && (
                  <div className="text-xs text-gray-500">{Math.round(s.confidence * 100)}%</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ── 決策歷史表格 ─────────────────────────────────────────────────────────────

const DecisionHistory: React.FC<{ history: HistoryRow[] }> = ({ history }) => {
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const totalPages = Math.ceil(history.length / pageSize);
  const pageRows = history.slice((page - 1) * pageSize, page * pageSize);

  const actionBadge = (a?: string) => {
    if (a === 'buy') return <span className="px-2 py-0.5 rounded-full bg-green-900/50 text-green-400 text-xs font-medium">買入</span>;
    if (a === 'sell') return <span className="px-2 py-0.5 rounded-full bg-red-900/50 text-red-400 text-xs font-medium">賣出</span>;
    if (a === 'hold') return <span className="px-2 py-0.5 rounded-full bg-yellow-900/50 text-yellow-400 text-xs font-medium">持有</span>;
    return <span className="text-gray-500 text-xs">--</span>;
  };

  const formatTs = (ts: string) => {
    try {
      const d = new Date(ts);
      return {
        date: d.toLocaleDateString('zh-TW', { year: 'numeric', month: '2-digit', day: '2-digit' }),
        time: d.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' }),
      };
    } catch { return { date: ts, time: '' }; }
  };

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      <div className="p-5 border-b border-slate-700">
        <h3 className="text-white font-semibold">📜 決策歷史</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-700 text-gray-400 text-xs">
              <th className="text-left px-4 py-3 font-medium">日期</th>
              <th className="text-left px-4 py-3 font-medium">時間</th>
              <th className="text-right px-4 py-3 font-medium">賣出</th>
              <th className="text-right px-4 py-3 font-medium">買進</th>
              <th className="text-center px-4 py-3 font-medium">信號</th>
              <th className="text-right px-4 py-3 font-medium">信心度</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row, i) => {
              const ts = formatTs(row.timestamp);
              return (
                <tr key={i} className="border-t border-slate-700/50 hover:bg-slate-700/30">
                  <td className="px-4 py-3 text-gray-400">{ts.date}</td>
                  <td className="px-4 py-3 text-gray-500">{ts.time}</td>
                  <td className="px-4 py-3 text-right text-green-400 font-mono">{row.sell.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right text-red-400 font-mono">{row.buy.toLocaleString()}</td>
                  <td className="px-4 py-3 text-center">{actionBadge(row.action)}</td>
                  <td className="px-4 py-3 text-right text-gray-400">
                    {row.confidence !== undefined ? `${Math.round(row.confidence * 100)}%` : '--'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700">
          <span className="text-gray-500 text-xs">
            第 {page} / {totalPages} 頁，共 {history.length} 筆記錄
          </span>
          <div className="flex gap-1">
            <button disabled={page === 1} onClick={() => setPage(1)} className="px-2 py-1 bg-slate-700 disabled:opacity-30 rounded text-xs">⏮</button>
            <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="px-2 py-1 bg-slate-700 disabled:opacity-30 rounded text-xs">◀</button>
            <span className="px-3 py-1 bg-slate-600 rounded text-xs text-white">{page}</span>
            <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)} className="px-2 py-1 bg-slate-700 disabled:opacity-30 rounded text-xs">▶</button>
            <button disabled={page === totalPages} onClick={() => setPage(totalPages)} className="px-2 py-1 bg-slate-700 disabled:opacity-30 rounded text-xs">⏭</button>
          </div>
        </div>
      )}
    </div>
  );
};

// ── 主元件 ──────────────────────────────────────────────────────────────────

const DecisionDetail: React.FC = () => {
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [decData, histData] = await Promise.all([
        fetchDecision(),
        fetchHistory(30),
      ]);
      setDecision(decData);

      // 將歷史報價附加模擬信號（實際對接時由 API 統一提供）
      const enriched: HistoryRow[] = histData.data.map((h, i) => {
        const pct = Math.random();
        const action = (pct > 0.6 ? 'buy' : pct > 0.3 ? 'hold' : 'sell') as HistoryRow['action'];
        return {
          ...h,
          action,
          confidence: 0.5 + Math.random() * 0.5,
          signal: action === 'buy' ? '短線買入' : action === 'sell' ? '短線賣出' : '觀望',
        };
      }).reverse();

      setHistory(enriched);
    } catch (e: any) {
      setError(e?.message ?? '載入失敗');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-6 p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">🎯 決策詳情</h2>
          <p className="text-gray-400 text-sm mt-0.5">信號分析 · 決策歷史 · 信心評估</p>
        </div>
        <button
          onClick={load}
          className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded text-sm transition-colors"
        >
          🔄 重新整理
        </button>
      </div>

      {loading && <div className="text-center py-16 text-gray-400 animate-pulse">載入中...</div>}
      {error && <div className="bg-red-900/30 text-red-400 p-4 rounded-lg text-sm">⚠️ {error}</div>}

      {!loading && !error && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 左側：信號儀表 */}
          <div className="lg:col-span-1">
            {decision && <SignalGauge decision={decision} />}
          </div>

          {/* 右側：信號列表 + 歷史表格 */}
          <div className="lg:col-span-2 space-y-6">
            <SignalList signals={history} />
            <DecisionHistory history={history} />
          </div>
        </div>
      )}
    </div>
  );
};

export default DecisionDetail;
