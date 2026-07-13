
-- Weekly Active Users by Department (v0.13, multi-region)
{{ config(materialized='table') }}

WITH weekly_views AS (
    SELECT
        DATE_TRUNC('week', event_time) AS week,
        user_id, region,
        COUNT(*) AS page_view_count,
        SUM(duration_seconds) AS total_seconds
    FROM {{ ref('page_views') }}
    WHERE event_time >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY 1, 2, 3
),
enriched AS (
    SELECT wv.*, u.department,
        COUNT(DISTINCT wv.user_id) OVER (
            PARTITION BY wv.week, u.department, wv.region
        ) AS department_wau
    FROM weekly_views wv
    LEFT JOIN {{ ref('users') }} u ON wv.user_id = u.id
)
SELECT week, department, region,
    department_wau AS weekly_active_users,
    SUM(page_view_count) AS total_page_views,
    ROUND(SUM(total_seconds) / 3600.0, 2) AS total_hours
FROM enriched
GROUP BY 1, 2, 3, 4
ORDER BY week DESC, department
