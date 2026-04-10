-- Mart: prompt dimension table with features
SELECT
    project_id,
    user_id,
    prompt,
    name,
    llm_category,
    llm_style,
    llm_color,
    llm_use_case,
    llm_keyword,
    llm_object,
    like_count,
    collect_count,
    score,
    display_image,
    prompt_length,
    word_count,
    has_color,
    has_style,
    -- Quality tiers
    CASE
        WHEN like_count >= 10 THEN 'viral'
        WHEN like_count >= 3 THEN 'popular'
        WHEN like_count >= 1 THEN 'liked'
        ELSE 'standard'
    END AS engagement_tier,
    -- Prompt complexity
    CASE
        WHEN word_count >= 30 THEN 'detailed'
        WHEN word_count >= 10 THEN 'moderate'
        ELSE 'simple'
    END AS complexity_tier,
    pt,
    created_at
FROM {{ ref('stg_prompts') }}
