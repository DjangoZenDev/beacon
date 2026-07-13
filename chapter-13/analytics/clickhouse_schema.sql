
-- Beacon v0.13 — ClickHouse Analytical Schema
-- Multi-region: each region hosts its own ClickHouse cluster.
-- Federated queries use Distributed tables for cross-region aggregation.
-- Chapter 13, Principle: "Regional analytics, federated queries."

CREATE DATABASE IF NOT EXISTS beacon_analytics;
USE beacon_analytics;

CREATE TABLE beacon_analytics.page_views (
    event_time DateTime64(3),
    page_id UInt64, page_title String, page_slug String,
    user_id UInt64, user_username String,
    user_department LowCardinality(String),
    organization_id UInt32, referrer String,
    duration_seconds UInt32, region LowCardinality(String),
    day Date MATERIALIZED toDate(event_time)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (page_id, event_time)
SETTINGS index_granularity = 8192;

CREATE MATERIALIZED VIEW beacon_analytics.daily_dept_views
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (day, user_department, page_id, region)
AS SELECT day, user_department, page_id, page_title, region,
    count() AS view_count, sum(duration_seconds) AS total_duration_seconds,
    uniqExact(user_id) AS unique_viewers
FROM beacon_analytics.page_views
GROUP BY day, user_department, page_id, page_title, region;

CREATE MATERIALIZED VIEW beacon_analytics.weekly_active_users_mv
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(week_start)
ORDER BY (week_start, user_department, region)
AS SELECT toMonday(day) AS week_start, user_department, region,
    uniqState(user_id) AS wau_state, countState() AS view_count_state
FROM beacon_analytics.page_views
GROUP BY week_start, user_department, region;
