/**
 * 工具函數
 */
import { format } from 'date-fns';

/**
 * 格式化價格
 */
export const formatPrice = (price: number, decimals = 2): string => {
  return price.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
};

/**
 * 格式化時間戳
 */
export const formatTimestamp = (timestamp: number, formatStr = 'yyyy-MM-dd HH:mm:ss'): string => {
  return format(new Date(timestamp), formatStr);
};

/**
 * 格式化百分比
 */
export const formatPercent = (value: number, decimals = 2): string => {
  return `${(value >= 0 ? '+' : '')}${value.toFixed(decimals)}%`;
};

/**
 * 計算價格變動百分比
 */
export const calcPriceChange = (current: number, previous: number): number => {
  if (previous === 0) return 0;
  return ((current - previous) / previous) * 100;
};
