"""
台灣銀行黃金存摺價格適配器
數據源：https://www.bot.com.tw/gold/info
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, List, Optional
import logging
import re

logger = logging.getLogger(__name__)


class BotBankAdapter:
    """台銀黃金價格適配器"""
    
    SOURCE_NAME = "BOT"
    BASE_URL = "https://www.bot.com.tw/gold/info"
    TIMEOUT = 10
    
    # 金屬代碼映射
    METAL_MAP = {
        "黃金": "GOLD",
        "白銀": "SILVER",
        "白金": "PLATINUM",
        "鈀金": "PALLADIUM",
    }
    
    def __init__(self, timeout: int = None):
        self.timeout = timeout or self.TIMEOUT
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36'
        })
    
    def fetch_prices(self) -> List[Dict]:
        """
        獲取台銀黃金存摺價格
        
        Returns:
            價格數據列表
        """
        try:
            response = self.session.get(
                self.BASE_URL,
                timeout=self.timeout
            )
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            return self._parse_prices(response.text)
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch BOT prices: {e}")
            raise
    
    def _parse_prices(self, html: str) -> List[Dict]:
        """解析 HTML 頁面提取價格"""
        soup = BeautifulSoup(html, 'html.parser')
        prices = []
        timestamp = datetime.now()
        
        # 嘗試找到價格表格
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    # 嘗試提取金屬名稱和價格
                    text = ' '.join(cell.get_text(strip=True) for cell in cells)
                    
                    for chinese_name, symbol in self.METAL_MAP.items():
                        if chinese_name in text:
                            price_data = self._extract_price_from_row(
                                cells, symbol, timestamp
                            )
                            if price_data:
                                prices.append(price_data)
                                break
        
        # 如果表格解析失敗，使用正則表達式
        if not prices:
            prices = self._parse_with_regex(html, timestamp)
        
        logger.info(f"Parsed {len(prices)} prices from BOT")
        return prices
    
    def _extract_price_from_row(self, cells, symbol: str, 
                                 timestamp: datetime) -> Optional[Dict]:
        """從表格行提取價格"""
        try:
            # 價格通常在後面的單元格
            prices = []
            for cell in cells:
                text = cell.get_text(strip=True)
                # 匹配價格格式 (如: 2,345.67 或 2345.67)
                match = re.search(r'[\d,]+\.?\d*', text)
                if match:
                    price_str = match.group().replace(',', '')
                    try:
                        price = float(price_str)
                        if price > 0:
                            prices.append(price)
                    except ValueError:
                        continue
            
            if len(prices) >= 2:
                return {
                    'symbol': symbol,
                    'source': self.SOURCE_NAME,
                    'buy_price': prices[0],    # 買入價
                    'sell_price': prices[1],   # 賣出價
                    'spot_price': (prices[0] + prices[1]) / 2,
                    'currency': 'TWD',
                    'timestamp': timestamp,
                }
        except Exception as e:
            logger.debug(f"Failed to extract price: {e}")
        
        return None
    
    def _parse_with_regex(self, html: str, timestamp: datetime) -> List[Dict]:
        """使用正則表達式解析價格（備用方案）"""
        prices = []
        
        # 這裡可以根據實際頁面結構添加正則匹配邏輯
        # 目前返回空列表，實際使用時需要根據頁面調整
        
        return prices
    
    def get_gold_price(self) -> Optional[Dict]:
        """只獲取黃金價格"""
        prices = self.fetch_prices()
        for p in prices:
            if p['symbol'] == 'GOLD':
                return p
        return None
    
    def close(self):
        """關閉 session"""
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 測試入口
if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    
    with BotBankAdapter() as adapter:
        prices = adapter.fetch_prices()
        print(json.dumps(prices, indent=2, default=str))
