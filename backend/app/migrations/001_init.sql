-- =============================================================================
-- Gold Analysis Database Migration Script
-- PostgreSQL Initial Schema - Migration 001
-- 
-- Author: Gold Analysis Team
-- Version: 1.0.0
-- Created: 2026-04-07
-- 
-- Description:
--   Initial database schema for gold-analysis-core project.
--   Creates all core tables: users, portfolios, portfolio_holdings, decisions, alerts.
--   Includes PostgreSQL ENUM types, indexes, and foreign key constraints.
--
-- Usage:
--   psql -U postgres -d gold_analysis -f 001_init.sql
--   or via Alembic: alembic upgrade head
--
-- Prerequisites:
--   - PostgreSQL 14+
--   - uuid-ossp extension enabled (for UUID support if needed)
-- =============================================================================

-- Enable UUID extension (reserved for future use with auth tokens, etc.)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- SECTION 1: PostgreSQL ENUM Types
-- Define reusable enumeration types used across tables
-- =============================================================================

-- Decision type enumeration
-- Values: buy (買入), sell (賣出), hold (持有), watch (觀察)
DROP TYPE IF EXISTS decision_type CASCADE;
CREATE TYPE decision_type AS ENUM ('buy', 'sell', 'hold', 'watch');

-- Decision source enumeration
-- Values: ai_analysis (AI分析), technical (技術分析), fundamental (基本面), sentiment (情緒), manual (手動)
DROP TYPE IF EXISTS decision_source CASCADE;
CREATE TYPE decision_source AS ENUM ('ai_analysis', 'technical', 'fundamental', 'sentiment', 'manual');

-- Alert type enumeration
-- Values: price_above (價格高於), price_below (價格低於), indicator_cross (指標交叉), volume_spike (成交量突增)
DROP TYPE IF EXISTS alert_type CASCADE;
CREATE TYPE alert_type AS ENUM ('price_above', 'price_below', 'indicator_cross', 'volume_spike');

-- =============================================================================
-- SECTION 2: Core Entity Tables
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Table: users
-- Description: Core user account table for authentication and profile
-- Relationships: one-to-many with portfolios, decisions, alerts
-- Notes: timezone defaults to Asia/Taipei for local users
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    avatar_url VARCHAR(500),
    bio TEXT,
    timezone VARCHAR(50) DEFAULT 'Asia/Taipei',
    language VARCHAR(10) DEFAULT 'zh-TW',
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    is_premium BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

-- User lookup indexes
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
-- Active user filter index (common query pattern)
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active) WHERE is_active = TRUE;

COMMENT ON TABLE users IS 'User account table - stores authentication and profile data';
COMMENT ON COLUMN users.hashed_password IS 'Bcrypt hashed password - never store plain text';
COMMENT ON COLUMN users.timezone IS 'User preferred timezone (IANA format, e.g. Asia/Taipei)';

-- -----------------------------------------------------------------------------
-- Table: portfolios
-- Description: Investment portfolio table - one portfolio per user
-- Relationships: many-to-one with users, one-to-many with holdings, decisions
-- Notes: Capital fields use DOUBLE PRECISION for financial calculations
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS portfolios (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(500),
    initial_capital DOUBLE PRECISION DEFAULT 0,
    current_value DOUBLE PRECISION DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Portfolio lookup by user
CREATE INDEX IF NOT EXISTS idx_portfolios_user ON portfolios(user_id);

COMMENT ON TABLE portfolios IS 'Investment portfolio table - tracks capital and positions';
COMMENT ON COLUMN portfolios.initial_capital IS 'Starting capital in USD';
COMMENT ON COLUMN portfolios.current_value IS 'Current portfolio value (updated via background job)';

-- -----------------------------------------------------------------------------
-- Table: portfolio_holdings
-- Description: Individual asset positions within a portfolio
-- Relationships: many-to-one with portfolios
-- Notes: asset_type examples: GOLD, DXY, BTC, USDT, EUR, rates
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id SERIAL PRIMARY KEY,
    portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    asset_type VARCHAR(20) NOT NULL,
    quantity DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_cost DOUBLE PRECISION NOT NULL DEFAULT 0,
    current_price DOUBLE PRECISION,
    market_value DOUBLE PRECISION,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_holdings_portfolio ON portfolio_holdings(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_holdings_asset ON portfolio_holdings(asset_type);
-- Composite index for portfolio + asset lookup (common pattern)
CREATE INDEX IF NOT EXISTS idx_holdings_portfolio_asset ON portfolio_holdings(portfolio_id, asset_type);

COMMENT ON TABLE portfolio_holdings IS 'Individual asset positions within a portfolio';
COMMENT ON COLUMN portfolio_holdings.asset_type IS 'Asset identifier: GOLD, DXY, BTC, USDT, EUR, rates';
COMMENT ON COLUMN portfolio_holdings.avg_cost IS 'Average cost basis per unit';

-- -----------------------------------------------------------------------------
-- Table: decisions
-- Description: AI-generated trading decision records
-- Relationships: many-to-one with users, optional many-to-one with portfolios
-- Notes: Contains reasoning, technical indicators snapshot, execution status
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS decisions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE SET NULL,
    decision_type decision_type NOT NULL,
    source decision_source NOT NULL,
    asset VARCHAR(20) NOT NULL DEFAULT 'GOLD',
    signal_strength DOUBLE PRECISION NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    price_target DOUBLE PRECISION,
    stop_loss DOUBLE PRECISION,
    reason_zh TEXT,
    reason_en TEXT,
    indicators_snapshot TEXT,
    analysis_scores TEXT,
    is_executed BOOLEAN DEFAULT FALSE,
    executed_at TIMESTAMP WITH TIME ZONE,
    execution_price DOUBLE PRECISION,
    model_version VARCHAR(50) DEFAULT 'v1',
    extra_data TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_decisions_user ON decisions(user_id);
CREATE INDEX IF NOT EXISTS idx_decisions_portfolio ON decisions(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_decisions_asset ON decisions(asset);
-- Time-based index for history queries
CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_at);
-- Composite index for user + asset queries
CREATE INDEX IF NOT EXISTS idx_decisions_user_asset ON decisions(user_id, asset);
-- Unexecuted decisions filter (for dashboard queries)
CREATE INDEX IF NOT EXISTS idx_decisions_unexecuted ON decisions(is_executed, created_at) WHERE is_executed = FALSE;

COMMENT ON TABLE decisions IS 'AI trading decision records';
COMMENT ON COLUMN decisions.signal_strength IS 'Signal strength 0.0-1.0 (0=neutral, 1=strong)';
COMMENT ON COLUMN decisions.confidence IS 'Model confidence 0.0-1.0';
COMMENT ON COLUMN decisions.indicators_snapshot IS 'JSON snapshot of technical indicators at decision time';
COMMENT ON COLUMN decisions.analysis_scores IS 'JSON scores across analysis dimensions (technical, fundamental, sentiment)';
COMMENT ON COLUMN decisions.extra_data IS 'Additional JSON metadata (reserved)';

-- -----------------------------------------------------------------------------
-- Table: alerts
-- Description: User-defined price alerts and notifications
-- Relationships: many-to-one with users
-- Notes: triggered_at is set when alert fires; is_active controls visibility
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    alert_type alert_type NOT NULL,
    asset VARCHAR(20) NOT NULL,
    target_price DOUBLE PRECISION NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    triggered_at TIMESTAMP WITH TIME ZONE,
    extra_data VARCHAR(500)
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_asset ON alerts(asset);
-- Active alerts filter (most common query)
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(is_active, asset) WHERE is_active = TRUE;

COMMENT ON TABLE alerts IS 'User price alerts and notifications';
COMMENT ON COLUMN alerts.alert_type IS 'Alert trigger type: price_above, price_below, indicator_cross, volume_spike';
COMMENT ON COLUMN alerts.target_price IS 'Target price level for the alert';
COMMENT ON COLUMN alerts.triggered_at IS 'Timestamp when alert was triggered (NULL if not triggered)';
COMMENT ON COLUMN alerts.extra_data IS 'Additional alert parameters (JSON)';

-- =============================================================================
-- SECTION 3: InfluxDB Time-Series Data (Reference)
-- =============================================================================
-- InfluxDB is used for time-series market data and technical indicators.
-- Unlike PostgreSQL, InfluxDB buckets are created via CLI or API, not SQL.
--
-- Required Buckets:
--   1. market-data     - Gold price, DXY, interest rates
--   2. indicators       - Technical indicators (RSI, MACD, Bollinger, etc.)
--   3. sentiment        - Market sentiment data
--   4. portfolio-values - Historical portfolio valuations
--
-- Example InfluxDB CLI commands:
--
--   # Create bucket
--   influx bucket create -n market-data -o gold-analysis -r 365d
--
--   # Create measurement schema reference:
--   # Measurement: gold_price
--   #   Tags: source (live, forecast)
--   #   Fields: price, change_24h, volume, open, high, low
--   #
--   # Measurement: technical_indicators
--   #   Tags: symbol (GOLD, DXY), indicator_type
--   #   Fields: value, param_json
--   #
--   # Measurement: ai_signals
--   #   Tags: user_id, symbol, decision_type
--   #   Fields: signal_strength, confidence, price_target
--
-- InfluxDB Connection Config (see backend/app/core/config.py):
--   INFLUXDB_URL=http://localhost:8086
--   INFLUXDB_TOKEN=<token>
--   INFLUXDB_ORG=gold-analysis
--   INFLUXDB_BUCKET=market-data
--
-- =============================================================================

-- =============================================================================
-- SECTION 4: Redis (Reference)
-- =============================================================================
-- Redis is used for caching and real-time data:
--   - Session management (FastAPI sessions)
--   - Rate limiting (per-user API calls)
--   - Market data cache (gold price, indicators)
--   - Alert trigger queue (pub/sub)
--
-- Key patterns:
--   cache:gold:price        - Current gold price (TTL: 60s)
--   cache:indicators:GOLD  - Technical indicators (TTL: 300s)
--   rate:api:{user_id}     - API rate limit counter
--   session:{session_id}    - User session data
-- =============================================================================

-- =============================================================================
-- SECTION 5: Data Integrity & Constraints Notes
-- =============================================================================
-- 
-- Foreign Key ON DELETE behaviors:
--   - users(id) → portfolios(user_id): CASCADE  (delete portfolios when user deleted)
--   - users(id) → decisions(user_id): CASCADE   (delete decisions when user deleted)
--   - users(id) → alerts(user_id): CASCADE       (delete alerts when user deleted)
--   - portfolios(id) → holdings(portfolio_id): CASCADE (delete holdings when portfolio deleted)
--   - portfolios(id) → decisions(portfolio_id): SET NULL (keep decision record, just unlink)
--
-- Index Strategy:
--   - Primary keys: SERIAL (auto-managed by PostgreSQL)
--   - Foreign keys: indexed (required for JOIN performance)
--   - Unique constraints: unique indexes on username, email
--   - Common filters: partial indexes on is_active, is_executed
--   - Composite indexes: (user_id, asset) covers most query patterns
--
-- Migration Order:
--   1. ENUM types first (no dependencies)
--   2. users table (no dependencies)
--   3. portfolios table (depends on users)
--   4. portfolio_holdings table (depends on portfolios)
--   5. decisions table (depends on users, portfolios)
--   6. alerts table (depends on users)
--   7. Regular indexes
--   8. Partial indexes
--
-- Rollback (if needed):
--   DROP TABLE IF EXISTS alerts CASCADE;
--   DROP TABLE IF EXISTS decisions CASCADE;
--   DROP TABLE IF EXISTS portfolio_holdings CASCADE;
--   DROP TABLE IF EXISTS portfolios CASCADE;
--   DROP TABLE IF EXISTS users CASCADE;
--   DROP TYPE IF EXISTS alert_type;
--   DROP TYPE IF EXISTS decision_source;
--   DROP TYPE IF EXISTS decision_type;
--
-- =============================================================================
