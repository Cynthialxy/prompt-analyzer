"""User retention analysis: cohort + 7d/30d retention + re-generation rate."""
from __future__ import annotations

import logging
from datetime import datetime

from app.config import settings
from app.services import athena_service, cache_service

logger = logging.getLogger(__name__)


def compute_retention(window_days: int = None) -> dict:
    """Compute cohort retention matrix and key retention metrics.

    Cohort: users grouped by their first-seen day.
    Matrix: for each cohort, how many users came back on day 1, 3, 7, 14, 30, 60.

    Returns:
        {
          "cohorts": [{"cohort": "2026-03-01", "size": 120, "retention": {"1": 45, "7": 20, ...}}],
          "overall": {"d1": 0.32, "d3": 0.25, "d7": 0.18, "d14": 0.12, "d30": 0.08},
          "re_generation": {"single_day": 450, "multi_day": 120, "rate": 0.21},
          "avg_active_interval_days": 5.3,
        }
    """
    if window_days is None:
        window_days = settings.retention_cohort_window_days

    logger.info("Computing retention for last %d days...", window_days)

    # Step 1: Get first-seen + all active days for each user
    sql = f"""
        WITH user_activity AS (
            SELECT
                user_id,
                pt AS activity_date,
                MIN(pt) OVER (PARTITION BY user_id) AS first_seen
            FROM silver.clean_tripo_project
            WHERE prompt IS NOT NULL AND prompt != ''
              AND user_id IS NOT NULL AND user_id != ''
              AND pt >= date_format(date_add('day', -{window_days}, current_date), '%Y%m%d')
            GROUP BY user_id, pt
        )
        SELECT
            first_seen,
            activity_date,
            COUNT(DISTINCT user_id) AS user_count
        FROM user_activity
        GROUP BY first_seen, activity_date
        ORDER BY first_seen, activity_date
    """
    result = athena_service.run_query(sql)
    rows = result["rows"]
    logger.info("Fetched %d cohort-day rows", len(rows))

    # Build cohort matrix: first_seen -> {day_offset: user_count}
    cohort_data: dict = {}
    cohort_sizes: dict = {}
    for row in rows:
        first_seen = row.get("first_seen")
        activity_date = row.get("activity_date")
        user_count = _to_int(row.get("user_count"))

        if not first_seen or not activity_date:
            continue

        try:
            fs_dt = datetime.strptime(first_seen, "%Y%m%d")
            ad_dt = datetime.strptime(activity_date, "%Y%m%d")
            offset = (ad_dt - fs_dt).days
        except ValueError:
            continue

        if first_seen not in cohort_data:
            cohort_data[first_seen] = {}
        cohort_data[first_seen][offset] = user_count

        if offset == 0:
            cohort_sizes[first_seen] = user_count

    # Build cohorts output
    cohorts = []
    checkpoints = [1, 3, 7, 14, 30]
    for first_seen in sorted(cohort_data.keys()):
        size = cohort_sizes.get(first_seen, 0)
        if size == 0:
            continue
        retention: dict = {"0": size}
        for cp in checkpoints:
            retention[str(cp)] = cohort_data[first_seen].get(cp, 0)
        cohorts.append({
            "cohort": _format_date(first_seen),
            "size": size,
            "retention": retention,
            "retention_rate": {
                str(cp): round(retention[str(cp)] / size, 4) if size else 0
                for cp in checkpoints
            },
        })

    # Overall retention rates (weighted average)
    overall: dict = {}
    for cp in checkpoints:
        total_initial = sum(c["size"] for c in cohorts)
        total_returned = sum(c["retention"].get(str(cp), 0) for c in cohorts)
        overall[f"d{cp}"] = round(total_returned / total_initial, 4) if total_initial else 0

    # Re-generation: users with multiple active days vs single-day users
    user_days_sql = f"""
        SELECT
            CASE
                WHEN active_days = 1 THEN 'single_day'
                WHEN active_days BETWEEN 2 AND 5 THEN 'few_days'
                WHEN active_days BETWEEN 6 AND 14 THEN 'frequent'
                ELSE 'heavy'
            END AS bucket,
            COUNT(*) AS user_count,
            AVG(CAST(active_days AS DOUBLE)) AS avg_days
        FROM (
            SELECT user_id, COUNT(DISTINCT pt) AS active_days
            FROM silver.clean_tripo_project
            WHERE prompt IS NOT NULL AND prompt != ''
              AND user_id IS NOT NULL AND user_id != ''
              AND pt >= date_format(date_add('day', -{window_days}, current_date), '%Y%m%d')
            GROUP BY user_id
        )
        GROUP BY 1
    """
    regen_result = athena_service.run_query(user_days_sql)
    regen_map: dict = {}
    total_users = 0
    for row in regen_result["rows"]:
        bucket = row.get("bucket")
        cnt = _to_int(row.get("user_count"))
        regen_map[bucket] = cnt
        total_users += cnt

    multi_day = sum(v for k, v in regen_map.items() if k != "single_day")
    re_generation = {
        "single_day": regen_map.get("single_day", 0),
        "few_days": regen_map.get("few_days", 0),
        "frequent": regen_map.get("frequent", 0),
        "heavy": regen_map.get("heavy", 0),
        "total_users": total_users,
        "multi_day_users": multi_day,
        "rate": round(multi_day / total_users, 4) if total_users else 0,
    }

    # Avg active interval (among multi-day users)
    interval_sql = f"""
        WITH user_days AS (
            SELECT user_id, MIN(pt) AS first_day, MAX(pt) AS last_day,
                   COUNT(DISTINCT pt) AS active_days
            FROM silver.clean_tripo_project
            WHERE prompt IS NOT NULL AND prompt != ''
              AND user_id IS NOT NULL AND user_id != ''
              AND pt >= date_format(date_add('day', -{window_days}, current_date), '%Y%m%d')
            GROUP BY user_id
            HAVING COUNT(DISTINCT pt) > 1
        )
        SELECT AVG(
            CAST(
                (CAST(SUBSTR(last_day, 1, 4) AS INTEGER) * 10000
                 + CAST(SUBSTR(last_day, 5, 2) AS INTEGER) * 100
                 + CAST(SUBSTR(last_day, 7, 2) AS INTEGER))
              - (CAST(SUBSTR(first_day, 1, 4) AS INTEGER) * 10000
                 + CAST(SUBSTR(first_day, 5, 2) AS INTEGER) * 100
                 + CAST(SUBSTR(first_day, 7, 2) AS INTEGER))
            AS DOUBLE) / NULLIF(active_days - 1, 0)
        ) AS avg_interval
        FROM user_days
    """
    try:
        interval_result = athena_service.run_query(interval_sql)
        avg_interval = _to_float(interval_result["rows"][0].get("avg_interval")) if interval_result["rows"] else 0
    except Exception as e:
        logger.warning("Avg interval calc failed: %s", e)
        avg_interval = 0

    result_data = {
        "cohorts": cohorts,
        "overall": overall,
        "re_generation": re_generation,
        "avg_active_interval_days": round(avg_interval or 0, 2),
        "window_days": window_days,
        "computed_at": datetime.now().isoformat(),
    }
    cache_service.save_analysis_result(0, "retention", result_data)
    logger.info("Retention computed: %d cohorts, overall d7=%.2f%%",
                len(cohorts), overall.get("d7", 0) * 100)
    return result_data


def _format_date(yyyymmdd: str) -> str:
    if not yyyymmdd or len(yyyymmdd) != 8:
        return yyyymmdd
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


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
