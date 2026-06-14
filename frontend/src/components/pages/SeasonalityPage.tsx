/**
 * 季節性頁（Seasonality）
 * 展示黃金月均表現、熱力圖、強度評級
 * 數據來源：CME/WGC/Kitco 多年研究平均值 + 本地歷史資料對照
 */
import React, { useEffect, useRef, useState } from 'react';
import { createChart, IChartApi, HistogramData, Time } from 'lightweight-charts';

interface MonthlyStat {
  month: number;
  month_label: string;
  avg_return_pct: number;
  avg_price: number | null;
  data_count: number;
  reference_return: number;
  reference_label: string;
  confidence: string;
  strength: string;
}

interface SeasonalityData {
  monthly_stats: MonthlyStat[];
  current_month: number;
  current_month_label: string;
  current_season: string;
  best_month: number;
  worst_month: number;
  data_note: string;
  fetched_at: string;
}

const STRENGTH_COLORS: Record<string, string> = {
  strong_buy: '#22c55e',
  buy:         '#86efac',
  neutral:     '#94a3b8',
  sell:        '#fdba74',
  strong_sell: '#ef4444',
};

const STRENGTH_LABELS: Record<string, string> = {
  strong_buy:  '🟢 強力買入',
  buy:         '🟢 買入',
  neutral:     '⚪ 中性',
  sell:        '🔴 賣出',
  strong_sell: '🔴 強力賣出',
};

// ── Return Bar Chart ─────────────────────────────────────────────────────────

const ReturnBarChart: React.FC<{ stats: MonthlyStat[]; currentMonth: number }> = ({
  stats,
  currentMonth,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    if (chartRef.current) { chartRef.current.remove(); chartRef.current = null; }

    const chart = createChart(el, {
      width: el.clientWidth || 700,
      height: 220,
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
      },
      timeScale: { borderColor: '#334155', visible: false },
      crosshair: {
        vertLine: { color: '#f59e0b', width: 1, style: 2 },
        horzLine: { color: '#f59e0b', width: 1, style: 2 },
      },
    });

    const series = chart.addHistogramSeries({
    });

    const colorFn = (bar: HistogramData<Time>) => {
      const v = bar.value;
      if (v >= 1.5) return '#22c55e';
      if (v >= 0.5) return '#4ade80';
      if (v >= -0.2) return '#94a3b8';
      if (v >= -0.4) return '#fb923c';
      return '#ef4444';
    };

    const barData: HistogramData<Time>[] = stats.map((s, i) => ({
      time: i as Time,
      value: s.avg_return_pct,
      color: colorFn({ time: i as Time, value: s.avg_return_pct } as HistogramData<Time>),
    }));
    series.setData(barData);
    chart.timeScale().fitContent();

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
  }, [stats]);

  return (
    <div
      ref={containerRef}
      className="rounded-xl overflow-hidden bg-slate-800"
      style={{ height: 240 }}
    />
  );
};

// ── Seasonal Heatmap ─────────────────────────────────────────────────────────

const SeasonalHeatmap: React.FC<{ stats: MonthlyStat[]; currentMonth: number; bestMonth: number; worstMonth: number }> = ({
  stats,
  currentMonth,
  bestMonth,
  worstMonth,
}) => (
  <div className="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-12 gap-1.5">
    {stats.map((s) => {
      const isCurrent = s.month === currentMonth;
      const isBest = s.month === bestMonth;
      const isWorst = s.month === worstMonth;
      const bg = isBest ? '#22c55e' : isWorst ? '#ef4444' : isCurrent ? '#f59e0b' : '#334155';
      const alpha = Math.min(Math.abs(s.avg_return_pct) / 2.5, 1);
      const fallback = isBest ? '#22c55e' : isWorst ? '#ef4444' : isCurrent ? '#f59e0b' : '#94a3b8';
      return (
        <div
          key={s.month}
          className="rounded-lg p-2 text-center cursor-default transition-all hover:scale-105"
          style={{
            background: isBest || isWorst
              ? (isBest ? `rgba(34,197,94,${0.2 + alpha * 0.6})` : `rgba(239,68,68,${0.2 + alpha * 0.6})`)
              : isCurrent
              ? `rgba(245,158,11,0.3)`
              : `rgba(148,163,184,${0.05 + alpha * 0.15})`,
            border: isCurrent ? '2px solid #f59e0b' : isBest ? '2px solid #22c55e' : isWorst ? '2px solid #ef4444' : '1px solid #334155',
          }}
        >
          <div className="text-xs text-gray-400 font-medium">{s.month_label}</div>
          <div className={`text-sm font-bold mt-0.5 ${isBest ? 'text-green-400' : isWorst ? 'text-red-400' : 'text-white'}`}>
            {s.avg_return_pct > 0 ? '+' : ''}{s.avg_return_pct}%
          </div>
          <div className={`text-xs mt-0.5 ${isBest ? 'text-green-300' : isWorst ? 'text-red-300' : 'text-gray-500'}`}>
            {s.confidence === 'high' ? '★' : s.confidence === 'medium' ? '☆' : '·'}
          </div>
        </div>
      );
    })}
  </div>
);

// ── Monthly Cards ─────────────────────────────────────────────────────────────

const MonthlyCard: React.FC<{ stat: MonthlyStat; isCurrent: boolean }> = ({ stat, isCurrent }) => (
  <div
    className="bg-slate-800 rounded-xl p-4 border transition-all hover:border-slate-600"
    style={{
      borderColor: isCurrent ? '#f59e0b' : STRENGTH_COLORS[stat.strength] + '40',
    }}
  >
    <div className="flex items-center justify-between mb-2">
      <div className="text-sm font-bold text-white">
        {stat.month_label}
        {isCurrent && <span className="ml-2 text-xs text-yellow-400">當月</span>}
      </div>
      <div
        className="text-xs px-2 py-0.5 rounded-full"
        style={{
          background: STRENGTH_COLORS[stat.strength] + '30',
          color: STRENGTH_COLORS[stat.strength],
        }}
      >
        {STRENGTH_LABELS[stat.strength]}
      </div>
    </div>

    <div className="flex items-baseline gap-1 mb-1">
      <span className={`text-2xl font-mono font-bold ${stat.avg_return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
        {stat.avg_return_pct > 0 ? '+' : ''}{stat.avg_return_pct}%
      </span>
      <span className="text-xs text-gray-500">月均漲跌</span>
    </div>

    <div className="space-y-0.5 mt-2">
      <div className="text-xs text-gray-400">{stat.reference_label}</div>
      {stat.data_count > 0 && (
        <div className="text-xs text-gray-600">本地資料：{stat.data_count} 天</div>
      )}
    </div>
  </div>
);

// ── Season Summary ────────────────────────────────────────────────────────────

const SEASON_MONTHS = {
  'Q1(春)': [1, 2, 3],
  'Q2(夏)': [4, 5, 6],
  'Q3(秋)': [7, 8, 9],
  'Q4(冬)': [10, 11, 12],
};

const SeasonSummary: React.FC<{ stats: MonthlyStat[]; currentSeason: string }> = ({
  stats,
  currentSeason,
}) => {
  const monthMap = Object.fromEntries(stats.map(s => [s.month, s]));

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {Object.entries(SEASON_MONTHS).map(([season, months]) => {
        const returns = months.map(m => monthMap[m]?.reference_return ?? 0);
        const avgReturn = returns.reduce((a, b) => a + b, 0) / 3;
        const isCurrent = season === currentSeason;
        return (
          <div
            key={season}
            className="bg-slate-800 rounded-xl p-4 border"
            style={{
              borderColor: isCurrent ? '#f59e0b' : '#334155',
              boxShadow: isCurrent ? '0 0 12px rgba(245,158,11,0.15)' : 'none',
            }}
          >
            <div className="text-xs text-gray-400 mb-1">{season}</div>
            <div className={`text-xl font-mono font-bold ${avgReturn >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {avgReturn >= 0 ? '+' : ''}{avgReturn.toFixed(2)}%
            </div>
            <div className="text-xs text-gray-500 mt-1">季度平均漲跌</div>
            {isCurrent && <div className="text-xs text-yellow-400 mt-1">⬤ 目前季節</div>}
          </div>
        );
      })}
    </div>
  );
};

// ── Main Page ─────────────────────────────────────────────────────────────────

const SeasonalityPage: React.FC = () => {
  const [data, setData] = useState<SeasonalityData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch('/api/seasonality');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setData(await resp.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '載入失敗');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">季節性分析</h1>
          <p className="text-sm text-gray-400 mt-0.5">黃金月均表現 · 多年季節性規律參考</p>
        </div>
        <button
          onClick={load}
          className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-white transition-colors"
        >
          🔄 重新整理
        </button>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-24">
          <div className="w-8 h-8 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-xl p-4 text-red-300 text-sm">
          ⚠️ {error}
        </div>
      )}

      {data && (
        <>
          {/* Data quality notice */}
          <div className="bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-xs text-yellow-300">
            {data.data_note}
          </div>

          {/* Season summary */}
          <div>
            <div className="text-sm font-medium text-white mb-3">📅 季度表現（{data.current_season}）</div>
            <SeasonSummary stats={data.monthly_stats} currentSeason={data.current_season} />
          </div>

          {/* Monthly heatmap */}
          <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-medium text-white">🗓️ 月度熱力圖</div>
              <div className="flex items-center gap-3 text-xs text-gray-400">
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded bg-green-500 inline-block" />
                  強力買入(★)
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded bg-red-500 inline-block" />
                  強力賣出(★)
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded bg-yellow-500 inline-block border-2 border-yellow-400" />
                  當月
                </span>
              </div>
            </div>
            <SeasonalHeatmap
              stats={data.monthly_stats}
              currentMonth={data.current_month}
              bestMonth={data.best_month}
              worstMonth={data.worst_month}
            />
          </div>

          {/* Bar chart */}
          <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="text-sm font-medium text-white mb-3">📊 月均漲跌幅（%）</div>
            <ReturnBarChart stats={data.monthly_stats} currentMonth={data.current_month} />
          </div>

          {/* Monthly cards grid */}
          <div>
            <div className="text-sm font-medium text-white mb-3">📋 各月詳細數據</div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
              {data.monthly_stats.map((s) => (
                <MonthlyCard
                  key={s.month}
                  stat={s}
                  isCurrent={s.month === data.current_month}
                />
              ))}
            </div>
          </div>

          {/* Legend */}
          <div className="text-xs text-gray-500 space-y-1">
            <div>★ 高置信度（CME/WGC/Kitco 多年數據驗證）</div>
            <div>☆ 中置信度（部分年份符合）</div>
            <div>· 低置信度（季節性趨勢不明顯）</div>
            <div className="text-gray-600 mt-2">
              ⚠️ 黃金季節性為多年平均趨勢，非精確預測。單月走勢受宏觀經濟、地緣政治等多因素影響。
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default SeasonalityPage;
