"""User segmentation and profile analysis."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.services import athena_service, cache_service

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
    """Compute user segments from Athena data and persist to SQLite.

    Args:
        days: look back window in days for user activity aggregation.
        top_n: max number of users to aggregate (ordered by total_prompts DESC).

    Returns:
        Summary dict with segment counts and top users.
    """
    logger.info("Computing user segments (last %d days, top %d users)...", days, top_n)

    sql = f"""
        SELECT
            user_id,
            COUNT(*) AS total_prompts,
            COUNT(DISTINCT pt) AS active_days,
            MIN(pt) AS first_seen,
            MAX(pt) AS last_seen,
            AVG(CAST(like_count AS DOUBLE)) AS avg_like_count,
            SUM(CAST(like_count AS BIGINT)) AS total_like_count,
            AVG(CAST(score AS DOUBLE)) AS avg_score,
            MAX_BY(llm_category, 1) AS top_category,
            MAX_BY(llm_style, 1) AS top_style
        FROM silver.clean_tripo_project
        WHERE prompt IS NOT NULL AND prompt != ''
          AND user_id IS NOT NULL AND user_id != ''
          AND pt >= date_format(date_add('day', -{days}, current_date), '%Y%m%d')
        GROUP BY user_id
        ORDER BY total_prompts DESC
        LIMIT {top_n}
    """

    result = athena_service.run_query(sql)
    rows = result["rows"]
    logger.info("Fetched %d user aggregates from Athena", len(rows))

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
    """Get detailed profile for a single user, querying Athena for fresh data."""
    logger.info("Fetching user profile for %s", user_id)

    # Aggregate stats
    stats_sql = f"""
        SELECT
            COUNT(*) AS total_prompts,
            COUNT(DISTINCT pt) AS active_days,
            MIN(pt) AS first_seen,
            MAX(pt) AS last_seen,
            AVG(CAST(like_count AS DOUBLE)) AS avg_like_count,
            SUM(CAST(like_count AS BIGINT)) AS total_like_count,
            SUM(CAST(collect_count AS BIGINT)) AS total_collect_count,
            AVG(CAST(score AS DOUBLE)) AS avg_score,
            AVG(LENGTH(prompt)) AS avg_prompt_length
        FROM silver.clean_tripo_project
        WHERE user_id = '{user_id}' AND prompt IS NOT NULL AND prompt != ''
    """
    stats_result = athena_service.run_query(stats_sql)
    stats = stats_result["rows"][0] if stats_result["rows"] else {}

    total_prompts = _to_int(stats.get("total_prompts"))
    active_days = _to_int(stats.get("active_days"))
    last_seen = stats.get("last_seen") or ""
    segment = classify_segment(total_prompts, active_days, last_seen)

    # Category distribution
    cat_sql = f"""
        SELECT llm_category AS name, COUNT(*) AS count
        FROM silver.clean_tripo_project
        WHERE user_id = '{user_id}'
          AND prompt IS NOT NULL AND prompt != ''
          AND llm_category IS NOT NULL AND llm_category != ''
        GROUP BY llm_category
        ORDER BY count DESC
        LIMIT 10
    """
    cat_result = athena_service.run_query(cat_sql)

    # Style distribution
    style_sql = f"""
        SELECT llm_style AS name, COUNT(*) AS count
        FROM silver.clean_tripo_project
        WHERE user_id = '{user_id}'
          AND prompt IS NOT NULL AND prompt != ''
          AND llm_style IS NOT NULL AND llm_style != ''
        GROUP BY llm_style
        ORDER BY count DESC
        LIMIT 10
    """
    style_result = athena_service.run_query(style_sql)

    # Activity timeline
    timeline_sql = f"""
        SELECT pt AS date, COUNT(*) AS count
        FROM silver.clean_tripo_project
        WHERE user_id = '{user_id}'
          AND prompt IS NOT NULL AND prompt != ''
          AND pt IS NOT NULL
        GROUP BY pt
        ORDER BY pt
    """
    timeline_result = athena_service.run_query(timeline_sql)

    # Top prompts by like_count
    top_sql = f"""
        SELECT project_id, prompt, like_count, collect_count, score,
               llm_category, llm_style, created_at, pt
        FROM silver.clean_tripo_project
        WHERE user_id = '{user_id}'
          AND prompt IS NOT NULL AND prompt != ''
        ORDER BY CAST(like_count AS BIGINT) DESC
        LIMIT 10
    """
    top_result = athena_service.run_query(top_sql)

    return {
        "user_id": user_id,
        "segment": segment,
        "summary": {
            "total_prompts": total_prompts,
            "active_days": active_days,
            "first_seen": stats.get("first_seen"),
            "last_seen": last_seen,
            "avg_likes": round(_to_float(stats.get("avg_like_count")) or 0, 2),
            "total_likes": _to_int(stats.get("total_like_count")),
            "total_collects": _to_int(stats.get("total_collect_count")),
            "avg_score": round(_to_float(stats.get("avg_score")) or 0, 2),
            "avg_prompt_length": round(_to_float(stats.get("avg_prompt_length")) or 0, 1),
        },
        "category_distribution": [
            {"name": r.get("name"), "count": _to_int(r.get("count"))}
            for r in cat_result["rows"]
        ],
        "style_distribution": [
            {"name": r.get("name"), "count": _to_int(r.get("count"))}
            for r in style_result["rows"]
        ],
        "activity_timeline": [
            {"date": r.get("date"), "count": _to_int(r.get("count"))}
            for r in timeline_result["rows"]
        ],
        "top_prompts": [
            {
                "project_id": r.get("project_id"),
                "prompt": r.get("prompt"),
                "like_count": _to_int(r.get("like_count")),
                "collect_count": _to_int(r.get("collect_count")),
                "score": _to_float(r.get("score")),
                "llm_category": r.get("llm_category"),
                "llm_style": r.get("llm_style"),
                "created_at": r.get("created_at"),
                "pt": r.get("pt"),
            }
            for r in top_result["rows"]
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
