# INC-001 - 黃金價格顯示異常

**日期**: 2026-04-10  
**發現者**: 豪  
**嚴重程度**: 🟡 中  
**狀態**: ✅ 已解決

## 問題描述

黃金價格監控腳本顯示的「本行賣出」和「本行買進」價格相同（都顯示 4,887 元），與實際情況不符（應有價差）。

## 影響範圍

- **影響模組**: `scripts/gold_monitor.py`
- **影響功能**: 價格通知、歷史記錄、圖表顯示
- **影響時間**: 2026-04-10 02:06 發現

## 根因分析

**問題**: 正則表達式匹配錯誤的 HTML table

```python
# 錯誤的正則
pattern = r'本行賣出[\s\S]*?(\d{1,3},\d{3})'
```

這個正則會匹配到「黃金條塊 1公斤」的價格表格，而非「黃金存摺 1公克」的表格。

台灣銀行網頁結構：
```html
<table>  <!-- 黃金條塊 1公斤 -->
  <tr><td>本行賣出</td><td>4,887</td></tr>
  <tr><td>本行買進</td><td>4,887</td></tr>
</table>

<table>  <!-- 黃金存摺 1公克 -->
  <tr><td>本行賣出</td><td>4,887</td></tr>
  <tr><td>本行買進</td><td>4,835</td></tr>
</table>
```

## 解決方案

改用 DOM 直接解析，精確定位「黃金存摺 1公克」表格：

```python
# 修正後的解析邏輯
result = await page.evaluate('''() => {
    const tables = document.querySelectorAll('table');
    for (const table of tables) {
        const caption = table.querySelector('caption');
        if (caption && caption.textContent.includes('黃金存摺') && 
            caption.textContent.includes('1公克')) {
            const rows = table.querySelectorAll('tr');
            for (const row of rows) {
                const cells = row.querySelectorAll('td');
                if (cells.length >= 2) {
                    const label = cells[0].textContent.trim();
                    const value = cells[1].textContent.trim().replace(/,/g, '');
                    if (label === '本行賣出') sell = parseInt(value);
                    if (label === '本行買進') buy = parseInt(value);
                }
            }
        }
    }
    return {sell, buy};
}''')
```

## 驗證結果

| 項目 | 修正前 | 修正後 |
|------|--------|--------|
| 賣出價格 | 4,887 | 4,887 ✅ |
| 買進價格 | 4,887 ❌ | 4,835 ✅ |
| 價差 | 0 ❌ | 52 ✅ |

## 預防措施

1. **資料驗證**: 加入價差檢查，若買賣價差 < 10 元則告警
2. **關鍵字精確**: 使用「黃金存摺 1公克」而非僅「本行賣出」
3. **測試覆蓋**: 增加價格合理性測試

## 相關 Commit

```
commit: feat: add gold_monitor.py (dual buy/sell price, DOM-based parsing)
Author: 碼農1號
Date: 2026-04-10 02:10
```

---
*問題關閉時間: 2026-04-10 02:10*
