/**
 * 技術分析頁 - TradingView 技術分析風格
 * 展示 RSI / MACD / MA / Bollinger Bands 各項指標及買賣信號
 */
import React, { useEffect, useState } from 'react';
import { fetchTechnicals, type TechnicalsResponse } from '@services/api';

type Timeframe = '1m' | '5m' | '15m' | '1H' | '4H' | '1D';

const TIMEFRAMES: Timeframe[] = ['1m', '5m', '15m', '1H', '4H', '1D'];

const SIGNAL_COLORS = {
  buy:  { badge: 'bg-green-600',   text: 'text-green-400',   bar: 'bg-green-500',   icon: '▲' },
  sell: { badge: 'bg-red-600',     text: 'text-red-400',     bar: 'bg-red-500',     icon: '▼' },
  hold: { badge: 'bg-yellow-600',  text: 'text-yellow-400',  bar: 'bg-yellow-500',  icon: '●' },
};

const RISK_COLORS = {
  low:    'text-green-400',
  medium: 'text-yellow-400',
  high:   'text-red-400',
};

const RISK_BADGE = {
  low:    'bg-green-900 text-green-300 border border-green-700',
  medium: 'bg-yellow-900 text-yellow-300 border border-yellow-700',
  high:   'bg-red-900 text-red-300 border border-red-700',
};

export const SIGNAL_ORDER = { buy: 0, sell: 1, hold: 2 };

const SignalBar: React.FC<{ signals: TechnicalsResponse['signals'] }> = ({ signals }) => {
  if (!signals || signals.length === 0) return null;
  const buy  = signals.filter(s => s.action === 'buy').length;
  const sell = signals.filter(s => s.action === 'sell').length;
  const hold = signals.filter(s => s.action === 'hold').length;
  const total = signals.length;
  const buyPct  = total ? buy  / total * 100 : 0;
  const sellPct = total ? sell / total * 100 : 0;
  const holdPct = 100 - buyPct - sellPct;

  const overall = buy > sell ? 'buy' : sell > buy ? 'sell' : 'hold';
  const cls = SIGNAL_COLORS[overall];

  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      {/* Overall signal */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-xs text-gray-400 uppercase tracking-wider mb-1">綜合信號</div>
          <div className={`text-2xl font-bold ${cls.text} flex items-center gap-2`}>
            <span>{cls.icon}</span>
            <span>{overall === 'buy' ? '買入' : overall === 'sell' ? '賣出' : '中性'}</span>
          </div>
        </div>
        <div className="text-right">
          <div className={`text-xs font-mono px-3 py-1 rounded-full ${RISK_BADGE[overall === 'buy' ? 'low' : overall === 'sell' ? 'high' : 'medium']}`}>
            {overall === 'buy' ? '低風險' : overall === 'sell' ? '高風險' : '中風險'}
          </div>
        </div>
      </div>

      {/* Bar */}
      <div className="h-3 rounded-full overflow-hidden flex">
        <div className="bg-green-500 transition-all duration-500" style={{ width: `${buyPct}%` }} />
        <div className="bg-yellow-500 transition-all duration-500" style={{ width: `${holdPct}%` }} />
        <div className="bg-red-500 transition-all duration-500" style={{ width: `${sellPct}%` }} />
      </div>

      {/* Labels */}
      <div className="flex justify-between mt-2 text-xs text-gray-400">
        <span className="text-green-400">買 {buyPct.toFixed(0)}%</span>
        <span className="text-yellow-400">中性 {holdPct.toFixed(0)}%</span>
        <span className="text-red-400">賣 {sellPct.toFixed(0)}%</span>
      </div>
    </div>
  );
};

const IndicatorCard: React.FC<{
  name: string;
  label: string;
  value: number | null;
  signal: 'buy' | 'sell' | 'hold';
  description?: string;
}> = ({ name, label, value, signal, description }) => {
  const cls = SIGNAL_COLORS[signal];
  return (
    <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
      <div className="flex items-center justify-between mb-2">
        <div className="text-gray-400 text-xs uppercase tracking-wider">{label}</div>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls.badge}`}>
          {cls.icon} {signal === 'buy' ? '買' : signal === 'sell' ? '賣' : '中性'}
        </span>
      </div>
      <div className="text-2xl font-mono font-bold text-white mb-1">
        {value !== null ? value.toFixed(2) : '—'}
      </div>
      <div className="text-xs text-gray-500">{name}</div>
      {description && (
        <div className="text-xs text-gray-400 mt-2 leading-relaxed">{description}</div>
      )}
    </div>
  );
};

const SignalsTable: React.FC<{ signals: TechnicalsResponse['signals'] }> = ({ signals }) => {
  if (!signals || signals.length === 0) return null;
  // 拿最近 10 個
  const recent = [...signals].reverse().slice(0, 10);

  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-700">
        <div className="text-sm font-medium text-white">最近信號</div>
      </div>
      <div className="divide-y divide-slate-700">
        {recent.map((s, i) => {
          const cls = SIGNAL_COLORS[s.action];
          return (
            <div key={i} className="flex items-center justify-between px-4 py-3">
              <div className="flex items-center gap-3">
                <span className={`text-sm font-bold ${cls.text}`}>{cls.icon}</span>
                <div>
                  <div className="text-sm text-white">{s.label || s.type}</div>
                  <div className="text-xs text-gray-500 uppercase">{s.type}</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-2 py-0.5 rounded ${cls.badge}`}>
                  {s.action === 'buy' ? '買入' : s.action === 'sell' ? '賣出' : '中性'}
                </span>
                <div className="text-xs text-gray-400">
                  {Math.round(s.strength * 100)}%
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const SupportResistance: React.FC<{
  sr: TechnicalsResponse['support_resistance'];
}> = ({ sr }) => {
  if (!sr || sr.length === 0) return null;
  return (
    <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
      <div className="text-sm font-medium text-white mb-3">支撐 / 壓力</div>
      <div className="space-y-2">
        {sr.map((item, i) => (
          <div key={i} className="flex items-center justify-between">
            <span className={`text-xs px-2 py-0.5 rounded ${
              item.type === 'support' ? 'bg-blue-900 text-blue-300' : 'bg-purple-900 text-purple-300'
            }`}>
              {item.type === 'support' ? '支撐' : '壓力'}
            </span>
            <span className="text-sm font-mono text-white">{item.price.toFixed(2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const LoadingSpinner: React.FC = () => (
  <div className="flex items-center justify-center py-16">
    <div className="w-8 h-8 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
  </div>
);

const ErrorMessage: React.FC<{ error: string }> = ({ error }) => (
  <div className="bg-red-900/30 border border-red-700 rounded-xl p-4 text-red-300 text-sm text-center">
    ⚠️ {error}
  </div>
);

const TechnicalsPage: React.FC = () => {
  const [timeframe, setTimeframe] = useState<Timeframe>('1D');
  const [data, setData] = useState<TechnicalsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (tf: Timeframe) => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchTechnicals('TAIFEX-TGF1', tf);
      setData(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '載入失敗');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(timeframe);
  }, [timeframe]);

  const recommendation = data?.recommendation || '';
  const riskLevel = data?.risk_level || 'medium';

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">技術分析</h1>
          <p className="text-sm text-gray-400 mt-0.5">60 天歷史 · 完整技術指標 · 訊號列表 · 支撐阻力位</p>
        </div>
        {/* Timeframe selector */}
        <div className="flex gap-1 bg-slate-800 rounded-lg p-1 border border-slate-700">
          {TIMEFRAMES.map(tf => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-3 py-1.5 text-xs rounded-md font-medium transition-all ${
                timeframe === tf
                  ? 'bg-yellow-500 text-slate-900 font-bold'
                  : 'text-gray-400 hover:text-white hover:bg-slate-700'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Loading / Error */}
      {loading && <LoadingSpinner />}
      {error && <ErrorMessage error={error} />}
      {data && !data.error && (
        <>
          {/* Signal Bar + Recommendation */}
          <SignalBar signals={data.signals} />

          {/* Recommendation */}
          {recommendation && (
            <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
              <div className="text-xs text-gray-400 uppercase tracking-wider mb-1">操作建議</div>
              <div className="text-white font-medium">{recommendation}</div>
              {data.trend_score !== undefined && (
                <div className="mt-2 flex items-center gap-4">
                  <div className="text-xs text-gray-400">
                    趨勢分數：<span className="text-white font-mono">{data.trend_score.toFixed(1)}</span>
                  </div>
                  <div className={`text-xs font-medium ${RISK_COLORS[riskLevel]}`}>
                    風險：{riskLevel === 'low' ? '低' : riskLevel === 'high' ? '高' : '中'}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Indicator Cards */}
          {data.indicators && (
            <div>
              <div className="text-sm font-medium text-gray-300 mb-3">技術指標</div>
              <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
                {data.indicators.rsi && (
                  <IndicatorCard
                    name="RSI (14)"
                    label="RSI"
                    value={data.indicators.rsi.value}
                    signal={data.indicators.rsi.signal}
                    description={data.indicators.rsi.description}
                  />
                )}
                {data.indicators.macd && (
                  <IndicatorCard
                    name="MACD (12/26/9)"
                    label="MACD"
                    value={data.indicators.macd.value}
                    signal={data.indicators.macd.signal}
                    description={data.indicators.macd.description}
                  />
                )}
                {data.indicators.bollinger && (
                  <IndicatorCard
                    name="Bollinger (20/2σ)"
                    label="BB"
                    value={data.indicators.bollinger.value}
                    signal={data.indicators.bollinger.signal}
                    description={data.indicators.bollinger.description}
                  />
                )}
                {data.indicators.ma_short && (
                  <IndicatorCard
                    name="MA (20)"
                    label="MA 短"
                    value={data.indicators.ma_short.value}
                    signal={data.indicators.ma_short.signal}
                    description={data.indicators.ma_short.description}
                  />
                )}
                {data.indicators.ma_long && (
                  <IndicatorCard
                    name="MA (60)"
                    label="MA 長"
                    value={data.indicators.ma_long.value}
                    signal={data.indicators.ma_long.signal}
                    description={data.indicators.ma_long.description}
                  />
                )}
              </div>
            </div>
          )}

          {/* Bottom grid: signals + support/resistance */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <SignalsTable signals={data.signals} />
            <SupportResistance sr={data.support_resistance} />
          </div>
        </>
      )}

      {/* No data yet */}
      {data && data.error && (
        <ErrorMessage error={data.error} />
      )}
    </div>
  );
};

export default TechnicalsPage;
