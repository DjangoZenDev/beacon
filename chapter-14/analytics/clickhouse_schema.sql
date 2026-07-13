-- Beacon v0.14 ClickHouse Schema (carried from Ch13, adds region column)
CREATE DATABASE IF NOT EXISTS beacon_analytics; USE beacon_analytics;
CREATE TABLE beacon_analytics.page_views (
    event_time DateTime64(3), page_id UInt64, page_title String, page_slug String,
    user_id UInt64, user_username String, user_department LowCardinality(String),
    organization_id UInt32, referrer String, duration_seconds UInt32,
    region LowCardinality(String), day Date MATERIALIZED toDate(event_time)
) ENGINE = MergeTree() PARTITION BY toYYYYMM(day) ORDER BY (page_id, event_time) SETTINGS index_granularity = 8192;
