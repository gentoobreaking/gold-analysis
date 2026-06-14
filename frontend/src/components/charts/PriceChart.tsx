/**
 * 黃金價格圖表組件 - TradingView Lightweight Charts
 */
import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData } from 'lightweight-charts';

interface PriceChartProps {
  data: CandlestickData[];
  width?: number;
  height?: number;
}

export const PriceChart: React.FC<PriceChartProps> = ({ 
  data, 
  width = 800, 
  height = 400 
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // 創建圖表
    const chart = createChart(chartContainerRef.current, {
      width,
      height,
      layout: {
        background: { color: '#1e293b' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: '#374151' },
        horzLines: { color: '#374151' },
      },
      crosshair: {
        mode: 1,
        vertLine: {
          color: '#f59e0b',
          width: 1,
          style: 2,
        },
        horzLine: {
          color: '#f59e0b',
          width: 1,
          style: 2,
        },
      },
      rightPriceScale: {
        borderColor: '#374151',
      },
      timeScale: {
        borderColor: '#374151',
        timeVisible: true,
      },
    });

    // 創建K線系列
    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });

    // 設置數據
    candlestickSeries.setData(data);

    // 自適應時間軸
    chart.timeScale().fitContent();

    chartRef.current = chart;
    seriesRef.current = candlestickSeries;

    // 清理
    return () => {
      chart.remove();
    };
  }, [width, height]);

  // 更新數據
  useEffect(() => {
    if (seriesRef.current && data.length > 0) {
      seriesRef.current.setData(data);
    }
  }, [data]);

  return (
    <div className="rounded-lg overflow-hidden bg-slate-800">
      <div className="p-4 border-b border-gray-700">
        <h3 className="text-lg font-semibold text-white">黃金價格（NT/克）</h3>
      </div>
      <div ref={chartContainerRef} className="w-full" />
    </div>
  );
};
