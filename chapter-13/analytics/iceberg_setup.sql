
-- Apache Iceberg Table Setup for Beacon Data Lake (v0.13)
-- Multi-region: Iceberg tables in S3 serve as global archive.
-- Chapter 12, Principle 5: "Data retention is a tiered strategy."

CREATE SCHEMA IF NOT EXISTS iceberg.beacon
WITH (location = 's3://beacon-data-lake/iceberg/');

CREATE TABLE IF NOT EXISTS iceberg.beacon.page_views (
    event_time TIMESTAMP(3), page_id BIGINT, page_title VARCHAR,
    page_slug VARCHAR, user_id BIGINT, user_username VARCHAR,
    user_department VARCHAR, organization_id INTEGER,
    referrer VARCHAR, duration_seconds INTEGER,
    region VARCHAR, event_month VARCHAR
)
WITH (format = 'PARQUET', partitioning = ARRAY['event_month'], format_version = 2);
