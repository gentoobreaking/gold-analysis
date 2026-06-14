-- 黃金價格數據庫 Schema
-- 支持台銀和 Yahoo Finance 數據

-- 金屬種類表
CREATE TABLE IF NOT EXISTS metals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT UNIQUE NOT NULL,        -- 代碼 (GOLD, SILVER, etc.)
    name TEXT NOT NULL,                  -- 名稱
    unit TEXT DEFAULT 'oz',              -- 單位
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 價格數據表
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metal_id INTEGER NOT NULL,
    source TEXT NOT NULL,                -- 數據源 (BOT, YAHOO)
    buy_price REAL,                      -- 買入價
    sell_price REAL,                     -- 賣出價
    spot_price REAL,                     -- 現貨價
    currency TEXT DEFAULT 'TWD',         -- 貨幣
    timestamp TIMESTAMP NOT NULL,        -- 數據時間戳
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(metal_id, source, timestamp), -- 去重約束
    FOREIGN KEY (metal_id) REFERENCES metals(id)
);

-- 數據收集日誌表
CREATE TABLE IF NOT EXISTS collection_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    status TEXT NOT NULL,                -- SUCCESS, FAILED, RETRY
    message TEXT,
    records_collected INTEGER DEFAULT 0,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引優化
CREATE INDEX IF NOT EXISTS idx_prices_metal ON prices(metal_id);
CREATE INDEX IF NOT EXISTS idx_prices_timestamp ON prices(timestamp);
CREATE INDEX IF NOT EXISTS idx_prices_source ON prices(source);
CREATE INDEX IF NOT EXISTS idx_collection_logs_created ON collection_logs(created_at);

-- 初始化金屬數據
INSERT OR IGNORE INTO metals (symbol, name, unit) VALUES
    ('GOLD', '黃金', 'oz'),
    ('SILVER', '白銀', 'oz'),
    ('PLATINUM', '白金', 'oz'),
    ('PALLADIUM', '鈀金', 'oz');
