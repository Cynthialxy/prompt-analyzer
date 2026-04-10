-- Mart: user dimension table with segmentation
WITH activity AS (
    SELECT * FROM {{ ref('int_user_activity') }}
),
segments AS (
    SELECT
        *,
        CASE
            WHEN total_prompts >= 10 AND active_days >= 5 THEN 'power_user'
            WHEN total_prompts >= 3 AND active_days >= 2 THEN 'regular'
            WHEN total_prompts < 3 THEN 'casual'
            ELSE 'casual'
        END AS segment,
        CAST(total_prompts AS DOUBLE) / NULLIF(active_days, 0) AS avg_prompts_per_day
    FROM activity
)
SELECT * FROM segments
