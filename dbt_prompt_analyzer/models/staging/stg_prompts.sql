-- Staging model: clean and type-cast raw prompt data
WITH source AS (
    SELECT
        project_id,
        user_id,
        prompt,
        caption,
        name,
        from_type,
        status,
        visibility,
        llm_keyword,
        llm_object,
        llm_category,
        llm_style,
        llm_color,
        llm_use_case,
        llm_height,
        CAST(like_count AS INTEGER) AS like_count,
        CAST(collect_count AS INTEGER) AS collect_count,
        CAST(score AS DOUBLE) AS score,
        display_image,
        created_at,
        pt,
        -- Derived features
        LENGTH(prompt) AS prompt_length,
        CARDINALITY(SPLIT(prompt, ' ')) AS word_count,
        CASE WHEN llm_color IS NOT NULL AND llm_color != '' THEN 1 ELSE 0 END AS has_color,
        CASE WHEN llm_style IS NOT NULL AND llm_style != '' THEN 1 ELSE 0 END AS has_style
    FROM {{ source('silver', 'clean_tripo_project') }}
    WHERE prompt IS NOT NULL
      AND prompt != ''
      AND deleted_at IS NULL
)

SELECT * FROM source
