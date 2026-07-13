-- Apache Iceberg Table Setup for Beacon Data Lake
--
-- Iceberg provides a table format over Parquet files in object storage
-- (S3, GCS). This enables ACID transactions, schema evolution, time
-- travel queries, and partition evolution on the data lake.
--
-- Run via Trino or Spark SQL against an Iceberg catalog.
--
-- Chapter 12, Principle 5: "Data retention is a tiered strategy."
--   Iceberg handles warm data (historical archive) while ClickHouse
--   handles hot data (last 90 days).

-- Create the Iceberg schema if using Trino.
CREATE SCHEMA IF NOT EXISTS iceberg.beacon
WITH (location = 's3://beacon-data-lake/iceberg/');

-- Create the page_views Iceberg table.
-- Partitioned by month for efficient time-range queries.
CREATE TABLE IF NOT EXISTS iceberg.beacon.page_views (
    event_time TIMESTAMP(3),
    page_id BIGINT,
    page_title VARCHAR,
    page_slug VARCHAR,
    user_id BIGINT,
    user_username VARCHAR,
    user_department VARCHAR,
    organization_id INTEGER,
    referrer VARCHAR,
    duration_seconds INTEGER,
    -- Iceberg partition: derived from event_time.
    event_month VARCHAR
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['event_month'],
    -- Iceberg v2 for row-level deletes (GDPR compliance).
    format_version = 2
);

-- ── Time Travel Queries ──────────────────────────────────────────

-- Query the table as it existed 7 days ago:
-- SELECT * FROM iceberg.beacon.page_views
-- FOR TIMESTAMP AS OF (CURRENT_TIMESTAMP - INTERVAL '7' DAY);

-- Query a specific snapshot by snapshot ID:
-- SELECT * FROM iceberg.beacon.page_views
-- FOR VERSION AS OF 1234567890123456789;

-- ── Schema Evolution ─────────────────────────────────────────────

-- Add a column without rewriting existing data:
-- ALTER TABLE iceberg.beacon.page_views
-- ADD COLUMN device_type VARCHAR;

-- Change partition scheme without rewriting data:
-- ALTER TABLE iceberg.beacon.page_views
-- SET PROPERTIES partitioning = ARRAY['event_month', 'user_department'];

-- ── Compaction ───────────────────────────────────────────────────

-- Merge small files into optimal sizes for query performance.
-- Run periodically (e.g., daily) via Spark or Trino.
-- CALL system.rewrite_data_files('iceberg.beacon.page_views');
