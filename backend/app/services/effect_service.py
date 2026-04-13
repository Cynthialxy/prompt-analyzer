"""Effect analysis: correlate prompt features with engagement metrics.

Uses cached SQLite data for all computations. Athena is no longer queried directly.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy import stats

from app.services import cache_service

logger = logging.getLogger(__name__)


def compute_effect_analysis(metric: str = "like_count") -> dict:
    """Correlate prompt features with engagement metrics using cached data."""
    valid_metrics = {"like_count", "collect_count", "score"}
    if metric not in valid_metrics:
        metric = "like_count"

    logger.info("Computing effect analysis for metric=%s from cache", metric)

    df = cache_service.get_prompts_df()
    if df.empty:
        return {
            "metric": metric,
            "feature_correlations": [],
            "correlation_insights": ["缓存中无数据，请先同步数据"],
            "correlation_method": "",
            "correlation_sample_size": 0,
            "significant_count": 0,
            "feature_heatmap": {},
            "category_performance": [],
            "style_performance": [],
            "hit_thresholds": {metric: {"p75": 0, "p90": 0, "p95": 0, "p99": 0}},
            "hit_prompts": [],
            "total_prompts": 0,
            "prompts_with_engagement": 0,
        }

    df[metric] = pd.to_numeric(df[metric], errors="coerce").fillna(0)

    total_prompts = len(df)
    prompts_with_engagement = int((df[metric] > 0).sum())

    # Sample for heavy computations to keep things fast
    SAMPLE_SIZE = 50000
    sample_df = df.sample(min(SAMPLE_SIZE, len(df)), random_state=42) if len(df) > SAMPLE_SIZE else df

    cat_perf = _compute_category_performance(df, metric)
    style_perf = _compute_style_performance(df, metric)
    hit_thresholds = _compute_hit_thresholds(df, metric)
    hit_prompts = _get_hit_prompts(df, metric, hit_thresholds.get("p90", 0))
    corr_data = _compute_feature_correlations(sample_df, metric)

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
        "total_prompts": total_prompts,
        "prompts_with_engagement": prompts_with_engagement,
    }

    cache_service.save_analysis_result(0, f"effect_{metric}", result)
    logger.info("Effect analysis done: %d cat, %d style, %d hits",
                len(cat_perf), len(style_perf), len(hit_prompts))
    return result


def _compute_category_performance(df: pd.DataFrame, metric: str) -> list:
    cat_df = df[df["llm_category"].fillna("") != ""].copy()
    if cat_df.empty:
        return []
    agg = cat_df.groupby("llm_category")[metric].agg(["mean", "sum", "count"]).reset_index()
    agg.columns = ["category", "avg", "total", "count"]
    agg = agg.sort_values("avg", ascending=False).head(20)
    return [
        {
            "category": r["category"],
            "avg": round(float(r["avg"]), 4),
            "total": int(r["total"]),
            "count": int(r["count"]),
        }
        for _, r in agg.iterrows()
    ]


def _compute_style_performance(df: pd.DataFrame, metric: str) -> list:
    style_df = df[df["llm_style"].fillna("") != ""].copy()
    if style_df.empty:
        return []
    agg = style_df.groupby("llm_style")[metric].agg(["mean", "sum", "count"]).reset_index()
    agg.columns = ["style", "avg", "total", "count"]
    agg = agg.sort_values("avg", ascending=False).head(20)
    return [
        {
            "style": r["style"],
            "avg": round(float(r["avg"]), 4),
            "total": int(r["total"]),
            "count": int(r["count"]),
        }
        for _, r in agg.iterrows()
    ]


def _compute_hit_thresholds(df: pd.DataFrame, metric: str) -> dict:
    engaged = df[df[metric] > 0][metric]
    if engaged.empty:
        return {"p75": 0, "p90": 0, "p95": 0, "p99": 0}
    return {
        "p75": round(float(np.percentile(engaged, 75)), 1),
        "p90": round(float(np.percentile(engaged, 90)), 1),
        "p95": round(float(np.percentile(engaged, 95)), 1),
        "p99": round(float(np.percentile(engaged, 99)), 1),
    }


def _get_hit_prompts(df: pd.DataFrame, metric: str, p90: float) -> list:
    threshold = max(p90, 1)
    hits = df[df[metric] >= threshold].sort_values(metric, ascending=False).head(50)
    result = []
    for _, r in hits.iterrows():
        score_val = r.get("score")
        result.append({
            "project_id": r.get("project_id"),
            "prompt": str(r.get("prompt", ""))[:200],
            "like_count": int(r.get("like_count", 0) or 0),
            "collect_count": int(r.get("collect_count", 0) or 0),
            "score": float(score_val) if score_val and not pd.isna(score_val) else None,
            "llm_category": r.get("llm_category"),
            "llm_style": r.get("llm_style"),
            "display_image": r.get("display_image"),
        })
    return result


def _compute_feature_correlations(df: pd.DataFrame, metric: str) -> dict:
    """Compute feature-engagement correlations using Spearman rank correlation."""
    try:
        # Filter to engaged-only samples
        engaged = df[df[metric] > 0].copy()
        all_count = len(df)
        engaged_count = len(engaged)

        if engaged_count < 10:
            return {
                "correlations": [],
                "insights": [f"有效样本不足（仅 {engaged_count} 条有{metric}数据），无法计算有意义的相关性"],
                "sample_size": engaged_count,
                "heatmap": {},
            }

        # Feature engineering
        prompt_str = engaged["prompt"].fillna("")
        engaged = engaged.copy()
        engaged["prompt_length"] = prompt_str.str.len()
        engaged["word_count"] = prompt_str.str.split().str.len()
        engaged["is_long_prompt"] = (engaged["prompt_length"] > 100).astype(int)
        engaged["is_very_long"] = (engaged["prompt_length"] > 300).astype(int)
        engaged["has_color"] = (engaged["llm_color"].fillna("") != "").astype(int)
        engaged["has_style"] = (engaged["llm_style"].fillna("") != "").astype(int)
        engaged["has_category"] = (engaged["llm_category"].fillna("") != "").astype(int)
        engaged["has_keyword"] = (engaged["llm_keyword"].fillna("") != "").astype(int)
        engaged["has_detail"] = (
            prompt_str.str.contains(r"detail|realistic|high.?quality|精细|细节|高质量",
                                    case=False, regex=True)
        ).astype(int)
        engaged["has_material"] = (
            prompt_str.str.contains(r"metal|wood|glass|stone|fabric|texture|材质|金属|木|玻璃",
                                    case=False, regex=True)
        ).astype(int)
        engaged["has_pose"] = (
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

        # Log-transform metric
        engaged["log_metric"] = np.log1p(engaged[metric].astype(float))

        # Spearman correlations
        correlations = []
        for col in feature_cols:
            label = feature_labels[col]
            col_values = engaged[col].fillna(0).astype(float)
            metric_values = engaged["log_metric"]

            if col_values.std() == 0:
                continue

            corr, p_val = stats.spearmanr(col_values, metric_values)

            n = len(col_values)
            z = np.arctanh(corr)
            se = 1 / np.sqrt(n - 3) if n > 3 else 0
            ci_lo = float(np.tanh(z - 1.96 * se))
            ci_hi = float(np.tanh(z + 1.96 * se))

            significant = bool(p_val < 0.05)

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

        # Feature-feature heatmap
        feat_df = engaged[feature_cols].fillna(0).astype(float)
        corr_matrix = feat_df.corr(method="spearman")
        heatmap_features = [feature_labels[c] for c in feature_cols]
        heatmap_values = []
        for i, c1 in enumerate(feature_cols):
            for j, c2 in enumerate(feature_cols):
                val = float(corr_matrix.loc[c1, c2])
                heatmap_values.append([i, j, None if np.isnan(val) else round(val, 3)])
        heatmap_data = {"features": heatmap_features, "values": heatmap_values}

        # Business insights
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
