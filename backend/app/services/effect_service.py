"""Effect analysis: correlate prompt features with engagement metrics.

Uses Athena for accurate aggregations (cache has limited sampling),
falls back to cache if Athena unavailable.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy import stats

from app.services import cache_service, athena_service

logger = logging.getLogger(__name__)


def compute_effect_analysis(metric: str = "like_count") -> dict:
    """Correlate prompt features with engagement metrics.

    Queries Athena directly for category/style performance (accurate over full dataset),
    uses local cache for feature correlation (on sampled data).
    """
    valid_metrics = {"like_count", "collect_count", "score"}
    if metric not in valid_metrics:
        metric = "like_count"

    logger.info("Computing effect analysis for metric=%s", metric)

    # --- Athena: accurate category performance ---
    cat_perf = _query_category_performance(metric)
    style_perf = _query_style_performance(metric)
    hit_thresholds = _query_hit_thresholds(metric)
    hit_prompts = _query_hit_prompts(metric, hit_thresholds.get("p90", 0))

    # --- Local cache: feature correlations (engaged-only, Spearman) ---
    corr_data = _compute_feature_correlations(metric)

    result = {
        "metric": metric,
        "feature_correlations": corr_data.get("correlations", []),
        "correlation_insights": corr_data.get("insights", []),
        "correlation_method": corr_data.get("method", ""),
        "correlation_sample_size": corr_data.get("sample_size", 0),
        "significant_count": corr_data.get("significant_count", 0),
        "feature_heatmap": corr_data.get("heatmap", {}),
        "category_performance": cat_perf,
        "style_performance": style_perf,
        "hit_thresholds": {metric: hit_thresholds},
        "hit_prompts": hit_prompts,
        "total_prompts": 0,
        "prompts_with_engagement": 0,
    }

    # Get totals from Athena
    try:
        total_sql = f"""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN TRY_CAST({metric} AS BIGINT) > 0 THEN 1 ELSE 0 END) as engaged
            FROM silver.clean_tripo_project
            WHERE prompt IS NOT NULL AND prompt != ''
        """
        r = athena_service.run_query(total_sql)
        if r["rows"]:
            result["total_prompts"] = int(r["rows"][0].get("total", 0) or 0)
            result["prompts_with_engagement"] = int(r["rows"][0].get("engaged", 0) or 0)
    except Exception as e:
        logger.warning("Total query failed: %s", e)

    cache_service.save_analysis_result(0, f"effect_{metric}", result)
    logger.info("Effect analysis done: %d cat, %d style, %d hits",
                len(cat_perf), len(style_perf), len(hit_prompts))
    return result


def _query_category_performance(metric: str) -> list:
    """Query avg engagement per category from Athena."""
    try:
        sql = f"""
            SELECT llm_category AS category,
                   CAST(SUM(TRY_CAST({metric} AS BIGINT)) AS DOUBLE) / COUNT(*) AS avg,
                   SUM(TRY_CAST({metric} AS BIGINT)) AS total,
                   COUNT(*) AS count
            FROM silver.clean_tripo_project
            WHERE prompt IS NOT NULL AND prompt != ''
              AND llm_category IS NOT NULL AND llm_category != ''
            GROUP BY llm_category
            ORDER BY avg DESC
            LIMIT 20
        """
        r = athena_service.run_query(sql)
        return [
            {
                "category": row.get("category"),
                "avg": round(float(row.get("avg") or 0), 4),
                "total": int(row.get("total") or 0),
                "count": int(row.get("count") or 0),
            }
            for row in r["rows"]
        ]
    except Exception as e:
        logger.warning("Category performance query failed: %s", e)
        return []


def _query_style_performance(metric: str) -> list:
    """Query avg engagement per style from Athena."""
    try:
        sql = f"""
            SELECT llm_style AS style,
                   CAST(SUM(TRY_CAST({metric} AS BIGINT)) AS DOUBLE) / COUNT(*) AS avg,
                   SUM(TRY_CAST({metric} AS BIGINT)) AS total,
                   COUNT(*) AS count
            FROM silver.clean_tripo_project
            WHERE prompt IS NOT NULL AND prompt != ''
              AND llm_style IS NOT NULL AND llm_style != ''
            GROUP BY llm_style
            ORDER BY avg DESC
            LIMIT 20
        """
        r = athena_service.run_query(sql)
        return [
            {
                "style": row.get("style"),
                "avg": round(float(row.get("avg") or 0), 4),
                "total": int(row.get("total") or 0),
                "count": int(row.get("count") or 0),
            }
            for row in r["rows"]
        ]
    except Exception as e:
        logger.warning("Style performance query failed: %s", e)
        return []


def _query_hit_thresholds(metric: str) -> dict:
    """Get P75/P90/P95/P99 of engagement metric from Athena."""
    try:
        sql = f"""
            SELECT
                APPROX_PERCENTILE(TRY_CAST({metric} AS DOUBLE), 0.75) AS p75,
                APPROX_PERCENTILE(TRY_CAST({metric} AS DOUBLE), 0.90) AS p90,
                APPROX_PERCENTILE(TRY_CAST({metric} AS DOUBLE), 0.95) AS p95,
                APPROX_PERCENTILE(TRY_CAST({metric} AS DOUBLE), 0.99) AS p99
            FROM silver.clean_tripo_project
            WHERE prompt IS NOT NULL AND prompt != ''
              AND TRY_CAST({metric} AS BIGINT) > 0
        """
        r = athena_service.run_query(sql)
        if r["rows"]:
            row = r["rows"][0]
            return {
                "p75": round(float(row.get("p75") or 0), 1),
                "p90": round(float(row.get("p90") or 0), 1),
                "p95": round(float(row.get("p95") or 0), 1),
                "p99": round(float(row.get("p99") or 0), 1),
            }
    except Exception as e:
        logger.warning("Hit thresholds query failed: %s", e)
    return {"p75": 0, "p90": 0, "p95": 0, "p99": 0}


def _query_hit_prompts(metric: str, p90: float) -> list:
    """Get top-performing prompts from Athena."""
    threshold = max(p90, 1)  # at least 1
    try:
        sql = f"""
            SELECT project_id, prompt, llm_category, llm_style,
                   TRY_CAST(like_count AS BIGINT) AS like_count,
                   TRY_CAST(collect_count AS BIGINT) AS collect_count,
                   TRY_CAST(score AS DOUBLE) AS score,
                   display_image
            FROM silver.clean_tripo_project
            WHERE prompt IS NOT NULL AND prompt != ''
              AND TRY_CAST({metric} AS BIGINT) >= {int(threshold)}
            ORDER BY TRY_CAST({metric} AS BIGINT) DESC
            LIMIT 50
        """
        r = athena_service.run_query(sql)
        return [
            {
                "project_id": row.get("project_id"),
                "prompt": str(row.get("prompt", ""))[:200],
                "like_count": int(row.get("like_count") or 0),
                "collect_count": int(row.get("collect_count") or 0),
                "score": float(row["score"]) if row.get("score") else None,
                "llm_category": row.get("llm_category"),
                "llm_style": row.get("llm_style"),
                "display_image": row.get("display_image"),
            }
            for row in r["rows"]
        ]
    except Exception as e:
        logger.warning("Hit prompts query failed: %s", e)
        return []


def _compute_feature_correlations(metric: str) -> dict:
    """Compute feature-engagement correlations.

    Strategy:
    1. Filter to engaged-only samples (metric > 0) for meaningful correlations
    2. Log-transform metric to handle extreme skew
    3. Use Spearman rank correlation (robust to non-normality)
    4. Only report p < 0.05 as significant
    5. Add richer features for better discrimination
    6. Generate business insights from significant correlations
    """
    try:
        # Try Athena for engaged-only data (much larger sample than local cache)
        df = _fetch_engaged_from_athena(metric)
        if df is None or df.empty:
            df = cache_service.get_prompts_df()
        if df.empty:
            return {"correlations": [], "insights": [], "sample_size": 0, "heatmap": {}}

        df[metric] = pd.to_numeric(df[metric], errors="coerce").fillna(0)

        # --- Feature engineering ---
        prompt_str = df["prompt"].fillna("")
        df["prompt_length"] = prompt_str.str.len()
        df["word_count"] = prompt_str.str.split().str.len()
        df["is_long_prompt"] = (df["prompt_length"] > 100).astype(int)
        df["is_very_long"] = (df["prompt_length"] > 300).astype(int)
        df["has_color"] = (df["llm_color"].fillna("") != "").astype(int)
        df["has_style"] = (df["llm_style"].fillna("") != "").astype(int)
        df["has_category"] = (df["llm_category"].fillna("") != "").astype(int)
        df["has_keyword"] = (df["llm_keyword"].fillna("") != "").astype(int)
        df["has_detail"] = (
            prompt_str.str.contains(r"detail|realistic|high.?quality|精细|细节|高质量",
                                    case=False, regex=True)
        ).astype(int)
        df["has_material"] = (
            prompt_str.str.contains(r"metal|wood|glass|stone|fabric|texture|材质|金属|木|玻璃",
                                    case=False, regex=True)
        ).astype(int)
        df["has_pose"] = (
            prompt_str.str.contains(r"pose|stand|sit|walk|run|动态|姿势|站|坐",
                                    case=False, regex=True)
        ).astype(int)

        feature_labels = {
            "prompt_length": "Prompt 长度（字符数）",
            "word_count": "词数",
            "is_long_prompt": "长 Prompt（>100字符）",
            "is_very_long": "超长 Prompt（>300字符）",
            "has_color": "含颜色描述",
            "has_style": "含风格标签",
            "has_category": "含类别标签",
            "has_keyword": "含关键词",
            "has_detail": "含细节/质量描述",
            "has_material": "含材质描述",
            "has_pose": "含姿势/动态描述",
        }
        feature_cols = list(feature_labels.keys())

        # --- Filter to engaged samples only ---
        engaged = df[df[metric] > 0].copy()
        all_count = len(df)
        engaged_count = len(engaged)

        if engaged_count < 10:
            logger.warning("Too few engaged samples (%d) for correlation", engaged_count)
            return {
                "correlations": [],
                "insights": [f"有效样本不足（仅 {engaged_count} 条有{metric}数据），无法计算有意义的相关性"],
                "sample_size": engaged_count,
                "heatmap": {},
            }

        # Log-transform metric
        engaged["log_metric"] = np.log1p(engaged[metric].astype(float))

        # --- Spearman correlations ---
        correlations = []
        for col in feature_cols:
            label = feature_labels[col]
            col_values = engaged[col].fillna(0).astype(float)
            metric_values = engaged["log_metric"]

            if col_values.std() == 0:
                continue

            corr, p_val = stats.spearmanr(col_values, metric_values)

            # Confidence interval via Fisher z-transform
            n = len(col_values)
            z = np.arctanh(corr)
            se = 1 / np.sqrt(n - 3) if n > 3 else 0
            ci_lo = float(np.tanh(z - 1.96 * se))
            ci_hi = float(np.tanh(z + 1.96 * se))

            significant = bool(p_val < 0.05)

            # Effect size: compare engaged samples with/without the feature
            effect_pct = None
            if col.startswith("has_") or col.startswith("is_"):
                with_feat = engaged[engaged[col] == 1][metric].mean()
                without_feat = engaged[engaged[col] == 0][metric].mean()
                if without_feat > 0:
                    effect_pct = round((with_feat - without_feat) / without_feat * 100, 1)

            correlations.append({
                "feature": label,
                "correlation": round(float(corr), 4),
                "p_value": round(float(p_val), 6),
                "ci_low": round(ci_lo, 4),
                "ci_high": round(ci_hi, 4),
                "significant": significant,
                "direction": "positive" if corr > 0 else "negative" if corr < 0 else "none",
                "effect_pct": effect_pct,
            })

        correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)

        # --- Heatmap: feature-feature correlation matrix ---
        heatmap_data = {}
        feat_df = engaged[feature_cols].fillna(0).astype(float)
        corr_matrix = feat_df.corr(method="spearman")
        heatmap_features = [feature_labels[c] for c in feature_cols]
        heatmap_values = []
        for i, c1 in enumerate(feature_cols):
            for j, c2 in enumerate(feature_cols):
                heatmap_values.append([i, j, round(float(corr_matrix.loc[c1, c2]), 3)])
        heatmap_data = {
            "features": heatmap_features,
            "values": heatmap_values,
        }

        # --- Business insights ---
        insights = []
        sig_correlations = [c for c in correlations if c["significant"]]
        top_positive = [c for c in sig_correlations if c["direction"] == "positive"]
        top_negative = [c for c in sig_correlations if c["direction"] == "negative"]

        if top_positive:
            best = top_positive[0]
            insights.append(
                f"最强正相关特征：「{best['feature']}」(r={best['correlation']}, p={best['p_value']})"
                + (f"，含此特征的 Prompt 平均{metric}提升 {best['effect_pct']}%" if best.get("effect_pct") else "")
            )
        if top_negative:
            worst = top_negative[0]
            insights.append(
                f"最强负相关特征：「{worst['feature']}」(r={worst['correlation']}, p={worst['p_value']})"
            )
        if not sig_correlations:
            insights.append("当前样本中未发现统计显著的相关特征（p<0.05），可能需要更大样本量")

        # Actionable suggestions
        suggestions = []
        for c in top_positive[:3]:
            feat = c["feature"]
            if "细节" in feat or "质量" in feat:
                suggestions.append("在 Prompt 中加入「detailed」「high-quality」等质量描述词")
            elif "材质" in feat:
                suggestions.append("指定材质（metal, wood, glass 等），提升生成效果")
            elif "颜色" in feat:
                suggestions.append("添加颜色描述，让生成结果更具体")
            elif "姿势" in feat or "动态" in feat:
                suggestions.append("描述角色姿态和动作，增加表现力")
            elif "长" in feat:
                suggestions.append("写更长、更详细的 Prompt 描述")
            elif "风格" in feat:
                suggestions.append("明确指定风格（realistic, cartoon 等）")
        if suggestions:
            insights.append("优化建议：" + "；".join(suggestions))

        return {
            "correlations": correlations,
            "significant_count": len(sig_correlations),
            "insights": insights,
            "sample_size": engaged_count,
            "total_prompts": all_count,
            "method": "Spearman 秩相关（log 变换后）",
            "heatmap": heatmap_data,
        }

    except Exception as e:
        logger.error("Feature correlation failed: %s", e, exc_info=True)
        return {"correlations": [], "insights": [f"计算失败：{e}"], "sample_size": 0, "heatmap": {}}


def _fetch_engaged_from_athena(metric: str, limit: int = 5000) -> pd.DataFrame | None:
    """Fetch engaged prompts (metric > 0) directly from Athena for correlation analysis."""
    try:
        sql = f"""
            SELECT prompt, llm_category, llm_style, llm_color, llm_keyword,
                   TRY_CAST(like_count AS BIGINT) AS like_count,
                   TRY_CAST(collect_count AS BIGINT) AS collect_count,
                   TRY_CAST(score AS DOUBLE) AS score
            FROM silver.clean_tripo_project
            WHERE prompt IS NOT NULL AND prompt != ''
              AND TRY_CAST({metric} AS BIGINT) > 0
            LIMIT {limit}
        """
        result = athena_service.run_query(sql)
        if not result["rows"]:
            return None
        df = pd.DataFrame(result["rows"])
        # Convert types
        for col in ["like_count", "collect_count"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0)
        logger.info("Fetched %d engaged prompts from Athena for correlation", len(df))
        return df
    except Exception as e:
        logger.warning("Athena engaged fetch failed: %s", e)
        return None
