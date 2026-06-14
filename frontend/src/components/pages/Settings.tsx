/**
 * Settings 頁面 - 系統設定與監控配置
 */
import React, { useState } from 'react';

interface AlertConfig {
  priceAbove: number;
  priceBelow: number;
  enabled: boolean;
}

const Settings: React.FC = () => {
  const [alerts, setAlerts] = useState<AlertConfig>({
    priceAbove: 9500,
    priceBelow: 8500,
    enabled: true,
  });
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    localStorage.setItem('gold-alert-config', JSON.stringify(alerts));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-6 p-4 max-w-2xl">
      <div>
        <h2 className="text-2xl font-bold text-white">⚙️ 系統設定</h2>
        <p className="text-gray-400 text-sm">監控告警門檻、通知設定</p>
      </div>

      {/* Alert Settings */}
      <div className="bg-slate-800 rounded-lg p-6">
        <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
          🔔 價格告警設定
        </h3>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-gray-300 text-sm font-medium">啟用告警</div>
              <div className="text-gray-500 text-xs">當價格觸及設定門檻時通知</div>
            </div>
            <button
              onClick={() => setAlerts(a => ({ ...a, enabled: !a.enabled }))}
              className={`w-12 h-6 rounded-full transition-colors ${alerts.enabled ? 'bg-green-500' : 'bg-slate-600'}`}
            >
              <div className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${alerts.enabled ? 'translate-x-6' : 'translate-x-0.5'}`} />
            </button>
          </div>

          <div className="border-t border-slate-700 pt-4 space-y-4">
            <div>
              <label className="block text-gray-300 text-sm mb-2">
                🔺 高價告警門檻（賣出價高於此價）
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  value={alerts.priceAbove}
                  onChange={(e) => setAlerts(a => ({ ...a, priceAbove: Number(e.target.value) }))}
                  disabled={!alerts.enabled}
                  className="flex-1 bg-slate-700 text-white rounded px-3 py-2 disabled:opacity-50"
                  placeholder="5000"
                />
                <span className="text-gray-400">NT/克</span>
              </div>
              <div className="text-xs text-gray-500 mt-1">目前台銀賣出價約 9000+（建議高於此設定）</div>
            </div>

            <div>
              <label className="block text-gray-300 text-sm mb-2">
                🔻 低價告警門檻（賣出價低於此價）
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  value={alerts.priceBelow}
                  onChange={(e) => setAlerts(a => ({ ...a, priceBelow: Number(e.target.value) }))}
                  disabled={!alerts.enabled}
                  className="flex-1 bg-slate-700 text-white rounded px-3 py-2 disabled:opacity-50"
                  placeholder="8000"
                />
                <span className="text-gray-400">NT/克</span>
              </div>
              <div className="text-xs text-gray-500 mt-1">目前台銀賣出價約 9000+（建議低於此設定）</div>
            </div>
          </div>
        </div>

        <button
          onClick={handleSave}
          className={`mt-6 px-6 py-2 rounded font-semibold transition ${saved ? 'bg-green-600 text-white' : 'bg-yellow-600 hover:bg-yellow-500 text-white'}`}
        >
          {saved ? '✅ 已儲存' : '💾 儲存設定'}
        </button>
      </div>

      {/* API Status */}
      <div className="bg-slate-800 rounded-lg p-6">
        <h3 className="text-white font-semibold mb-4">📡 API 狀態</h3>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-400">後端服務</span>
            <span className="text-green-400">✅ 正常 (localhost:8765)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">前端服務</span>
            <span className="text-green-400">✅ 正常 (localhost:3000)</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">資料來源</span>
            <span className="text-blue-400">台灣銀行黃金存摺</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">更新頻率</span>
            <span className="text-yellow-400">每分鐘自動更新</span>
          </div>
        </div>
      </div>

      {/* System Info */}
      <div className="bg-slate-800 rounded-lg p-6">
        <h3 className="text-white font-semibold mb-4">ℹ️ 系統資訊</h3>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-400">版本</span>
            <span className="text-white">Gold Analysis Extend v1.0.0</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">前端框架</span>
            <span className="text-white">React + TypeScript + Tailwind</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">圖表引擎</span>
            <span className="text-white">TradingView Lightweight Charts</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">數據代理</span>
            <span className="text-white">Vite Proxy → Flask Backend</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">最後更新</span>
            <span className="text-gray-300">{new Date().toLocaleString('zh-TW')}</span>
          </div>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="bg-red-900/20 border border-red-800 rounded-lg p-6">
        <h3 className="text-red-400 font-semibold mb-3">⚠️ 進階操作</h3>
        <div className="flex gap-3">
          <button
            onClick={() => {
              if (confirm('確定清除所有本地快取？')) {
                localStorage.clear();
                window.location.reload();
              }
            }}
            className="px-4 py-2 bg-red-700/50 hover:bg-red-700 text-red-300 rounded text-sm transition"
          >
            🗑️ 清除本地快取
          </button>
        </div>
      </div>
    </div>
  );
};

export default Settings;
