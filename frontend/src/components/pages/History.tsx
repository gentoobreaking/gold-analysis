/**
 * History 頁面 - 完整歷史報價記錄
 */
import React, { useEffect, useState } from 'react';
import { fetchHistory, fetchCurrentPrice } from '@services/api';

interface HistoryRow {
  timestamp: string;
  sell: number;
  buy: number;
}

const History: React.FC = () => {
  const [rows, setRows] = useState<HistoryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string |null>(null);
  const [days, setDays] = useState(7);
  const [currentPage, setCurrentPage] = useState(1);
  const [price, setPrice] = useState<{ sell: number; buy: number } | null>(null);
  const pageSize = 20;

  const load = async () => {
    setLoading(true);
    setError(null);
    setCurrentPage(1);
    try {
      const [histData, priceData] = await Promise.all([
        fetchHistory(days),
        fetchCurrentPrice(),
      ]);
      setRows(histData.data);
      setPrice({ sell: priceData.sell, buy: priceData.buy });
    } catch (e: any) {
      setError(e?.message ?? '載入失敗');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [days]);

  const totalPages = Math.ceil(rows.length / pageSize);
  const pageRows = rows.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  // Stats
  const sells = rows.map(r => r.sell);
  const maxSell = sells.length > 0 ? Math.max(...sells) : 0;
  const minSell = sells.length > 0 ? Math.min(...sells) : 0;
  const avgSell = sells.length > 0 ? sells.reduce((s, v) => s + v, 0) / sells.length : 0;
  const change = price ? sells.length > 0 ? price.sell - sells[sells.length - 1] : 0 : 0;

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
    <div className="space-y-6 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">📜 歷史報價</h2>
          <p className="text-gray-400 text-sm">完整報價記錄 · {rows.length} 筆資料</p>
        </div>
        <div className="flex gap-2 items-center">
          <div className="flex gap-1 text-sm">
            {[3, 7, 14, 30].map((d) => (
              <button key={d} onClick={() => setDays(d)}
                className={`px-3 py-1 rounded ${days === d ? 'bg-yellow-600 text-white' : 'bg-slate-700 text-gray-400 hover:bg-slate-600'}`}>
                {d}天
              </button>
            ))}
          </div>
          <button onClick={load} className="px-3 py-1 bg-slate-700 hover:bg-slate-600 rounded text-sm">🔄</button>
        </div>
      </div>

      {/* Stats summary */}
      {price && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="bg-slate-800 rounded-lg p-3 text-center">
            <div className="text-gray-400 text-xs">最高</div>
            <div className="text-green-400 font-bold text-lg">${maxSell.toLocaleString()}</div>
          </div>
          <div className="bg-slate-800 rounded-lg p-3 text-center">
            <div className="text-gray-400 text-xs">最低</div>
            <div className="text-red-400 font-bold text-lg">${minSell.toLocaleString()}</div>
          </div>
          <div className="bg-slate-800 rounded-lg p-3 text-center">
            <div className="text-gray-400 text-xs">平均</div>
            <div className="text-blue-400 font-bold text-lg">${avgSell.toFixed(0)}</div>
          </div>
          <div className="bg-slate-800 rounded-lg p-3 text-center">
            <div className="text-gray-400 text-xs">區間變化</div>
            <div className={`font-bold text-lg ${change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {change >= 0 ? '+' : ''}{change.toFixed(1)}
            </div>
          </div>
          <div className="bg-slate-800 rounded-lg p-3 text-center">
            <div className="text-gray-400 text-xs">波動幅度</div>
            <div className="text-yellow-400 font-bold text-lg">
              {maxSell - minSell > 0 ? `$${(maxSell - minSell).toFixed(0)}` : '--'}
            </div>
          </div>
        </div>
      )}

      {loading && <div className="text-gray-400 text-center py-8 animate-pulse">載入歷史資料...</div>}
      {error && <div className="bg-red-900/30 text-red-400 p-3 rounded">⚠️ {error}</div>}

      {/* Table */}
      {!loading && !error && rows.length > 0 && (
        <div className="bg-slate-800 rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-700 text-gray-300">
                  <th className="text-left px-4 py-3">日期</th>
                  <th className="text-left px-4 py-3">時間</th>
                  <th className="text-right px-4 py-3">台灣銀行賣出</th>
                  <th className="text-right px-4 py-3">台灣銀行買進</th>
                  <th className="text-right px-4 py-3">買賣價差</th>
                  <th className="text-right px-4 py-3">相對均價</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((row, i) => {
                  const ts = formatTs(row.timestamp);
                  const spread = row.sell - row.buy;
                  const relAvg = avgSell > 0 ? ((row.sell - avgSell) / avgSell * 100) : 0;
                  return (
                    <tr key={i} className="border-t border-slate-700/50 hover:bg-slate-700/30">
                      <td className="px-4 py-2 text-gray-400">{ts.date}</td>
                      <td className="px-4 py-2 text-gray-400">{ts.time}</td>
                      <td className="px-4 py-2 text-right text-green-400 font-mono">{row.sell.toLocaleString()}</td>
                      <td className="px-4 py-2 text-right text-red-400 font-mono">{row.buy.toLocaleString()}</td>
                      <td className="px-4 py-2 text-right text-gray-400">{spread.toFixed(1)}</td>
                      <td className={`px-4 py-2 text-right font-mono ${relAvg > 0 ? 'text-green-400' : relAvg < 0 ? 'text-red-400' : 'text-gray-400'}`}>
                        {relAvg > 0 ? '+' : ''}{relAvg.toFixed(2)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700">
              <span className="text-gray-400 text-sm">
                第 {currentPage} / {totalPages} 頁，共 {rows.length} 筆記錄
              </span>
              <div className="flex gap-2">
                <button disabled={currentPage === 1} onClick={() => setCurrentPage(1)}
                  className="px-3 py-1 bg-slate-700 disabled:opacity-30 rounded text-sm">⏮</button>
                <button disabled={currentPage === 1} onClick={() => setCurrentPage(p => p - 1)}
                  className="px-3 py-1 bg-slate-700 disabled:opacity-30 rounded text-sm">◀</button>
                <span className="px-3 py-1 bg-slate-600 rounded text-sm text-white">{currentPage}</span>
                <button disabled={currentPage === totalPages} onClick={() => setCurrentPage(p => p + 1)}
                  className="px-3 py-1 bg-slate-700 disabled:opacity-30 rounded text-sm">▶</button>
                <button disabled={currentPage === totalPages} onClick={() => setCurrentPage(totalPages)}
                  className="px-3 py-1 bg-slate-700 disabled:opacity-30 rounded text-sm">⏭</button>
              </div>
            </div>
          )}
        </div>
      )}

      {rows.length === 0 && !loading && !error && (
        <div className="bg-slate-800 rounded-lg p-8 text-center text-gray-500">暫無歷史資料</div>
      )}
    </div>
  );
};

export default History;
