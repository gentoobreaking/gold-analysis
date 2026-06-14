/**
 * 合約頁（Contracts）
 * 展示台灣黃金期貨（TGF1）合約規格與各月合約列表
 * 資料來源：TAIFEX 台灣期貨交易所
 */
import React, { useEffect, useState } from 'react';

interface ContractSpec {
  symbol: string;
  full_name: string;
  exchange: string;
  multiplier: string;
  tick_size: string;
  tick_value: string;
  trading_session: string;
  settlement: string;
  last_trading_day: string;
  delivery_months: string;
  margin: string;
  price_limit: string;
  daily_settlement: string;
}

interface ContractMonth {
  delivery_month: string;
  delivery_label: string;
  contract_code: string;
  last_trading_date: string;
  is_near: boolean;
  months_ahead: number;
}

interface ContractsData {
  specs: ContractSpec;
  contracts: ContractMonth[];
  fetched_at: string;
}

// ── 合約規格卡 ────────────────────────────────────────────────────────────────

const SpecRow: React.FC<{ label: string; value: string; highlight?: boolean }> = ({
  label,
  value,
  highlight,
}) => (
  <tr className={highlight ? 'bg-yellow-900/20' : 'hover:bg-slate-700/50 transition-colors'}>
    <td className="px-4 py-2.5 text-sm text-gray-400 w-40 font-medium">{label}</td>
    <td className="px-4 py-2.5 text-sm text-white">{value}</td>
  </tr>
);

// ── 月份合約卡 ────────────────────────────────────────────────────────────────

const ContractCard: React.FC<{ c: ContractMonth }> = ({ c }) => {
  const labelStyle = c.is_near
    ? 'bg-yellow-500 text-black font-bold'
    : 'bg-slate-700 text-gray-300';
  const borderStyle = c.is_near
    ? 'border-yellow-500'
    : 'border-slate-700';

  const daysUntil = Math.ceil(
    (new Date(c.last_trading_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
  );
  const daysLabel =
    daysUntil < 0
      ? '已到期'
      : daysUntil === 0
      ? '今日到期'
      : `${daysUntil} 天後到期`;

  return (
    <div
      className={`bg-slate-800 rounded-xl p-4 border-2 ${borderStyle} transition-all hover:scale-[1.02] cursor-default`}
      style={c.is_near ? { boxShadow: '0 0 16px rgba(234,179,8,0.2)' } : {}}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${labelStyle}`}>
            {c.is_near ? '近月' : `+${c.months_ahead}月`}
          </span>
          {c.is_near && (
            <span className="text-xs text-yellow-400">⬤ 主力合約</span>
          )}
        </div>
        <div className="text-xs text-gray-500">{c.delivery_month}</div>
      </div>

      {/* Contract code */}
      <div className="mb-2">
        <div className="text-xs text-gray-500 mb-0.5">合約代碼</div>
        <div className="text-lg font-mono font-bold text-white tracking-wide">
          {c.contract_code}
        </div>
      </div>

      {/* Delivery label */}
      <div className="text-sm text-gray-300 mb-1">{c.delivery_label}</div>

      {/* Last trading date */}
      <div className="mt-3 pt-3 border-t border-slate-700 flex items-center justify-between">
        <div>
          <div className="text-xs text-gray-500">最後交易日</div>
          <div className="text-sm text-white font-medium">{c.last_trading_date}</div>
        </div>
        <div
          className={`text-xs px-2 py-1 rounded-full ${
            daysUntil < 7
              ? 'bg-red-900/60 text-red-300'
              : daysUntil < 30
              ? 'bg-orange-900/60 text-orange-300'
              : 'bg-slate-700 text-gray-400'
          }`}
        >
          {daysLabel}
        </div>
      </div>
    </div>
  );
};

// ── 月份合約時序軸 ────────────────────────────────────────────────────────────

const ContractTimeline: React.FC<{ contracts: ContractMonth[] }> = ({ contracts }) => (
  <div className="relative">
    {/* Timeline bar */}
    <div className="flex items-center gap-0 overflow-x-auto pb-2">
      {contracts.map((c, i) => {
        const isNear = c.is_near;
        const isPast = c.months_ahead < 0;
        return (
          <div key={c.delivery_month} className="flex-1 min-w-0 relative">
            {/* Connector line */}
            {i > 0 && (
              <div className="absolute -left-3 top-3 w-6 h-0.5 bg-slate-600 z-0" />
            )}
            <div
              className={`relative z-10 h-6 rounded-full flex items-center justify-center text-xs font-medium transition-all ${
                isNear
                  ? 'bg-yellow-500 text-black'
                  : isPast
                  ? 'bg-slate-700 text-gray-500'
                  : 'bg-slate-700 text-gray-300 hover:bg-slate-600'
              }`}
            >
              {c.delivery_month.split('-')[1]}月
            </div>
          </div>
        );
      })}
    </div>
  </div>
);

// ── 主頁面 ───────────────────────────────────────────────────────────────────

const ContractsPage: React.FC = () => {
  const [data, setData] = useState<ContractsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch('/api/contracts');
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
          <h1 className="text-xl font-bold text-white">合約資訊</h1>
          <p className="text-sm text-gray-400 mt-0.5">
            台灣黃金期貨 TGF1 · TAIFEX 台灣期貨交易所
          </p>
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
          {/* 合約規格表 */}
          <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
            <div className="px-5 py-3.5 border-b border-slate-700 flex items-center justify-between">
              <div className="text-sm font-bold text-white">📋 合約規格</div>
              <div className="text-xs text-gray-500">{data.fetched_at}</div>
            </div>
            <table className="w-full">
              <tbody>
                <SpecRow label="合約代碼" value={data.specs.symbol} highlight />
                <SpecRow label="商品名稱" value={data.specs.full_name} />
                <SpecRow label="交易所" value={data.specs.exchange} />
                <SpecRow label="合約乘數" value={data.specs.multiplier} />
                <SpecRow label="最小跳動" value={data.specs.tick_size} />
                <SpecRow label="每口價值" value={data.specs.tick_value} />
                <SpecRow label="交易時段" value={data.specs.trading_session} />
                <SpecRow label="結算方式" value={data.specs.settlement} />
                <SpecRow label="最後交易日" value={data.specs.last_trading_day} />
                <SpecRow label="掛牌月份" value={data.specs.delivery_months} />
                <SpecRow label="原始保證金" value={data.specs.margin} />
                <SpecRow label="漲跌限制" value={data.specs.price_limit} />
                <SpecRow label="每日結算" value={data.specs.daily_settlement} />
              </tbody>
            </table>
          </div>

          {/* 月份合約時序軸 */}
          <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
            <div className="text-sm font-bold text-white mb-3">📅 月份合約時序</div>
            <ContractTimeline contracts={data.contracts} />
          </div>

          {/* 月份合約卡片 */}
          <div>
            <div className="text-sm font-bold text-white mb-3">📆 各月合約列表</div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              {data.contracts.map((c) => (
                <ContractCard key={c.contract_code} c={c} />
              ))}
            </div>
          </div>

          {/* 說明 */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl px-4 py-3 text-xs text-gray-500 space-y-1">
            <div>• 近月合約（黃色）為目前主力交易合約，成交量最大、流動性最好。</div>
            <div>• 月份代碼：F=1月 G=2月 H=3月 J=4月 K=5月 M=6月 N=7月 Q=8月 U=9月 V=10月 X=11月 Z=12月</div>
            <div>• 合約到期前請注意保證金調整風險，並提前平倉或轉倉。</div>
            <div className="text-gray-600 mt-1">
              ⚠️ 保證金數值僅供參考，請以 TAIFEX 官網最新公告為準。
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ContractsPage;
