"""User segmentation and profile analysis."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd

from app.services import cache_service

logger = logging.getLogger(__name__)

# Segmentation rules (thresholds)
POWER_USER_MIN_PROMPTS = 10
POWER_USER_MIN_ACTIVE_DAYS = 5
REGULAR_USER_MIN_PROMPTS = 3
REGULAR_USER_MIN_ACTIVE_DAYS = 2
CHURNED_DAYS_THRESHOLD = 14


def classify_segment(total_prompts: int, active_days: int, last_seen: str) -> str:
    """Classify a user into a segment based on activity."""
    # Check churned first
    if last_seen:
        try:
            last_dt = datetime.strptime(last_seen, "%Y%m%d")
            days_since = (datetime.now() - last_dt).days
            if days_since > CHURNED_DAYS_THRESHOLD and total_prompts >= REGULAR_USER_MIN_PROMPTS:
                return "churned"
        except (ValueError, TypeError):
            pass

    if total_prompts >= POWER_USER_MIN_PROMPTS and active_days >= POWER_USER_MIN_ACTIVE_DAYS:
        return "power_user"
    if total_prompts >= REGULAR_USER_MIN_PROMPTS and active_days >= REGULAR_USER_MIN_ACTIVE_DAYS:
        return "regular"
    return "casual"


def compute_user_segments(days: int = 30, top_n: int = 50000) -> dict:
    """Compute user segments from cached SQLite data and persist results."""
    logger.info("Computing user segments (last %d days, top %d users) from cache...", days, top_n)

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

    with cache_service.get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) as cnt FROM prompts").fetchone()["cnt"]
        if count == 0:
            logger.warning("No cached prompts for user segment computation")
            return {"segments": {}, "total_users": 0, "computed_at": datetime.now().isoformat()}

        # Aggregate per user entirely in SQL — avoids loading 600K rows into pandas
        rows_raw = conn.execute(f"""
            SELECT
                user_id,
                COUNT(*) as total_prompts,
                COUNT(DISTINCT pt) as active_days,
                MIN(pt) as first_seen,
                MAX(pt) as last_seen,
                AVG(CAST(like_count AS REAL)) as avg_like_count,
                SUM(CAST(like_count AS INTEGER)) as total_like_count,
                AVG(CAST(score AS REAL)) as avg_score
            FROM prompts
            WHERE user_id IS NOT NULL AND user_id != ''
              AND pt >= ?
            GROUP BY user_id
            ORDER BY total_prompts DESC
            LIMIT ?
        """, (cutoff, top_n)).fetchall()

        # Top category per user via SQL (most frequent)
        cat_map = {}
        for r in conn.execute(f"""
            SELECT user_id, llm_category, COUNT(*) as cnt
            FROM prompts
            WHERE user_id IS NOT NULL AND user_id != ''
              AND llm_category IS NOT NULL AND llm_category != ''
              AND pt >= ?
            GROUP BY user_id, llm_category
        """, (cutoff,)).fetchall():
            uid = r["user_id"]
            if uid not in cat_map or r["cnt"] > cat_map[uid][1]:
                cat_map[uid] = (r["llm_category"], r["cnt"])

        style_map = {}
        for r in conn.execute(f"""
            SELECT user_id, llm_style, COUNT(*) as cnt
            FROM prompts
            WHERE user_id IS NOT NULL AND user_id != ''
              AND llm_style IS NOT NULL AND llm_style != ''
              AND pt >= ?
            GROUP BY user_id, llm_style
        """, (cutoff,)).fetchall():
            uid = r["user_id"]
            if uid not in style_map or r["cnt"] > style_map[uid][1]:
                style_map[uid] = (r["llm_style"], r["cnt"])

    rows = []
    for r in rows_raw:
        uid = r["user_id"]
        rows.append({
            "user_id": uid,
            "total_prompts": r["total_prompts"],
            "active_days": r["active_days"],
            "first_seen": r["first_seen"] or "",
            "last_seen": r["last_seen"] or "",
            "avg_like_count": r["avg_like_count"] or 0.0,
            "total_like_count": r["total_like_count"] or 0,
            "avg_score": r["avg_score"] or 0.0,
            "top_category": cat_map.get(uid, (None,))[0],
            "top_style": style_map.get(uid, (None,))[0],
        })
    logger.info("Aggregated %d users from cache via SQL", len(rows))

    # Classify and persist
    segment_counts = {"power_user": 0, "regular": 0, "casual": 0, "churned": 0}
    segment_sums = {
        s: {"total_prompts": 0, "total_likes": 0, "user_count": 0}
        for s in segment_counts
    }
    persisted = []
    for row in rows:
        user_id = row.get("user_id")
        total_prompts = _to_int(row.get("total_prompts"))
        active_days = _to_int(row.get("active_days"))
        first_seen = row.get("first_seen") or ""
        last_seen = row.get("last_seen") or ""
        avg_like = _to_float(row.get("avg_like_count")) or 0.0
        total_like = _to_int(row.get("total_like_count"))
        avg_score = _to_float(row.get("avg_score")) or 0.0

        segment = classify_segment(total_prompts, active_days, last_seen)
        segment_counts[segment] += 1
        segment_sums[segment]["total_prompts"] += total_prompts
        segment_sums[segment]["total_likes"] += total_like
        segment_sums[segment]["user_count"] += 1

        avg_pd = total_prompts / active_days if active_days > 0 else 0.0

        persisted.append({
            "user_id": user_id,
            "segment": segment,
            "total_prompts": total_prompts,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "active_days": active_days,
            "avg_prompts_per_day": round(avg_pd, 2),
            "top_category": row.get("top_category"),
            "top_style": row.get("top_style"),
            "avg_like_count": round(avg_like, 2),
            "total_like_count": total_like,
            "avg_score": round(avg_score, 2),
        })

    _save_segments(persisted)

    total_users = sum(segment_counts.values())
    segments_summary = {}
    for seg, cnt in segment_counts.items():
        s = segment_sums[seg]
        segments_summary[seg] = {
            "count": cnt,
            "percentage": round(cnt / total_users * 100, 1) if total_users else 0,
            "avg_prompts": round(s["total_prompts"] / s["user_count"], 1) if s["user_count"] else 0,
            "avg_likes": round(s["total_likes"] / s["user_count"], 2) if s["user_count"] else 0,
        }

    summary = {
        "segments": segments_summary,
        "segment_definitions": {
            "power_user": f">={POWER_USER_MIN_PROMPTS} 条 且 活跃天数 >={POWER_USER_MIN_ACTIVE_DAYS}",
            "regular": f">={REGULAR_USER_MIN_PROMPTS} 条 且 活跃天数 >={REGULAR_USER_MIN_ACTIVE_DAYS}",
            "casual": f"<{REGULAR_USER_MIN_PROMPTS} 条",
            "churned": f"最后活跃超过 {CHURNED_DAYS_THRESHOLD} 天 且 历史>={REGULAR_USER_MIN_PROMPTS} 条",
        },
        "total_users": total_users,
        "computed_at": datetime.now().isoformat(),
    }
    # Cache summary as analysis_result (run_id=0 for direct invocations)
    cache_service.save_analysis_result(0, "user_segments_summary", summary)
    logger.info("User segments computed: %s", segment_counts)
    return summary


def _save_segments(rows: list[dict]):
    """Persist user segments to SQLite."""
    if not rows:
        return
    with cache_service.get_conn() as conn:
        conn.execute("DELETE FROM user_segments")
        conn.executemany("""
            INSERT INTO user_segments
            (user_id, segment, total_prompts, first_seen, last_seen, active_days,
             avg_prompts_per_day, top_category, top_style, avg_like_count,
             total_like_count, avg_score, computed_at)
            VALUES (:user_id, :segment, :total_prompts, :first_seen, :last_seen,
                    :active_days, :avg_prompts_per_day, :top_category, :top_style,
                    :avg_like_count, :total_like_count, :avg_score, CURRENT_TIMESTAMP)
        """, rows)


def get_segment_overview(segment: str = None, sort_by: str = "total_prompts",
                          limit: int = 100) -> dict:
    """Get segment summary + top users list."""
    summary = cache_service.get_analysis_result("user_segments_summary") or {
        "segments": {}, "total_users": 0, "computed_at": None
    }

    # Validate sort_by
    valid_sorts = {"total_prompts", "avg_like_count", "active_days", "total_like_count", "avg_score"}
    sort_col = sort_by if sort_by in valid_sorts else "total_prompts"

    where = ""
    params: list = []
    if segment:
        where = "WHERE segment = ?"
        params.append(segment)

    with cache_service.get_conn() as conn:
        rows = conn.execute(
            f"""SELECT * FROM user_segments {where}
                ORDER BY {sort_col} DESC LIMIT ?""",
            [*params, limit]
        ).fetchall()

    summary["top_users"] = [dict(r) for r in rows]
    return summary


def get_user_profile(user_id: str) -> dict:
    """Get detailed profile for a single user from cached SQLite data."""
    logger.info("Fetching user profile for %s from cache", user_id)

    df = cache_service.get_prompts_df()
    udf = df[df["user_id"] == user_id].copy()

    if udf.empty:
        return {"user_id": user_id, "segment": "casual", "summary": {}, "error": "用户数据不在缓存中"}

    udf["like_count"] = pd.to_numeric(udf["like_count"], errors="coerce").fillna(0)
    udf["collect_count"] = pd.to_numeric(udf["collect_count"], errors="coerce").fillna(0)
    udf["score"] = pd.to_numeric(udf["score"], errors="coerce").fillna(0)

    total_prompts = len(udf)
    active_days = udf["pt"].nunique()
    first_seen = udf["pt"].min() or ""
    last_seen = udf["pt"].max() or ""
    segment = classify_segment(total_prompts, active_days, last_seen)

    # Category distribution
    cat_dist = (
        udf[udf["llm_category"].fillna("") != ""]
        .groupby("llm_category").size().reset_index(name="count")
        .sort_values("count", ascending=False).head(10)
    )

    # Style distribution
    style_dist = (
        udf[udf["llm_style"].fillna("") != ""]
        .groupby("llm_style").size().reset_index(name="count")
        .sort_values("count", ascending=False).head(10)
    )

    # Activity timeline
    timeline = (
        udf[udf["pt"].fillna("") != ""]
        .groupby("pt").size().reset_index(name="count")
        .sort_values("pt")
    )

    # Top prompts by like_count
    top_prompts = udf.sort_values("like_count", ascending=False).head(10)

    return {
        "user_id": user_id,
        "segment": segment,
        "summary": {
            "total_prompts": total_prompts,
            "active_days": active_days,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "avg_likes": round(float(udf["like_count"].mean()), 2),
            "total_likes": int(udf["like_count"].sum()),
            "total_collects": int(udf["collect_count"].sum()),
            "avg_score": round(float(udf["score"].mean()), 2),
            "avg_prompt_length": round(float(udf["prompt"].str.len().mean()), 1),
        },
        "category_distribution": [
            {"name": r["llm_category"], "count": int(r["count"])}
            for _, r in cat_dist.iterrows()
        ],
        "style_distribution": [
            {"name": r["llm_style"], "count": int(r["count"])}
            for _, r in style_dist.iterrows()
        ],
        "activity_timeline": [
            {"date": r["pt"], "count": int(r["count"])}
            for _, r in timeline.iterrows()
        ],
        "top_prompts": [
            {
                "project_id": r.get("project_id"),
                "prompt": r.get("prompt"),
                "like_count": int(r.get("like_count", 0)),
                "collect_count": int(r.get("collect_count", 0)),
                "score": float(r["score"]) if r.get("score") else None,
                "llm_category": r.get("llm_category"),
                "llm_style": r.get("llm_style"),
                "created_at": r.get("created_at"),
                "pt": r.get("pt"),
            }
            for _, r in top_prompts.iterrows()
        ],
    }


def _to_int(v) -> int:
    try:
        return int(float(v)) if v not in (None, "") else 0
    except (ValueError, TypeError):
        return 0


def _to_float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None
