/**
 * 圖表分析頁面 - 4 種時間框架 × 5 種技術指標
 * 參考 Chart.tsx 的 TradingView Lightweight Charts 整合方式
 */
import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  createChart,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  Time,
  HistogramData,
  LineData,
} from 'lightweight-charts';
import { fetchHistory, fetchCurrentPrice, type PriceResponse } from '@services/api';

type TimeFrame = '1H' | '4H' | '1D' | '1W';
type Indicator = 'MA' | 'EMA' | 'RSI' | 'MACD' | 'VOL';

interface ChartPoint {
  timestamp: string;
  sell: number;
  buy: number;
}

// ── 指標計算 ────────────────────────────────────────────────────────────────

const calcMA = (pts: ChartPoint[], period: number): LineData<Time>[] =>
  pts.map((_, i) => {
    if (i < period - 1) return null;
    const avg = pts.slice(i - period + 1, i + 1).reduce((s, p) => s + p.sell, 0) / period;
    return { time: Math.floor(new Date(pts[i].timestamp).getTime() / 1000) as Time, value: avg };
  }).filter(Boolean) as LineData<Time>[];

// EMA — 指數移動平均（使用 k = 2/(period+1)）
const calcEMA = (pts: ChartPoint[], period: number): LineData<Time>[] => {
  if (pts.length < period) return [];
  const k = 2 / (period + 1);
  const result: LineData<Time>[] = [];
  let ema = pts.slice(0, period).reduce((s, p) => s + p.sell, 0) / period;
  for (let i = period - 1; i < pts.length; i++) {
    if (i === period - 1) {
      result.push({ time: Math.floor(new Date(pts[i].timestamp).getTime() / 1000) as Time, value: ema });
    } else {
      ema = pts[i].sell * k + ema * (1 - k);
      result.push({ time: Math.floor(new Date(pts[i].timestamp).getTime() / 1000) as Time, value: ema });
    }
  }
  return result;
};

// RSI — 相對強弱指數（14日）
const calcRSI = (pts: ChartPoint[], period = 14): LineData<Time>[] => {
  if (pts.length < period + 1) return [];
  const result: LineData<Time>[] = [];
  let gains = 0, losses = 0;
  for (let i = 1; i <= period; i++) {
    const diff = pts[i].sell - pts[i - 1].sell;
    if (diff > 0) gains += diff; else losses += Math.abs(diff);
  }
  let avgGain = gains / period, avgLoss = losses / period;
  const toDb = (ag: number, al: number): number => {
    if (al === 0) return 100;
    const rs = ag / al;
    return 100 - 100 / (1 + rs);
  };
  result.push({ time: Math.floor(new Date(pts[period].timestamp).getTime() / 1000) as Time, value: toDb(avgGain, avgLoss) });
  for (let i = period + 1; i < pts.length; i++) {
    const diff = pts[i].sell - pts[i - 1].sell;
    avgGain = (avgGain * (period - 1) + (diff > 0 ? diff : 0)) / period;
    avgLoss = (avgLoss * (period - 1) + (diff < 0 ? Math.abs(diff) : 0)) / period;
    result.push({ time: Math.floor(new Date(pts[i].timestamp).getTime() / 1000) as Time, value: toDb(avgGain, avgLoss) });
  }
  return result;
};

// MACD – 12/26/9
const calcMACD = (pts: ChartPoint[], fast = 12, slow = 26, signal = 9) => {
  const emaFast = calcEMA(pts, fast);
  const emaSlow = calcEMA(pts, slow);
  if (emaFast.length === 0 || emaSlow.length === 0) return { macd: [], signal: [], histogram: [] };

  const offset = Number(emaSlow[0].time) - Number(emaFast[Math.max(0, emaFast.length - emaSlow.length)].time);
  const macdLine: LineData<Time>[] = emaFast.map((f) => {
    const match = emaSlow.find((s) => s.time === f.time);
    return match ? { time: f.time, value: f.value - match.value } : null;
  }).filter(Boolean) as LineData<Time>[];

  // Signal = EMA of MACD
  if (macdLine.length < signal) return { macd: macdLine, signal: [], histogram: [] };
  const k = 2 / (signal + 1);
  let emaVal = macdLine.slice(0, signal).reduce((s, m) => s + m.value, 0) / signal;
  const signalLine: LineData<Time>[] = [];
  for (let i = signal - 1; i < macdLine.length; i++) {
    if (i === signal - 1) {
      signalLine.push({ time: macdLine[i].time, value: emaVal });
    } else {
      emaVal = macdLine[i].value * k + emaVal * (1 - k);
      signalLine.push({ time: macdLine[i].time, value: emaVal });
    }
  }

  const histogram: HistogramData<Time>[] = macdLine.map((m) => {
    const s = signalLine.find((s) => s.time === m.time);
    return { time: m.time, value: m.value - (s?.value ?? 0), color: m.value - (s?.value ?? 0) >= 0 ? '#22c55e' : '#ef4444' };
  });

  return { macd: macdLine, signal: signalLine, histogram };
};

// 成交量柱
const calcVol = (pts: ChartPoint[]): HistogramData<Time>[] =>
  pts.map((p) => ({
    time: Math.floor(new Date(p.timestamp).getTime() / 1000) as Time,
    value: Math.abs(p.sell - p.buy),
    color: p.sell >= p.buy ? '#22c55e' : '#ef4444',
  }));

// ── 走勢摘要 ───────────────────────────────────────────────────────────────

const summarize = (pts: ChartPoint[]): string => {
  if (pts.length < 5) return '數據不足，無法分析';
  const recent = pts.slice(-5);
  const first = recent[0].sell, last = recent[recent.length - 1].sell;
  const change = last - first;
  const pct = ((change / first) * 100).toFixed(2);
  const trend = change >= 0 ? '上漲' : '下跌';
  const avg = recent.reduce((s, p) => s + p.sell, 0) / recent.length;
  const vsAvg = last >= avg ? '高於' : '低於';
  return `近${recent.length}筆走勢${trend} ${change >= 0 ? '+' : ''}${change.toFixed(1)}（${pct}%），最新價${vsAvg}均價`;
};

// ── RSI / MACD 面板 ────────────────────────────────────────────────────────

const IndicatorPanel: React.FC<{ pts: ChartPoint[] }> = ({ pts }) => {
  const rsi = calcRSI(pts);
  const macd = calcMACD(pts);
  const latestRSI = rsi[rsi.length - 1]?.value ?? null;
  const latestMACD = macd.macd[macd.macd.length - 1]?.value ?? null;
  const latestSignal = macd.signal[macd.signal.length - 1]?.value ?? null;

  const rsiLevel = latestRSI !== null ? (latestRSI > 70 ? '超買' : latestRSI < 30 ? '超賣' : '中性') : '--';
  const rsiColor = latestRSI !== null ? (latestRSI > 70 ? 'text-red-400' : latestRSI < 30 ? 'text-green-400' : 'text-gray-400') : 'text-gray-500';

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div className="bg-slate-800 rounded-lg p-3">
        <div className="text-gray-400 text-xs mb-1">RSI (14)</div>
        <div className={`text-xl font-bold ${rsiColor}`}>{latestRSI?.toFixed(1) ?? '--'}</div>
        <div className="text-xs text-gray-500 mt-1">狀態：{rsiLevel}</div>
      </div>
      <div className="bg-slate-800 rounded-lg p-3">
        <div className="text-gray-400 text-xs mb-1">MACD</div>
        <div className={`text-xl font-bold ${(latestMACD ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {latestMACD?.toFixed(2) ?? '--'}
        </div>
        <div className="text-xs text-gray-500 mt-1">快線</div>
      </div>
      <div className="bg-slate-800 rounded-lg p-3">
        <div className="text-gray-400 text-xs mb-1">Signal</div>
        <div className="text-xl font-bold text-yellow-400">
          {latestSignal?.toFixed(2) ?? '--'}
        </div>
        <div className="text-xs text-gray-500 mt-1">慢線</div>
      </div>
      <div className="bg-slate-800 rounded-lg p-3">
        <div className="text-gray-400 text-xs mb-1">走勢判斷</div>
        <div className={`text-sm font-semibold ${(latestMACD ?? 0) >= (latestSignal ?? 0) ? 'text-green-400' : 'text-red-400'}`}>
          {(latestMACD ?? 0) >= (latestSignal ?? 0) ? '▲ 金叉' : '▼ 死叉'}
        </div>
        <div className="text-xs text-gray-500 mt-1">{summarize(pts)}</div>
      </div>
    </div>
  );
};

// ── 主元件 ──────────────────────────────────────────────────────────────────

const ChartAnalysis: React.FC = () => {
  const [timeframe, setTimeframe] = useState<TimeFrame>('1D');
  const [activeIndicators, setActiveIndicators] = useState<Set<Indicator>>(new Set(['MA', 'EMA']));
  const [data, setData] = useState<ChartPoint[]>([]);
  const [price, setPrice] = useState<PriceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chartKey, setChartKey] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const daysMap: Record<TimeFrame, number> = { '1H': 2, '4H': 7, '1D': 30, '1W': 90 };
      const [histData, priceData] = await Promise.all([
        fetchHistory(daysMap[timeframe]),
        fetchCurrentPrice(),
      ]);
      setData(histData.data);
      setPrice(priceData);
      setChartKey((k) => k + 1);
    } catch (e: any) {
      setError(e?.message ?? '載入失敗');
    } finally {
      setLoading(false);
    }
  }, [timeframe]);

  useEffect(() => { load(); }, [load]);

  const toggleIndicator = (ind: Indicator) => {
    setActiveIndicators((prev) => {
      const next = new Set(prev);
      if (next.has(ind)) next.delete(ind);
      else next.add(ind);
      return next;
    });
    setChartKey((k) => k + 1);
  };

  const indBtn = (ind: Indicator, label: string) => {
    const active = activeIndicators.has(ind);
    return (
      <button
        key={ind}
        onClick={() => toggleIndicator(ind)}
        className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
          active ? 'bg-yellow-600 text-white' : 'bg-slate-700 text-gray-400 hover:bg-slate-600'
        }`}
      >
        {label}
      </button>
    );
  };

  const tfBtn = (tf: TimeFrame) => (
    <button
      key={tf}
      onClick={() => setTimeframe(tf)}
      className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
        timeframe === tf ? 'bg-yellow-600 text-white' : 'bg-slate-700 text-gray-400 hover:bg-slate-600'
      }`}
    >
      {tf}
    </button>
  );

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-white">📈 技術分析</h2>
          <p className="text-gray-400 text-sm mt-0.5">
            K線圖 · 5 種技術指標 · {timeframe} 框架
          </p>
        </div>
        <div className="flex flex-col gap-2 items-end">
          <div className="flex gap-1">{(['1H', '4H', '1D', '1W'] as TimeFrame[]).map(tfBtn)}</div>
          <div className="flex gap-1 flex-wrap justify-end">
            {indBtn('MA', 'MA')}
            {indBtn('EMA', 'EMA')}
            {indBtn('RSI', 'RSI')}
            {indBtn('MACD', 'MACD')}
            {indBtn('VOL', 'VOL')}
          </div>
        </div>
      </div>

      {/* 報價卡片 */}
      {price && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-slate-800 rounded-lg p-3">
            <div className="text-gray-400 text-xs">台灣銀行賣出</div>
            <div className="text-xl font-bold text-white">${price.sell.toLocaleString()}</div>
          </div>
          <div className="bg-slate-800 rounded-lg p-3">
            <div className="text-gray-400 text-xs">台灣銀行買進</div>
            <div className="text-xl font-bold text-white">${price.buy.toLocaleString()}</div>
          </div>
          <div className="bg-slate-800 rounded-lg p-3">
            <div className="text-gray-400 text-xs">日內變動</div>
            <div className={`text-xl font-bold ${price.change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {price.change >= 0 ? '+' : ''}{price.change.toFixed(1)}
            </div>
          </div>
          <div className="bg-slate-800 rounded-lg p-3">
            <div className="text-gray-400 text-xs">變動幅度</div>
            <div className={`text-xl font-bold ${price.change_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {price.change_pct >= 0 ? '+' : ''}{price.change_pct.toFixed(2)}%
            </div>
          </div>
        </div>
      )}

      {/* RSI / MACD 面板 */}
      {!loading && !error && <IndicatorPanel pts={data} />}

      {/* Loading / Error */}
      {loading && (
        <div className="flex items-center justify-center h-[420px]">
          <span className="text-gray-400 animate-pulse text-sm">載入圖表中...</span>
        </div>
      )}
      {error && (
        <div className="flex items-center justify-center h-[420px]">
          <div className="bg-red-900/30 text-red-400 p-4 rounded-lg text-sm">⚠️ {error}</div>
        </div>
      )}

      {/* 圖表 */}
      {!loading && !error && (
        <ChartInner
          key={chartKey}
          containerRef={containerRef}
          chartRef={chartRef}
          data={data}
          activeIndicators={activeIndicators}
        />
      )}

      {/* 圖例 */}
      {!loading && !error && (
        <div className="flex flex-wrap gap-3 text-xs">
          {activeIndicators.has('MA') && <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-yellow-500 inline-block" />MA(20)</span>}
          {activeIndicators.has('EMA') && <span className="flex items-center gap-1"><span className="w-4 h-0.5 bg-purple-500 inline-block" />EMA(20)</span>}
          {activeIndicators.has('VOL') && <span className="flex items-center gap-1"><span className="w-3 h-3 bg-green-500 inline-block" />成交量</span>}
          <span className="flex items-center gap-1"><span className="w-3 h-3 bg-green-500 inline-block" />K線(漲)</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 bg-red-500 inline-block" />K線(跌)</span>
        </div>
      )}
    </div>
  );
};

// ── 圖表渲染內層（靠 key 重 mount） ──────────────────────────────────────────

interface ChartInnerProps {
  containerRef: React.RefObject<HTMLDivElement>;
  chartRef: React.MutableRefObject<IChartApi | null>;
  data: ChartPoint[];
  activeIndicators: Set<Indicator>;
}

const ChartInner: React.FC<ChartInnerProps> = ({ containerRef, chartRef, data, activeIndicators }) => {
  const volRef = useRef<ISeriesApi<'Histogram'> | null>(null);
  const maRef = useRef<ISeriesApi<'Line'> | null>(null);
  const emaRef = useRef<ISeriesApi<'Line'> | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // 等待容器佈局
    let retries = 10;
    const tryDraw = () => {
      if (chartRef.current) { chartRef.current.remove(); chartRef.current = null; }
      if (el.clientWidth === 0 && retries > 0) { retries--; setTimeout(tryDraw, 50); return; }

      const chart = createChart(el, {
        width: el.clientWidth || el.offsetWidth,
        height: 400,
        layout: { background: { color: '#1e293b' }, textColor: '#9ca3af' },
        grid: { vertLines: { color: '#334155' }, horzLines: { color: '#334155' } },
        crosshair: { mode: 1, vertLine: { color: '#f59e0b', width: 1, style: 2, labelBackgroundColor: '#f59e0b' }, horzLine: { color: '#f59e0b', width: 1, style: 2 } },
        rightPriceScale: { borderColor: '#334155' },
        timeScale: { borderColor: '#334155', timeVisible: true, secondsVisible: false },
      });

      const candleSeries = chart.addCandlestickSeries({
        upColor: '#22c55e', downColor: '#ef4444',
        borderUpColor: '#22c55e', borderDownColor: '#ef4444',
        wickUpColor: '#22c55e', wickDownColor: '#ef4444',
      });

      candleSeries.setData(data.map((d) => ({
        time: Math.floor(new Date(d.timestamp).getTime() / 1000) as Time,
        open: d.sell, high: Math.max(d.sell, d.buy),
        low: Math.min(d.sell, d.buy), close: d.buy,
      })));

      if (activeIndicators.has('MA')) {
        const ma = chart.addLineSeries({ color: '#f59e0b', lineWidth: 1, title: 'MA' });
        ma.setData(calcMA(data, 20));
        maRef.current = ma;
      }
      if (activeIndicators.has('EMA')) {
        const ema = chart.addLineSeries({ color: '#a855f7', lineWidth: 1, title: 'EMA' });
        ema.setData(calcEMA(data, 20));
        emaRef.current = ema;
      }
      if (activeIndicators.has('VOL')) {
        const vol = chart.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: '' });
        vol.priceScale().applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
        vol.setData(calcVol(data));
        volRef.current = vol;
      }

      chart.timeScale().fitContent();
      chartRef.current = chart;

      const handleResize = () => {
        if (chartRef.current && containerRef.current) {
          chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
        }
      };
      window.addEventListener('resize', handleResize);
      return () => { window.removeEventListener('resize', handleResize); chart.remove(); };
    };

    tryDraw();
  }, [data, activeIndicators]);

  return (
    <div
      ref={containerRef}
      className="bg-slate-800 rounded-lg overflow-hidden"
      style={{ height: activeIndicators.has('VOL') ? 480 : 420 }}
    />
  );
};

export default ChartAnalysis;
