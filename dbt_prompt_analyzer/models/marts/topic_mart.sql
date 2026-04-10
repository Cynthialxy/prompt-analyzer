-- Mart: topic aggregation by category + style
SELECT
    llm_category,
    llm_style,
    COUNT(*) AS prompt_count,
    AVG(like_count) AS avg_likes,
    AVG(collect_count) AS avg_collects,
    AVG(score) AS avg_score,
    AVG(prompt_length) AS avg_prompt_length,
    AVG(word_count) AS avg_word_count,
    SUM(CASE WHEN like_count >= 3 THEN 1 ELSE 0 END) AS popular_count,
    CAST(SUM(CASE WHEN like_count >= 3 THEN 1 ELSE 0 END) AS DOUBLE) / NULLIF(COUNT(*), 0) AS popular_rate,
    MIN(pt) AS first_date,
    MAX(pt) AS last_date
FROM {{ ref('stg_prompts') }}
WHERE llm_category IS NOT NULL AND llm_category != ''
GROUP BY llm_category, llm_style
