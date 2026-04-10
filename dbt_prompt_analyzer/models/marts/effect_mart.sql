-- Mart: daily metrics for effect analysis and dashboards
SELECT
    pt AS date,
    COUNT(*) AS total_prompts,
    COUNT(DISTINCT user_id) AS unique_users,
    AVG(like_count) AS avg_likes,
    SUM(CAST(like_count AS BIGINT)) AS total_likes,
    AVG(collect_count) AS avg_collects,
    AVG(score) AS avg_score,
    AVG(prompt_length) AS avg_prompt_length,
    SUM(CASE WHEN like_count >= 3 THEN 1 ELSE 0 END) AS popular_prompts,
    SUM(CASE WHEN has_color = 1 THEN 1 ELSE 0 END) AS prompts_with_color,
    SUM(CASE WHEN has_style = 1 THEN 1 ELSE 0 END) AS prompts_with_style
FROM {{ ref('stg_prompts') }}
WHERE pt IS NOT NULL
GROUP BY pt
ORDER BY pt
