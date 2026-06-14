/**
 * 側邊欄導航
 */
import React from 'react';
import { NavLink } from 'react-router-dom';

const navItems = [
  { path: '/', label: '🥇 黃金分析', icon: '' },
  { path: '/summary', label: '市場概要', icon: '📊' },
  { path: '/chart', label: '走勢圖', icon: '📈' },
  { path: '/analysis', label: '市場分析', icon: '🔍' },
  { path: '/decision', label: '決策詳情', icon: '🎯' },
  { path: '/technicals', label: '技術分析', icon: '📊' },
  { path: '/forward-curve', label: '遠期曲線', icon: '📈' },
  { path: '/seasonality', label: '季節性', icon: '🗓️' },
  { path: '/contracts', label: '合約資訊', icon: '📄' },
  { path: '/news', label: '市場新聞', icon: '📰' },
  { path: '/history', label: '歷史報價', icon: '📜' },
  { path: '/settings', label: '系統設定', icon: '⚙️' },
];

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 bg-slate-800 border-r border-gray-700 min-h-screen">
      <div className="p-4">
        <div className="text-yellow-500 text-2xl mb-2">🥇</div>
        <div className="text-white font-semibold">黃金分析系統</div>
      </div>
      
      <nav className="mt-4">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 transition-colors ${
                isActive 
                  ? 'bg-yellow-500/20 text-yellow-500 border-r-2 border-yellow-500' 
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }`
            }
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
};
