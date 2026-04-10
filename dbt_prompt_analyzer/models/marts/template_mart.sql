-- Mart: high-engagement prompt templates (candidates for template library)
WITH ranked AS (
    SELECT
        project_id,
        user_id,
        prompt,
        llm_category,
        llm_style,
        llm_color,
        llm_use_case,
        like_count,
        collect_count,
        score,
        prompt_length,
        word_count,
        display_image,
        pt,
        ROW_NUMBER() OVER (
            PARTITION BY llm_category, llm_style
            ORDER BY like_count DESC, score DESC
        ) AS rank_in_group
    FROM {{ ref('stg_prompts') }}
    WHERE like_count >= 1
)
SELECT * FROM ranked
WHERE rank_in_group <= 10
