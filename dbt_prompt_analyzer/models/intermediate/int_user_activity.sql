-- Intermediate: per-user activity aggregation
SELECT
    user_id,
    COUNT(*) AS total_prompts,
    COUNT(DISTINCT pt) AS active_days,
    MIN(pt) AS first_seen,
    MAX(pt) AS last_seen,
    AVG(CAST(like_count AS DOUBLE)) AS avg_like_count,
    SUM(CAST(like_count AS BIGINT)) AS total_like_count,
    SUM(CAST(collect_count AS BIGINT)) AS total_collect_count,
    AVG(CAST(score AS DOUBLE)) AS avg_score,
    AVG(LENGTH(prompt)) AS avg_prompt_length,
    AVG(CARDINALITY(SPLIT(prompt, ' '))) AS avg_word_count
FROM {{ ref('stg_prompts') }}
WHERE user_id IS NOT NULL AND user_id != ''
GROUP BY user_id
