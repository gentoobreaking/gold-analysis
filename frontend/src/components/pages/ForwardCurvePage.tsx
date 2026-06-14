/**
 * 遠期曲線頁（Forward Curve）
 * 參照 TradingView Forward Curve 頁面
 * 展示黃金期貨各月合約價格結構與溢價分析
 */
import React, { useEffect, useRef, useState } from 'react';
import { createChart, IChartApi, LineData, Time } from 'lightweight-charts';
import { api } from '@services/api';

// ── Types ─────────────────────────────────────────────────────────────────────

interface ContractPoint {
  symbol: string;
  contract_month: string;
  maturity_date: string;
  price: number;
  premium: number;
  premium_label: string;
}

interface ForwardCurveResponse {
  spot_price: number;
  fetched_at: string;
  contracts: ContractPoint[];
  summary: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/** 把 202506 → 顯示標籤 "2025/06" 或 "Jun 25" */
const monthLabel = (ym: string) => {
  const [y, m] = [ym.slice(0, 4), ym.slice(4, 6)];
  const d = new Date(parseInt(y), parseInt(m) - 1, 1);
  return d.toLocaleString('en-US', { month: 'short', year: '2-digit' }); // "Jun 25"
};

const maturityLabel = (dateStr: string) => {
  try {
    const [y, m, d] = dateStr.split('/');
    return `${y.slice(2)}/${m}/${d}`;
  } catch { return dateStr; }
};

// ── Curve Chart ───────────────────────────────────────────────────────────────

const CurveChart: React.FC<{ contracts: ContractPoint[] }> = ({ contracts }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || contracts.length === 0) return;

    if (chartRef.current) { chartRef.current.remove(); chartRef.current = null; }

    const chart = createChart(el, {
      width: el.clientWidth || el.offsetWidth,
      height: 340,
      layout: {
        background: { color: '#1e293b' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: '#334155' },
        horzLines: { color: '#334155' },
      },
      rightPriceScale: {
        borderColor: '#334155',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: '#334155',
        visible: true,
        tickMarkFormatter: (time: number) => {
          const idx = Math.round(time);
          if (idx >= 0 && idx < contracts.length) {
            return monthLabel(contracts[idx].contract_month);
          }
          return '';
        },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: '#f59e0b', width: 1, style: 2, labelBackgroundColor: '#f59e0b' },
        horzLine: { color: '#f59e0b', width: 1, style: 2 },
      },
    });

    // 曲線線
    const series = chart.addLineSeries({
      color: '#f59e0b',
      lineWidth: 2,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 5,
      crosshairMarkerBorderColor: '#f59e0b',
      title: 'TGF1',
    });

    const lineData: LineData<Time>[] = contracts.map((c, i) => ({
      time: i as Time,
      value: c.price,
    }));
    series.setData(lineData);
    chart.timeScale().fitContent();

    // 垂直標記由 Y 軸顯示，無需額外 priceLine

    chartRef.current = chart;
    const handleResize = () => {
      if (chartRef.current && containerRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [contracts]);

  return (
    <div
      ref={containerRef}
      className="rounded-xl overflow-hidden bg-slate-800"
      style={{ height: 360 }}
    />
  );
};

// ── Premium Bar Chart (CSS-based) ─────────────────────────────────────────────

const PremiumBars: React.FC<{ contracts: ContractPoint[]; maxPremium: number }> = ({
  contracts,
  maxPremium,
}) => {
  return (
    <div className="space-y-2">
      {contracts.map((c, i) => {
        const barWidth = maxPremium > 0 ? (Math.abs(c.premium) / maxPremium) * 100 : 0;
        const isPositive = c.premium >= 0;
        return (
          <div key={i} className="flex items-center gap-3">
            <div className="w-14 text-xs text-gray-400 text-right">{monthLabel(c.contract_month)}</div>
            <div className="flex-1 relative h-6 bg-slate-900 rounded overflow-hidden">
              <div
                className={`absolute top-0 h-full rounded transition-all duration-500 ${
                  isPositive ? 'bg-blue-500/70' : 'bg-red-500/70'
                }`}
                style={{ width: `${barWidth}%` }}
              />
              <div className="absolute inset-0 flex items-center justify-center">
                <span className={`text-xs font-mono font-medium ${
                  isPositive ? 'text-blue-200' : 'text-red-200'
                }`}>
                  {isPositive ? '+' : ''}{c.premium.toFixed(2)}%
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ── Contract Table ────────────────────────────────────────────────────────────

const ContractTable: React.FC<{ contracts: ContractPoint[]; spotPrice: number }> = ({
  contracts,
  spotPrice,
}) => {
  const maxDiff = Math.max(...contracts.map(c => Math.abs(c.price - spotPrice)));

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-400 border-b border-slate-700 text-xs uppercase tracking-wider">
              <th className="text-left py-3 px-4">合約月</th>
              <th className="text-right py-3 px-4">到期日</th>
              <th className="text-right py-3 px-4">結算價</th>
              <th className="text-right py-3 px-4">溢價</th>
              <th className="text-center py-3 px-4">結構</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700">
            {contracts.map((c, i) => {
              const diff = c.price - spotPrice;
              const isNear = i === 0;
              return (
                <tr
                  key={i}
                  className={`text-white ${isNear ? 'bg-slate-700/40' : ''} hover:bg-slate-700/30 transition-colors`}
                >
                  <td className="py-3 px-4 font-medium">
                    {monthLabel(c.contract_month)}
                    {isNear && <span className="ml-2 text-xs text-yellow-400">近月</span>}
                  </td>
                  <td className="py-3 px-4 text-right text-gray-400">{maturityLabel(c.maturity_date)}</td>
                  <td className="py-3 px-4 text-right font-mono font-bold">
                    {c.price.toLocaleString('zh-TW', { minimumFractionDigits: 2 })}
                  </td>
                  <td className={`py-3 px-4 text-right font-mono ${
                    diff > 0 ? 'text-blue-400' : diff < 0 ? 'text-red-400' : 'text-gray-400'
                  }`}>
                    {diff >= 0 ? '+' : ''}{diff.toFixed(2)}
                  </td>
                  <td className="py-3 px-4 text-center">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      c.premium_label === '正價差'
                        ? 'bg-blue-900 text-blue-300'
                        : c.premium_label === '負價差'
                        ? 'bg-red-900 text-red-300'
                        : 'bg-gray-700 text-gray-300'
                    }`}>
                      {c.premium_label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// ── Summary Card ───────────────────────────────────────────────────────────────

const SummaryCard: React.FC<{ summary: string; spotPrice: number; fetchedAt: string }> = ({
  summary,
  spotPrice,
  fetchedAt,
}) => (
  <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
    <div className="text-xs text-gray-400 uppercase tracking-wider mb-2">市場結構分析</div>
    <div className="text-white font-medium leading-relaxed mb-3">{summary}</div>
    <div className="flex items-center gap-4 text-xs text-gray-500">
      <span>現貨參考價：<span className="text-white font-mono">{spotPrice.toLocaleString('zh-TW', { minimumFractionDigits: 2 })}</span></span>
      <span>更新：{fetchedAt}</span>
    </div>
  </div>
);

// ── Main Page ─────────────────────────────────────────────────────────────────

const ForwardCurvePage: React.FC = () => {
  const [data, setData] = useState<ForwardCurveResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get<ForwardCurveResponse>('/api/forward-curve');
      setData(resp.data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '載入失敗');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const loadingEl = (
    <div className="flex items-center justify-center py-24">
      <div className="w-8 h-8 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">遠期曲線</h1>
          <p className="text-sm text-gray-400 mt-0.5">期貨合約月份結構 · Contango / Backwardation</p>
        </div>
        <button
          onClick={load}
          className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-white transition-colors"
        >
          🔄 重新整理
        </button>
      </div>

      {/* ⚠️ Mock data notice */}
      {data && (
        <div className="bg-yellow-900/20 border border-yellow-700/50 rounded-xl px-4 py-3 text-xs text-yellow-300">
          ⚠️ 目前顯示模擬資料（無法從台灣期交所直接取得黃金期貨多合約報價）。
          真實黃金期貨遠期曲線需透過期貨商 API（如元大期貨、群益期貨）或路透數據取得。
        </div>
      )}

      {loading && loadingEl}
      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-xl p-4 text-red-300 text-sm">
          ⚠️ {error}
        </div>
      )}

      {data && (
        <>
          <SummaryCard
            summary={data.summary}
            spotPrice={data.spot_price}
            fetchedAt={data.fetched_at}
          />

          {/* 曲線圖 */}
          <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-medium text-white">TGF1 遠期曲線</div>
              <div className="text-xs text-gray-500">
                {data.contracts.length} 個合約月份
              </div>
            </div>
            <CurveChart contracts={data.contracts} />
          </div>

          {/* 溢價柱圖 + 合約表 */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Premium bars */}
            <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
              <div className="text-sm font-medium text-white mb-4">各合約溢價（相對近月）</div>
              <PremiumBars
                contracts={data.contracts}
                maxPremium={Math.max(...data.contracts.map(c => Math.abs(c.premium)))}
              />
            </div>

            {/* Contract details */}
            <div className="lg:col-span-2">
              <ContractTable contracts={data.contracts} spotPrice={data.spot_price} />
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ForwardCurvePage;
