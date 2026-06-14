"""
Yahoo Finance 貴金屬價格適配器
使用 yfinance 庫獲取實時價格
"""
import yfinance as yf
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class YahooFinanceAdapter:
    """Yahoo Finance 貴金屬價格適配器"""
    
    SOURCE_NAME = "YAHOO"
    TIMEOUT = 10
    
    # Yahoo Finance 符號映射
    SYMBOL_MAP = {
        'GOLD': 'GC=F',        # 黃金期貨
        'SILVER': 'SI=F',      # 白銀期貨
        'PLATINUM': 'PL=F',    # 白金期貨
        'PALLADIUM': 'PA=F',   # 鈀金期貨
    }
    
    # 匯率符號
    USD_TWD_SYMBOL = 'TWD=X'
    
    def __init__(self, timeout: int = None, convert_to_twd: bool = True):
        """
        初始化適配器
        
        Args:
            timeout: 請求超時秒數
            convert_to_twd: 是否轉換為台幣
        """
        self.timeout = timeout or self.TIMEOUT
        self.convert_to_twd = convert_to_twd
        self._usd_twd_rate: Optional[float] = None
    
    def fetch_prices(self, symbols: List[str] = None) -> List[Dict]:
        """
        獲取貴金屬價格
        
        Args:
            symbols: 要獲取的金屬符號列表，默認全部
        
        Returns:
            價格數據列表
        """
        if symbols is None:
            symbols = list(self.SYMBOL_MAP.keys())
        
        # 獲取匯率
        if self.convert_to_twd:
            self._fetch_usd_twd_rate()
        
        prices = []
        timestamp = datetime.now()
        
        for symbol in symbols:
            try:
                price_data = self._fetch_single_price(symbol, timestamp)
                if price_data:
                    prices.append(price_data)
            except Exception as e:
                logger.error(f"Failed to fetch {symbol}: {e}")
                continue
        
        logger.info(f"Fetched {len(prices)} prices from Yahoo Finance")
        return prices
    
    def _fetch_single_price(self, symbol: str, timestamp: datetime) -> Optional[Dict]:
        """獲取單個金屬價格"""
        yahoo_symbol = self.SYMBOL_MAP.get(symbol)
        if not yahoo_symbol:
            logger.warning(f"Unknown symbol: {symbol}")
            return None
        
        try:
            ticker = yf.Ticker(yahoo_symbol)
            info = ticker.info
            
            # 獲取當前價格
            current_price = info.get('currentPrice') or info.get('regularMarketPrice')
            if not current_price:
                # 嘗試從歷史數據獲取
                hist = ticker.history(period='1d')
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
            
            if not current_price:
                logger.warning(f"No price data for {symbol}")
                return None
            
            # 轉換為台幣
            price_twd = current_price
            currency = 'USD'
            
            if self.convert_to_twd and self._usd_twd_rate:
                price_twd = current_price * self._usd_twd_rate
                currency = 'TWD'
            
            return {
                'symbol': symbol,
                'source': self.SOURCE_NAME,
                'spot_price': round(price_twd, 2),
                'buy_price': round(price_twd * 0.998, 2),   # 模擬買入價（略低）
                'sell_price': round(price_twd * 1.002, 2),  # 模擬賣出價（略高）
                'currency': currency,
                'timestamp': timestamp,
                'raw_price_usd': current_price,
            }
            
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return None
    
    def _fetch_usd_twd_rate(self) -> Optional[float]:
        """獲取 USD/TWD 匯率"""
        try:
            ticker = yf.Ticker(self.USD_TWD_SYMBOL)
            info = ticker.info
            rate = info.get('currentPrice') or info.get('regularMarketPrice')
            
            if rate:
                self._usd_twd_rate = rate
                logger.info(f"USD/TWD rate: {rate}")
                return rate
            
            # 備用：從歷史數據獲取
            hist = ticker.history(period='1d')
            if not hist.empty:
                self._usd_twd_rate = hist['Close'].iloc[-1]
                return self._usd_twd_rate
                
        except Exception as e:
            logger.warning(f"Failed to fetch USD/TWD rate: {e}")
        
        # 使用預設匯率
        self._usd_twd_rate = 32.0
        logger.warning(f"Using default USD/TWD rate: {self._usd_twd_rate}")
        return self._usd_twd_rate
    
    def get_gold_price(self) -> Optional[Dict]:
        """只獲取黃金價格"""
        prices = self.fetch_prices(['GOLD'])
        return prices[0] if prices else None
    
    def get_price_history(self, symbol: str, period: str = '1mo') -> List[Dict]:
        """
        獲取歷史價格
        
        Args:
            symbol: 金屬符號
            period: 時間週期 (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        
        Returns:
            歷史價格列表
        """
        yahoo_symbol = self.SYMBOL_MAP.get(symbol)
        if not yahoo_symbol:
            return []
        
        try:
            ticker = yf.Ticker(yahoo_symbol)
            hist = ticker.history(period=period)
            
            prices = []
            for index, row in hist.iterrows():
                price_twd = row['Close']
                if self.convert_to_twd and self._usd_twd_rate:
                    price_twd *= self._usd_twd_rate
                
                prices.append({
                    'symbol': symbol,
                    'source': self.SOURCE_NAME,
                    'spot_price': round(price_twd, 2),
                    'timestamp': index.to_pydatetime(),
                })
            
            return prices
            
        except Exception as e:
            logger.error(f"Failed to fetch history for {symbol}: {e}")
            return []


# 測試入口
if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    
    adapter = YahooFinanceAdapter()
    prices = adapter.fetch_prices()
    print(json.dumps(prices, indent=2, default=str))
