
-- Beacon v0.12 — ClickHouse Analytical Schema
--
-- Column-oriented OLAP store for Beacon analytics.
-- Denormalized, partitioned by month, ordered by (page_id, event_time).
-- LowCardinality() reduces storage for low-cardinality columns by 95%.
--
-- Chapter 12, Principle 2: "Column-oriented storage changes the economics."
--   A query that takes 78s on PostgreSQL takes 0.5s on ClickHouse.

CREATE DATABASE IF NOT EXISTS beacon_analytics;

USE beacon_analytics;

CREATE TABLE beacon_analytics.page_views (
    event_time DateTime64(3),
    page_id UInt64,
    page_title String,
    page_slug String,
    user_id UInt64,
    user_username String,
    user_department LowCardinality(String),
    organization_id UInt32,
    referrer String,
    duration_seconds UInt32,
    day Date MATERIALIZED toDate(event_time)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (page_id, event_time)
SETTINGS index_granularity = 8192;

-- ── Materialized Views for Common Aggregations ──────────────────

-- Daily page views by department.
CREATE MATERIALIZED VIEW beacon_analytics.daily_dept_views
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (day, user_department, page_id)
AS SELECT
    day,
    user_department,
    page_id,
    page_title,
    count() AS view_count,
    sum(duration_seconds) AS total_duration_seconds,
    uniqExact(user_id) AS unique_viewers
FROM beacon_analytics.page_views
GROUP BY day, user_department, page_id, page_title;

-- Weekly active users by department (the dashboard query from Ch12).
CREATE MATERIALIZED VIEW beacon_analytics.weekly_active_users_mv
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(week_start)
ORDER BY (week_start, user_department)
AS SELECT
    toMonday(day) AS week_start,
    user_department,
    uniqState(user_id) AS wau_state,
    countState() AS view_count_state
FROM beacon_analytics.page_views
GROUP BY week_start, user_department;

-- Query the WAU view:
-- SELECT
--     week_start,
--     user_department,
--     uniqMerge(wau_state) AS weekly_active_users,
--     countMerge(view_count_state) AS total_page_views
-- FROM beacon_analytics.weekly_active_users_mv
-- WHERE week_start >= today() - INTERVAL 90 DAY
-- GROUP BY week_start, user_department
-- ORDER BY week_start DESC;
