/**
 * 頂部導航欄
 */
import React from 'react';
import { useGoldStore } from '@stores/useGoldStore';

export const Header: React.FC = () => {
  const { currentPrice, isLoading } = useGoldStore();
  
  return (
    <header className="bg-slate-800 border-b border-gray-700 px-6 py-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-yellow-500">
          Gold Analysis System
        </h1>
        
        <div className="flex items-center gap-6">
          {/* 當前價格 */}
          <div className="flex items-center gap-2">
            <span className="text-gray-400 text-sm">NT/克</span>
            <span className="text-2xl font-bold text-white">
              {isLoading ? (
                <span className="animate-pulse">Loading...</span>
              ) : (
                currentPrice > 0 ? `${currentPrice.toFixed(0)}` : '--'
              )}
            </span>
          </div>
          
          {/* 狀態指示燈 */}
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${isLoading ? 'bg-yellow-500 animate-pulse' : 'bg-green-500'}`} />
            <span className="text-gray-400 text-sm">
              {isLoading ? 'Updating' : 'Live'}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};
