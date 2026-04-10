"""BERTopic-based topic modeling (replaces LDA for v1 analysis)."""
from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
import pandas as pd

from app.config import settings
from app.services import cache_service

logger = logging.getLogger(__name__)

# Lazy module state
_topic_model = None


def is_available() -> bool:
    """Check if BERTopic dependencies are installed."""
    try:
        import bertopic  # noqa: F401
        import umap  # noqa: F401
        import hdbscan  # noqa: F401
        return True
    except ImportError:
        return False


def compute_bertopic() -> dict:
    """Train BERTopic model on cached prompts.

    Returns:
        {
          "topics": [{"id": 0, "label": "...", "keywords": [...], "size": 120, "representative_prompts": [...]}],
          "topic_heat_trend": [{"topic": 0, "date": "2026-03-01", "count": 10}],
          "topic_quality_link": [{"topic": 0, "avg_likes": 3.2, "avg_score": 4.1}],
          "scatter": [{"x": 1.2, "y": 0.4, "topic_id": 0, "prompt_preview": "..."}],
          "n_topics": 15,
          "model": "BERTopic"
        }
    """
    if not is_available():
        logger.warning("BERTopic unavailable (missing dependencies), falling back to simple clustering")
        return _fallback_clustering()

    df = cache_service.get_prompts_df()
    if df.empty:
        return {"error": "No data"}

    # Sample to keep cost bounded
    sample_size = min(len(df), settings.bertopic_sample_size)
    if len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=42)

    # Filter: English-like prompts for BERTopic base model (can be upgraded)
    df = df[df["prompt"].notna() & (df["prompt"].str.len() > 10)].copy()
    if df.empty:
        return {"error": "No valid prompts"}

    logger.info("Training BERTopic on %d prompts...", len(df))
    try:
        from bertopic import BERTopic
        from sentence_transformers import SentenceTransformer

        embedding_model = SentenceTransformer(settings.embedding_model_name)
        topic_model = BERTopic(
            embedding_model=embedding_model,
            min_topic_size=settings.bertopic_min_topic_size,
            calculate_probabilities=False,
            verbose=False,
        )
        prompts = df["prompt"].astype(str).tolist()
        topics, _ = topic_model.fit_transform(prompts)
        df["topic_id"] = topics

        global _topic_model
        _topic_model = topic_model

        # Extract topic info
        topic_info = topic_model.get_topic_info()
        topics_out = []
        for _, row in topic_info.iterrows():
            tid = int(row["Topic"])
            if tid == -1:
                continue  # outlier
            words = topic_model.get_topic(tid) or []
            keywords = [w for w, _ in words[:10]] if words else []
            # Sample representative prompts
            sample = df[df["topic_id"] == tid].head(5)["prompt"].tolist()
            # Label (use top-3 keywords)
            label = ", ".join(keywords[:3]) if keywords else f"Topic {tid}"
            topics_out.append({
                "id": tid,
                "label": label,
                "keywords": keywords,
                "size": int((df["topic_id"] == tid).sum()),
                "representative_prompts": [str(p)[:200] for p in sample],
            })

        # Topic heat trend (daily)
        heat_trend = []
        if "pt" in df.columns:
            trend = df.groupby(["topic_id", "pt"]).size().reset_index(name="count")
            for _, r in trend.iterrows():
                tid = int(r["topic_id"])
                if tid == -1:
                    continue
                heat_trend.append({
                    "topic": tid,
                    "date": _format_date(str(r["pt"])),
                    "count": int(r["count"]),
                })

        # Topic -> engagement link
        topic_quality = []
        for tid_row in topics_out:
            tid = tid_row["id"]
            mask = df["topic_id"] == tid
            subset = df[mask]
            topic_quality.append({
                "topic": tid,
                "label": tid_row["label"],
                "size": tid_row["size"],
                "avg_likes": round(float(pd.to_numeric(subset.get("like_count", 0), errors="coerce").fillna(0).mean() or 0), 2),
                "avg_collects": round(float(pd.to_numeric(subset.get("collect_count", 0), errors="coerce").fillna(0).mean() or 0), 2),
                "avg_score": round(float(pd.to_numeric(subset.get("score", 0), errors="coerce").fillna(0).mean() or 0), 2),
            })

        result = {
            "topics": topics_out,
            "topic_heat_trend": heat_trend,
            "topic_quality_link": topic_quality,
            "topic_prompt_samples": _build_topic_prompt_samples_from_df(df),
            "n_topics": len(topics_out),
            "model": "BERTopic",
            "sample_size": len(df),
            "computed_at": datetime.now().isoformat(),
        }
        result["filter_options"] = _build_filter_options(result.get("topic_prompt_samples", []))
        cache_service.save_analysis_result(0, "bertopic", result)
        logger.info("BERTopic done: %d topics", len(topics_out))
        return result

    except Exception as e:
        logger.error("BERTopic failed: %s", e, exc_info=True)
        return _fallback_clustering()


def _fallback_clustering() -> dict:
    """Fallback: reuse existing LDA topic data from v1 cache."""
    existing = cache_service.get_analysis_result("topics")
    if not existing:
        return {
            "topics": [], "topic_heat_trend": [], "topic_quality_link": [],
            "n_topics": 0, "model": "none",
            "error": "BERTopic unavailable and no LDA fallback",
        }

    clusters = [
        {
            "id": c["id"],
            "label": c.get("label", f"Topic {c['id']+1}"),
            "keywords": c.get("keywords", []),
            "size": c.get("size", 0),
            "representative_prompts": [p for p in c.get("representative_prompts", []) if p and str(p).strip()],
        }
        for c in existing.get("clusters", [])
    ]

    # Build quality link from cached prompts
    quality_link = []
    try:
        df = cache_service.get_prompts_df()
        if not df.empty and "topic_id" not in df.columns:
            # Assign topics from scatter data if available
            scatter = existing.get("scatter_data", [])
            if scatter:
                preview_to_topic = {s["prompt_preview"]: s["topic_id"] for s in scatter if s.get("prompt_preview")}
                df["_preview"] = df["prompt"].astype(str).str[:200]
                df["topic_id"] = df["_preview"].map(preview_to_topic)

        if not df.empty and "topic_id" in df.columns:
            for cluster in clusters:
                mask = df["topic_id"] == cluster["id"]
                subset = df[mask]
                if subset.empty:
                    quality_link.append({
                        "topic": cluster["id"], "label": cluster["label"],
                        "size": cluster["size"], "avg_likes": 0, "avg_collects": 0, "avg_score": 0,
                    })
                else:
                    quality_link.append({
                        "topic": cluster["id"],
                        "label": cluster["label"],
                        "size": cluster["size"],
                        "avg_likes": round(float(pd.to_numeric(subset.get("like_count", 0), errors="coerce").fillna(0).mean()), 4),
                        "avg_collects": round(float(pd.to_numeric(subset.get("collect_count", 0), errors="coerce").fillna(0).mean()), 4),
                        "avg_score": round(float(pd.to_numeric(subset.get("score", 0), errors="coerce").fillna(0).mean()), 2),
                    })
    except Exception as e:
        logger.warning("Fallback quality link failed: %s", e)
        quality_link = [
            {"topic": c["id"], "label": c["label"], "size": c["size"],
             "avg_likes": 0, "avg_collects": 0, "avg_score": 0}
            for c in clusters
        ]

    return {
        "topics": clusters,
        "topic_heat_trend": [],
        "topic_quality_link": quality_link,
        "n_topics": len(clusters),
        "model": "LDA_fallback",
        "sample_size": len(existing.get("scatter_data", [])),
        "fallback_reason": "BERTopic unavailable, using LDA results",
        "computed_at": datetime.now().isoformat(),
    }


def _format_date(yyyymmdd: str) -> str:
    if not yyyymmdd or len(yyyymmdd) != 8:
        return yyyymmdd
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


def _build_sample_quality_metrics(existing: dict) -> dict[int, dict[str, float]]:
    scatter = existing.get("scatter_data") or []
    if not scatter:
        return {}

    prompts_df = cache_service.get_prompts_df()
    if prompts_df.empty:
        return {}

    scatter_df = pd.DataFrame(scatter)
    if scatter_df.empty or "prompt_preview" not in scatter_df.columns or "topic_id" not in scatter_df.columns:
        return {}

    prompts_df = prompts_df.copy()
    prompts_df["prompt_preview"] = prompts_df["prompt"].astype(str).str.slice(0, 200)
    prefix_stats = (
        prompts_df.groupby("prompt_preview", as_index=False)
        .agg(
            like_count=("like_count", "mean"),
            collect_count=("collect_count", "mean"),
            score=("score", "mean"),
        )
    )
    merged = scatter_df.merge(prefix_stats, on="prompt_preview", how="left")
    if merged.empty:
        return {}

    metrics = (
        merged.groupby("topic_id", as_index=False)
        .agg(
            avg_likes=("like_count", "mean"),
            avg_collects=("collect_count", "mean"),
            avg_score=("score", "mean"),
        )
        .fillna(0)
    )
    return {
        int(row["topic_id"]): {
            "avg_likes": float(row["avg_likes"] or 0),
            "avg_collects": float(row["avg_collects"] or 0),
            "avg_score": float(row["avg_score"] or 0),
        }
        for _, row in metrics.iterrows()
    }


def _build_sample_heat_trend(existing: dict) -> list[dict]:
    scatter = existing.get("scatter_data") or []
    if not scatter:
        return []

    prompts_df = cache_service.get_prompts_df()
    if prompts_df.empty or "pt" not in prompts_df.columns:
        return []

    scatter_df = pd.DataFrame(scatter)
    if scatter_df.empty or "prompt_preview" not in scatter_df.columns or "topic_id" not in scatter_df.columns:
        return []

    prompts_df = prompts_df.copy()
    prompts_df["prompt_preview"] = prompts_df["prompt"].astype(str).str.slice(0, 200)
    prefix_dates = prompts_df.groupby("prompt_preview", as_index=False).agg(pt=("pt", "first"))
    merged = scatter_df.merge(prefix_dates, on="prompt_preview", how="left")
    if merged.empty or "pt" not in merged.columns:
        return []

    grouped = (
        merged[merged["pt"].notna()]
        .groupby(["topic_id", "pt"], as_index=False)
        .size()
    )
    return [
        {
            "topic": int(row["topic_id"]),
            "date": _format_date(str(row["pt"])),
            "count": int(row["size"]),
        }
        for _, row in grouped.iterrows()
    ]


def _build_topic_prompt_samples_from_df(df: pd.DataFrame) -> list[dict]:
    if df.empty or "topic_id" not in df.columns:
        return []

    user_segments = _build_user_segment_map(df)
    samples = []
    for _, row in df.iterrows():
        topic_id = int(row.get("topic_id", -1))
        if topic_id == -1:
            continue
        samples.append({
            "topic": topic_id,
            "date": _format_date(str(row.get("pt", "") or "")),
            "platform": _normalize_platform(row.get("from_type")),
            "user_segment": user_segments.get(str(row.get("user_id") or ""), "casual"),
            "like_count": _safe_float(row.get("like_count"), 4),
            "collect_count": _safe_float(row.get("collect_count"), 4),
            "score": _safe_float(row.get("score"), 2),
        })
    return samples


def _build_topic_prompt_samples_from_existing(existing: dict) -> list[dict]:
    scatter = existing.get("scatter_data") or []
    if not scatter:
        return []

    prompts_df = cache_service.get_prompts_df()
    if prompts_df.empty:
        return []

    scatter_df = pd.DataFrame(scatter)
    if scatter_df.empty or "prompt_preview" not in scatter_df.columns or "topic_id" not in scatter_df.columns:
        return []

    prompts_df = prompts_df.copy()
    prompts_df["prompt_preview"] = prompts_df["prompt"].astype(str).str.slice(0, 200)
    user_segments = _build_user_segment_map(prompts_df)
    prompt_rows = (
        prompts_df.groupby("prompt_preview", as_index=False)
        .agg(
            pt=("pt", "first"),
            from_type=("from_type", "first"),
            user_id=("user_id", "first"),
            like_count=("like_count", "mean"),
            collect_count=("collect_count", "mean"),
            score=("score", "mean"),
        )
    )
    merged = scatter_df.merge(prompt_rows, on="prompt_preview", how="left")
    if merged.empty:
        return []

    samples = []
    for _, row in merged.iterrows():
        samples.append({
            "topic": int(row.get("topic_id", -1)),
            "date": _format_date(str(row.get("pt", "") or "")),
            "platform": _normalize_platform(row.get("from_type")),
            "user_segment": user_segments.get(str(row.get("user_id") or ""), "casual"),
            "like_count": _safe_float(row.get("like_count"), 4),
            "collect_count": _safe_float(row.get("collect_count"), 4),
            "score": _safe_float(row.get("score"), 2),
        })
    return samples


def _build_user_segment_map(df: pd.DataFrame) -> dict[str, str]:
    if df.empty or "user_id" not in df.columns:
        return {}

    from app.services import user_service

    work_df = df.copy()
    work_df = work_df[work_df["user_id"].notna() & (work_df["user_id"].astype(str).str.strip() != "")]
    if work_df.empty:
        return {}

    if "pt" not in work_df.columns:
        work_df["pt"] = ""

    grouped = (
        work_df.groupby("user_id", as_index=False)
        .agg(
            total_prompts=("prompt", "count"),
            active_days=("pt", lambda s: s.replace("", pd.NA).dropna().nunique()),
            last_seen=("pt", "max"),
        )
    )
    return {
        str(row["user_id"]): user_service.classify_segment(
            int(row["total_prompts"] or 0),
            int(row["active_days"] or 0),
            str(row["last_seen"] or ""),
        )
        for _, row in grouped.iterrows()
    }


def _normalize_platform(value) -> str:
    text = str(value or "").strip()
    return text if text else "unknown"


def _build_filter_options(samples: list[dict]) -> dict:
    if not samples:
        return {"platforms": [], "user_groups": ["power_user", "regular", "casual", "churned"], "date_range": {}}

    dates = sorted({row["date"] for row in samples if row.get("date")})
    platforms = sorted({row["platform"] for row in samples if row.get("platform")})
    user_groups = sorted({row["user_segment"] for row in samples if row.get("user_segment")})
    return {
        "platforms": platforms,
        "user_groups": user_groups,
        "date_range": {
            "min": dates[0] if dates else None,
            "max": dates[-1] if dates else None,
        },
    }


def _safe_float(value, digits: int = 4) -> float:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return 0.0
    return round(float(numeric), digits)
