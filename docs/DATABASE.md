# Gold Analysis - Database Architecture

## Overview

This document describes the complete database architecture for the gold-analysis-core project.

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Primary DB | PostgreSQL 14+ | Relational data: users, portfolios, decisions, alerts |
| Time-Series DB | InfluxDB | Market data: gold price, indicators, signals |
| Cache | Redis | Sessions, rate limiting, market data cache |
| ORM | SQLAlchemy 2.0 | Python ORM with async support |
| Migration | Alembic | Database schema versioning |

## PostgreSQL Schema

### Entity Relationship Diagram

```
┌──────────────┐     ┌──────────────────┐     ┌───────────────────────┐
│    users     │────<│   portfolios     │────<│  portfolio_holdings   │
│              │ 1:N │                  │ 1:N │                       │
└──────┬───────┘     └──────────────────┘     └───────────────────────┘
       │ 1:N                  │
       │                     │ 1:N (SET NULL)
       │                     ▼
       │            ┌─────────────────┐
       ├───────────>│    decisions    │
       │ 1:N        │                 │
       │            └─────────────────┘
       │ 1:N
       ▼
┌──────────────────┐
│      alerts      │
└──────────────────┘
```

### Table: users

Core user account table for authentication and profile.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-increment ID |
| username | VARCHAR(50) | UNIQUE, NOT NULL | Login username |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Email address |
| hashed_password | VARCHAR(255) | NOT NULL | Bcrypt hashed password |
| display_name | VARCHAR(100) | | Display name |
| avatar_url | VARCHAR(500) | | Avatar image URL |
| bio | TEXT | | User biography |
| timezone | VARCHAR(50) | DEFAULT 'Asia/Taipei' | IANA timezone |
| language | VARCHAR(10) | DEFAULT 'zh-TW' | Preferred language |
| is_active | BOOLEAN | DEFAULT TRUE | Account active flag |
| is_verified | BOOLEAN | DEFAULT FALSE | Email verified |
| is_premium | BOOLEAN | DEFAULT FALSE | Premium subscription |
| created_at | TIMESTAMP TZ | DEFAULT NOW() | Account creation time |
| updated_at | TIMESTAMP TZ | DEFAULT NOW() | Last update time |
| last_login | TIMESTAMP TZ | | Last login time |

**Indexes:**
- `idx_users_username` - Username lookup
- `idx_users_email` - Email lookup
- `idx_users_is_active` - Active user filter (partial)

### Table: portfolios

Investment portfolio table.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-increment ID |
| user_id | INTEGER | FK → users(id), ON DELETE CASCADE | Owner user |
| name | VARCHAR(100) | NOT NULL | Portfolio name |
| description | VARCHAR(500) | | Portfolio description |
| initial_capital | DOUBLE PRECISION | DEFAULT 0 | Starting capital (USD) |
| current_value | DOUBLE PRECISION | DEFAULT 0 | Current portfolio value |
| created_at | TIMESTAMP TZ | DEFAULT NOW() | Creation time |
| updated_at | TIMESTAMP TZ | DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_portfolios_user` - User's portfolio lookup

### Table: portfolio_holdings

Individual asset positions within a portfolio.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-increment ID |
| portfolio_id | INTEGER | FK → portfolios(id), ON DELETE CASCADE | Parent portfolio |
| asset_type | VARCHAR(20) | NOT NULL | Asset code: GOLD, DXY, BTC, USDT |
| quantity | DOUBLE PRECISION | NOT NULL, DEFAULT 0 | Position size |
| avg_cost | DOUBLE PRECISION | NOT NULL, DEFAULT 0 | Average cost per unit |
| current_price | DOUBLE PRECISION | | Latest market price |
| market_value | DOUBLE PRECISION | | Position market value |
| created_at | TIMESTAMP TZ | DEFAULT NOW() | Creation time |
| updated_at | TIMESTAMP TZ | DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_holdings_portfolio` - Portfolio holdings lookup
- `idx_holdings_asset` - Asset type filter
- `idx_holdings_portfolio_asset` - Composite (portfolio, asset)

### Table: decisions

AI-generated trading decision records.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-increment ID |
| user_id | INTEGER | FK → users(id), ON DELETE CASCADE | Decision owner |
| portfolio_id | INTEGER | FK → portfolios(id), ON DELETE SET NULL | Associated portfolio |
| decision_type | ENUM | NOT NULL | buy, sell, hold, watch |
| source | ENUM | NOT NULL | ai_analysis, technical, fundamental, sentiment, manual |
| asset | VARCHAR(20) | NOT NULL, DEFAULT 'GOLD' | Target asset |
| signal_strength | DOUBLE PRECISION | NOT NULL | Signal strength 0.0-1.0 |
| confidence | DOUBLE PRECISION | NOT NULL | Model confidence 0.0-1.0 |
| price_target | DOUBLE PRECISION | | Target price |
| stop_loss | DOUBLE PRECISION | | Stop loss price |
| reason_zh | TEXT | | Chinese reasoning |
| reason_en | TEXT | | English reasoning |
| indicators_snapshot | TEXT | | JSON: technical indicators |
| analysis_scores | TEXT | | JSON: analysis dimension scores |
| is_executed | BOOLEAN | DEFAULT FALSE | Execution status |
| executed_at | TIMESTAMP TZ | | Execution time |
| execution_price | DOUBLE PRECISION | | Actual execution price |
| model_version | VARCHAR(50) | DEFAULT 'v1' | AI model version |
| extra_data | TEXT | | Additional JSON metadata |
| created_at | TIMESTAMP TZ | DEFAULT NOW() | Decision time |
| updated_at | TIMESTAMP TZ | DEFAULT NOW() | Last update time |

**Indexes:**
- `idx_decisions_user` - User's decisions
- `idx_decisions_portfolio` - Portfolio decisions
- `idx_decisions_asset` - Asset filter
- `idx_decisions_created` - Time-based history
- `idx_decisions_user_asset` - Composite (user, asset)
- `idx_decisions_unexecuted` - Unexecuted filter (partial)

### Table: alerts

User-defined price alerts.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | SERIAL | PRIMARY KEY | Auto-increment ID |
| user_id | INTEGER | FK → users(id), ON DELETE CASCADE | Alert owner |
| alert_type | ENUM | NOT NULL | price_above, price_below, indicator_cross, volume_spike |
| asset | VARCHAR(20) | NOT NULL | Target asset |
| target_price | DOUBLE PRECISION | NOT NULL | Target price level |
| is_active | BOOLEAN | DEFAULT TRUE | Active flag |
| created_at | TIMESTAMP TZ | DEFAULT NOW() | Creation time |
| triggered_at | TIMESTAMP TZ | | Trigger time (NULL if not triggered) |
| extra_data | VARCHAR(500) | | Additional parameters |

**Indexes:**
- `idx_alerts_user` - User's alerts
- `idx_alerts_asset` - Asset filter
- `idx_alerts_active` - Active alerts (partial)

## InfluxDB Structure

InfluxDB stores time-series market data and is not managed via SQL migrations.

### Buckets

| Bucket | Retention | Description |
|--------|-----------|-------------|
| market-data | 365d | Gold price, DXY, interest rates |
| indicators | 365d | Technical indicators |
| sentiment | 90d | Market sentiment data |
| portfolio-values | 730d | Historical valuations |

### Measurements

**gold_price:**
- Tags: `source` (live, forecast)
- Fields: `price`, `change_24h`, `volume`, `open`, `high`, `low`

**technical_indicators:**
- Tags: `symbol` (GOLD, DXY), `indicator_type` (RSI, MACD, etc.)
- Fields: `value`, `param_json`

**ai_signals:**
- Tags: `user_id`, `symbol`, `decision_type`
- Fields: `signal_strength`, `confidence`, `price_target`

### CLI Commands

```bash
# Create bucket
influx bucket create -n market-data -o gold-analysis -r 365d

# Write data
influx write -b market-data -o gold-analysis -p s \
  "gold_price,source=live price=2345.67,change_24h=0.5"
```

## Redis Keys

| Key Pattern | Type | TTL | Description |
|-------------|------|-----|-------------|
| `cache:gold:price` | String | 60s | Current gold price |
| `cache:indicators:{symbol}` | String | 300s | Technical indicators |
| `rate:api:{user_id}` | Counter | 60s | API rate limit |
| `session:{session_id}` | Hash | 24h | User session data |
| `alert:queue` | List | - | Alert trigger queue |

## Migration Guide

### Initial Setup

```bash
# Navigate to backend
cd backend

# Run migrations
alembic upgrade head

# Or manually via psql
psql -U postgres -d gold_analysis -f app/migrations/001_init.sql
```

### Check Migration Status

```bash
alembic current
alembic history
```

### Rollback (if needed)

```bash
# Rollback one step
alembic downgrade -1

# Or drop and recreate
psql -U postgres -d gold_analysis -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

### Rollback SQL Reference

```sql
-- Drop order (reverse of creation)
DROP TABLE IF EXISTS alerts CASCADE;
DROP TABLE IF EXISTS decisions CASCADE;
DROP TABLE IF EXISTS portfolio_holdings CASCADE;
DROP TABLE IF EXISTS portfolios CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TYPE IF EXISTS alert_type;
DROP TYPE IF EXISTS decision_source;
DROP TYPE IF EXISTS decision_type;
```

## Environment Variables

```bash
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=gold_analysis
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<password>

# InfluxDB
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=<token>
INFLUXDB_ORG=gold-analysis
INFLUXDB_BUCKET=market-data

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

## Query Examples

### Get user's latest decisions with high confidence

```sql
SELECT d.*, p.name as portfolio_name
FROM decisions d
LEFT JOIN portfolios p ON d.portfolio_id = p.id
WHERE d.user_id = $1
  AND d.confidence > 0.8
ORDER BY d.created_at DESC
LIMIT 10;
```

### Get active alerts for gold price

```sql
SELECT * FROM alerts
WHERE user_id = $1
  AND asset = 'GOLD'
  AND is_active = TRUE
  AND triggered_at IS NULL;
```

### Get portfolio with holdings summary

```sql
SELECT 
    p.name,
    p.current_value,
    COUNT(h.id) as holding_count,
    SUM(h.market_value) as total_market_value
FROM portfolios p
LEFT JOIN portfolio_holdings h ON p.id = h.portfolio_id
WHERE p.user_id = $1
GROUP BY p.id;
```

## Performance Tips

1. **Use partial indexes** for common filter patterns (active, unexecuted)
2. **Composite indexes** for multi-column queries (user_id, asset)
3. **Analyze tables** after bulk inserts: `ANALYZE table_name;`
4. **Connection pooling** via PgBouncer for high concurrency
5. **Read replicas** for analytical queries

## Backup Strategy

```bash
# Full backup
pg_dump -U postgres gold_analysis > backup_$(date +%Y%m%d).sql

# InfluxDB backup
influx backup /tmp/influx_backup -o gold-analysis
```
