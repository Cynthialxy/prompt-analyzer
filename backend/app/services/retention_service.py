"""User retention analysis: cohort + 7d/30d retention + re-generation rate."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd

from app.config import settings
from app.services import cache_service

logger = logging.getLogger(__name__)


def compute_retention(window_days: int = None) -> dict:
    """Compute cohort retention matrix and key retention metrics from cached data.

    Cohort: users grouped by their first-seen day.
    Matrix: for each cohort, how many users came back on day 1, 3, 7, 14, 30.
    """
    if window_days is None:
        window_days = settings.retention_cohort_window_days

    logger.info("Computing retention for last %d days from cache...", window_days)

    df = cache_service.get_prompts_df()
    if df.empty:
        return {
            "cohorts": [], "overall": {}, "re_generation": {},
            "avg_active_interval_days": 0, "window_days": window_days,
            "computed_at": datetime.now().isoformat(),
        }

    # Filter by date window and valid users
    cutoff = (datetime.now() - timedelta(days=window_days)).strftime("%Y%m%d")
    df = df[df["pt"].fillna("") >= cutoff]
    df = df[df["user_id"].fillna("") != ""]

    if df.empty:
        return {
            "cohorts": [], "overall": {}, "re_generation": {},
            "avg_active_interval_days": 0, "window_days": window_days,
            "computed_at": datetime.now().isoformat(),
        }

    # Compute first_seen per user
    first_seen_map = df.groupby("user_id")["pt"].min().rename("first_seen")
    df = df.merge(first_seen_map, on="user_id")

    # Build cohort data: first_seen -> {day_offset: user_count}
    cohort_data: dict = {}
    cohort_sizes: dict = {}

    for _, row in df[["user_id", "pt", "first_seen"]].drop_duplicates().iterrows():
        first_seen = row["first_seen"]
        activity_date = row["pt"]
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
        cohort_data[first_seen][offset] = cohort_data[first_seen].get(offset, 0) + 1

        if offset == 0:
            cohort_sizes[first_seen] = cohort_sizes.get(first_seen, 0) + 1

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

    # Re-generation: bucket users by active day count
    user_active_days = df.groupby("user_id")["pt"].nunique().reset_index(name="active_days")
    regen_map: dict = {"single_day": 0, "few_days": 0, "frequent": 0, "heavy": 0}
    for _, row in user_active_days.iterrows():
        d = int(row["active_days"])
        if d == 1:
            regen_map["single_day"] += 1
        elif d <= 5:
            regen_map["few_days"] += 1
        elif d <= 14:
            regen_map["frequent"] += 1
        else:
            regen_map["heavy"] += 1

    total_users = sum(regen_map.values())
    multi_day = sum(v for k, v in regen_map.items() if k != "single_day")
    re_generation = {
        **regen_map,
        "total_users": total_users,
        "multi_day_users": multi_day,
        "rate": round(multi_day / total_users, 4) if total_users else 0,
    }

    # Avg active interval (among multi-day users)
    multi_users = user_active_days[user_active_days["active_days"] > 1]["user_id"]
    avg_interval = 0.0
    if len(multi_users) > 0:
        multi_df = df[df["user_id"].isin(multi_users)]
        user_span = multi_df.groupby("user_id").agg(
            first_day=("pt", "min"),
            last_day=("pt", "max"),
            active_days=("pt", "nunique"),
        ).reset_index()
        intervals = []
        for _, row in user_span.iterrows():
            try:
                fd = datetime.strptime(row["first_day"], "%Y%m%d")
                ld = datetime.strptime(row["last_day"], "%Y%m%d")
                span = (ld - fd).days
                ad = int(row["active_days"]) - 1
                if ad > 0:
                    intervals.append(span / ad)
            except ValueError:
                pass
        avg_interval = round(sum(intervals) / len(intervals), 2) if intervals else 0.0

    result_data = {
        "cohorts": cohorts,
        "overall": overall,
        "re_generation": re_generation,
        "avg_active_interval_days": avg_interval,
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
