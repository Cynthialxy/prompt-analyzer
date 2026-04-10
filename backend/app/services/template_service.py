"""Hot template mining: extract high-value prompt templates from engagement data."""
from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime

import numpy as np
import pandas as pd

from app.config import settings
from app.services import cache_service, llm_service, athena_service

logger = logging.getLogger(__name__)


def mine_hot_templates(metric: str = "like_count", top_k: int = None) -> dict:
    """Mine hot prompt templates from high-engagement prompts.

    Steps:
    1. Filter prompts by engagement threshold (like_count >= settings.template_min_likes)
    2. Cluster by category + style
    3. Extract structural patterns: [style] [object] [detail] [render]
    4. For each cluster, call LLM to synthesize a reusable template

    Returns:
        {
          "templates": [
            {
              "id": 1,
              "category": "character_design",
              "style": "anime",
              "pattern": "[style] [character] with [detail], [rendering]",
              "template_prompt": "An anime-style warrior with glowing sword, cel-shaded, dynamic pose",
              "examples": ["...", "..."],
              "avg_likes": 12.3,
              "avg_score": 82,
              "usage_count": 45
            }
          ],
          "total_hits": 450,
          "hit_threshold": {"metric": "like_count", "value": 1}
        }
    """
    if top_k is None:
        top_k = settings.template_max_templates

    # Fetch engaged prompts from Athena (local cache is too small)
    df = _fetch_engaged_from_athena(metric, min_value=1, limit=3000)
    if df is None or df.empty:
        df = cache_service.get_prompts_df()
    if df is None or df.empty:
        return {"error": "No data"}

    # Ensure numeric
    df[metric] = pd.to_numeric(df[metric], errors="coerce").fillna(0)
    engaged = df[df[metric] > 0]
    if len(engaged) == 0:
        engaged = df

    # Use P90 to define "hit"
    if (engaged[metric] > 0).any():
        p90 = float(np.percentile(engaged[metric][engaged[metric] > 0], 90))
    else:
        p90 = 0

    hits = engaged[engaged[metric] >= p90] if p90 > 0 else engaged.head(100)
    logger.info("Hot template mining: %d hit prompts (threshold=%.1f)", len(hits), p90)

    # Cluster by (category, style)
    templates: list = []
    grouped = hits.groupby(
        [hits["llm_category"].fillna("unknown"), hits["llm_style"].fillna("unknown")]
    )

    tid = 0
    for (category, style), group in grouped:
        if category == "unknown" or style == "unknown":
            continue

        examples = group.nlargest(5, metric)["prompt"].tolist()[:5]
        examples = [e for e in examples if e and str(e).strip()]
        if not examples:
            continue

        pattern = _extract_pattern(examples, category, style)
        template_prompt = _synthesize_template(examples, category, style)

        templates.append({
            "id": tid,
            "category": category,
            "style": style,
            "pattern": pattern,
            "template_prompt": template_prompt,
            "examples": [str(e)[:200] for e in examples],
            "avg_likes": round(float(group["like_count"].fillna(0).mean()), 2),
            "avg_collects": round(float(group["collect_count"].fillna(0).mean()), 2),
            "avg_score": round(float(pd.to_numeric(group.get("score", 0), errors="coerce").fillna(0).mean() or 0), 2),
            "usage_count": int(len(group)),
        })
        tid += 1

    # Sort by avg_likes desc
    templates.sort(key=lambda t: t["avg_likes"], reverse=True)
    templates = templates[:top_k]

    result = {
        "templates": templates,
        "total_hits": int(len(hits)),
        "hit_threshold": {"metric": metric, "value": round(p90, 1)},
        "total_templates": len(templates),
        "computed_at": datetime.now().isoformat(),
    }
    cache_service.save_analysis_result(0, "hot_templates", result)
    logger.info("Mined %d hot templates", len(templates))
    return result


def _extract_pattern(examples: list, category: str, style: str) -> str:
    """Extract a structural pattern from example prompts."""
    if not examples:
        return f"[{style}] [{category}] [detail] [render]"

    # Simple heuristic: look for common tokens across examples
    all_words = []
    for ex in examples:
        words = re.findall(r"\w+", str(ex).lower())
        all_words.extend(words)

    common = [w for w, c in Counter(all_words).most_common(5) if len(w) > 3]
    common_str = " + ".join(common[:3]) if common else "detail"
    return f"[{style}] [{category}] [{common_str}] [rendering]"


def _synthesize_template(examples: list, category: str, style: str) -> str:
    """Synthesize a reusable template from examples.

    Uses the best (first) example as the template. LLM synthesis was removed
    because it adds 30+ API calls per mining run and doesn't improve quality
    significantly for template surfacing.
    """
    if not examples:
        return f"{style} {category}"
    # Use the top-performing example directly as the template
    return str(examples[0])[:300]


def _fetch_engaged_from_athena(metric: str, min_value: int = 1, limit: int = 3000):
    """Fetch high-engagement prompts from Athena for template mining."""
    try:
        sql = f"""
            SELECT project_id, prompt, llm_category, llm_style, llm_color, llm_use_case,
                   TRY_CAST(like_count AS BIGINT) AS like_count,
                   TRY_CAST(collect_count AS BIGINT) AS collect_count,
                   TRY_CAST(score AS DOUBLE) AS score,
                   display_image
            FROM silver.clean_tripo_project
            WHERE prompt IS NOT NULL AND prompt != ''
              AND TRY_CAST({metric} AS BIGINT) >= {min_value}
            ORDER BY TRY_CAST({metric} AS BIGINT) DESC
            LIMIT {limit}
        """
        result = athena_service.run_query(sql)
        if not result["rows"]:
            return None
        df = pd.DataFrame(result["rows"])
        for col in ["like_count", "collect_count"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0)
        logger.info("Fetched %d engaged prompts from Athena for template mining", len(df))
        return df
    except Exception as e:
        logger.warning("Athena fetch for templates failed: %s", e)
        return None
