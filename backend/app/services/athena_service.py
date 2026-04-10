"""Athena query service - adapted from data-agent/query/athena_executor.py."""
from __future__ import annotations

import logging
import time

import boto3


from app.config import settings
from app.services import cache_service

logger = logging.getLogger(__name__)


def run_query(sql: str, database: str = "silver") -> dict:
    """Execute Athena query synchronously with polling and pagination."""
    athena = boto3.client("athena", region_name=settings.aws_region)

    start_args = {
        "QueryString": sql,
        "QueryExecutionContext": {"Database": database},
    }
    if settings.athena_workgroup:
        start_args["WorkGroup"] = settings.athena_workgroup
    if settings.athena_output_location:
        start_args["ResultConfiguration"] = {"OutputLocation": settings.athena_output_location}

    qid = athena.start_query_execution(**start_args)["QueryExecutionId"]
    logger.info("Athena query submitted: %s", qid)

    # Poll for completion
    start_time = time.time()
    while True:
        qe = athena.get_query_execution(QueryExecutionId=qid)
        state = qe["QueryExecution"]["Status"]["State"]

        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            if state != "SUCCEEDED":
                reason = qe["QueryExecution"]["Status"].get("StateChangeReason", "")
                raise RuntimeError(f"Athena query failed: {state} - {reason}")
            break

        if time.time() - start_time > settings.athena_query_timeout_sec:
            raise TimeoutError(f"Athena query timeout (>{settings.athena_query_timeout_sec}s)")

        time.sleep(settings.athena_poll_interval_sec)

    stats = qe["QueryExecution"].get("Statistics", {})
    bytes_scanned = stats.get("DataScannedInBytes", 0)
    execution_time_ms = stats.get("EngineExecutionTimeInMillis", 0)

    # Paginate results
    paginator = athena.get_paginator("get_query_results")
    column_names = []
    rows = []
    seen_header = False

    for page in paginator.paginate(QueryExecutionId=qid):
        if not column_names:
            column_info = page["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]
            column_names = [col["Name"] for col in column_info]

        for row in page["ResultSet"]["Rows"]:
            if not seen_header:
                seen_header = True
                continue
            data = row.get("Data", [])
            row_obj = {}
            for idx, col_name in enumerate(column_names):
                val = data[idx].get("VarCharValue") if idx < len(data) else None
                row_obj[col_name] = val
            rows.append(row_obj)

    logger.info("Athena query done: %d rows, %.2f MB scanned, %d ms",
                len(rows), bytes_scanned / 1024 / 1024, execution_time_ms)

    return {
        "columns": column_names,
        "rows": rows,
        "row_count": len(rows),
        "bytes_scanned": bytes_scanned,
        "execution_time_ms": execution_time_ms,
    }


def fetch_and_cache_prompts(days: int = 7, limit: int = 50000) -> int:
    """Fetch recent prompts from Athena and cache in SQLite."""
    sql = f"""
        SELECT project_id, user_id, prompt, caption, name,
               llm_keyword, llm_object, llm_category, llm_style,
               llm_color, llm_use_case, llm_height, from_type,
               status, visibility, display_image,
               like_count, collect_count, score,
               created_at, pt
        FROM silver.clean_tripo_project
        WHERE prompt IS NOT NULL AND prompt != ''
          AND pt >= date_format(date_add('day', -{days}, current_date), '%Y-%m-%d')
        LIMIT {limit}
    """
    result = run_query(sql)
    cache_service.save_prompts(result["rows"])
    return result["row_count"]


def fetch_summary(date_from: str = None, date_to: str = None) -> dict:
    """Get real-time summary stats directly from Athena."""
    date_filter = ""
    if date_from:
        date_filter += f" AND pt >= '{date_from.replace('-', '')}'"
    if date_to:
        date_filter += f" AND pt <= '{date_to.replace('-', '')}'"

    sql = f"""
        SELECT
            COUNT(*) as total_prompts,
            COUNT(DISTINCT user_id) as unique_users,
            MIN(pt) as min_date,
            MAX(pt) as max_date,
            ROUND(AVG(LENGTH(prompt)), 1) as avg_prompt_length
        FROM silver.clean_tripo_project
        WHERE prompt IS NOT NULL AND prompt != '' {date_filter}
    """
    result = run_query(sql)
    row = result["rows"][0] if result["rows"] else {}

    # Top categories
    cat_sql = f"""
        SELECT llm_category, COUNT(*) as cnt
        FROM silver.clean_tripo_project
        WHERE prompt IS NOT NULL AND prompt != ''
          AND llm_category IS NOT NULL AND llm_category != '' {date_filter}
        GROUP BY llm_category
        ORDER BY cnt DESC
        LIMIT 10
    """
    cat_result = run_query(cat_sql)

    return {
        "total_prompts": int(row.get("total_prompts", 0)),
        "unique_users": int(row.get("unique_users", 0)),
        "date_range": {"min": row.get("min_date"), "max": row.get("max_date")},
        "avg_prompt_length": float(row.get("avg_prompt_length", 0) or 0),
        "top_categories": [
            {"name": r["llm_category"], "count": int(r["cnt"])}
            for r in cat_result["rows"]
        ],
    }


def fetch_daily_counts_live(date_from: str = None, date_to: str = None) -> list[dict]:
    """Get daily counts directly from Athena with date filter."""
    date_filter = ""
    if date_from:
        date_filter += f" AND pt >= '{date_from.replace('-', '')}'"
    if date_to:
        date_filter += f" AND pt <= '{date_to.replace('-', '')}'"

    sql = f"""
        SELECT pt as date, COUNT(*) as count
        FROM silver.clean_tripo_project
        WHERE prompt IS NOT NULL AND prompt != '' AND pt IS NOT NULL {date_filter}
        GROUP BY pt
        ORDER BY pt
    """
    result = run_query(sql)
    return [{"date": r["date"], "count": int(r["count"])} for r in result["rows"]]


def fetch_category_distributions() -> dict:
    """Fetch all category/style/use_case distributions from Athena."""
    result = {}

    for field in ["llm_category", "llm_style", "llm_use_case"]:
        sql = f"""
            SELECT {field} as name, COUNT(*) as count
            FROM silver.clean_tripo_project
            WHERE prompt IS NOT NULL AND prompt != ''
              AND {field} IS NOT NULL AND {field} != ''
            GROUP BY {field}
            ORDER BY count DESC
        """
        qr = run_query(sql)
        result[field] = [{"name": r["name"], "count": int(r["count"])} for r in qr["rows"]]

    # Color
    color_sql = """
        SELECT llm_color, COUNT(*) as cnt
        FROM silver.clean_tripo_project
        WHERE prompt IS NOT NULL AND prompt != ''
          AND llm_color IS NOT NULL AND llm_color != ''
        GROUP BY llm_color
        ORDER BY cnt DESC
        LIMIT 100
    """
    color_qr = run_query(color_sql)
    color_counts: dict = {}
    for r in color_qr["rows"]:
        for color in r["llm_color"].split(","):
            c = color.strip().lower()
            if c:
                color_counts[c] = color_counts.get(c, 0) + int(r["cnt"])
    result["llm_color"] = sorted(
        [{"name": k, "count": v} for k, v in color_counts.items()],
        key=lambda x: x["count"], reverse=True
    )

    # Cross-tab: category x style (top combos)
    cross_sql = """
        SELECT llm_category, llm_style, COUNT(*) as count
        FROM silver.clean_tripo_project
        WHERE prompt IS NOT NULL AND prompt != ''
          AND llm_category IS NOT NULL AND llm_category != ''
          AND llm_style IS NOT NULL AND llm_style != ''
        GROUP BY llm_category, llm_style
        ORDER BY count DESC
        LIMIT 200
    """
    cross_qr = run_query(cross_sql)
    result["category_style_cross"] = [
        {"llm_category": r["llm_category"], "llm_style": r["llm_style"], "count": int(r["count"])}
        for r in cross_qr["rows"]
    ]

    return result


def fetch_daily_counts() -> list[dict]:
    """Push-down daily count aggregation."""
    sql = """
        SELECT pt, COUNT(*) as daily_count
        FROM silver.clean_tripo_project
        WHERE prompt IS NOT NULL AND prompt != '' AND pt IS NOT NULL
        GROUP BY pt
        ORDER BY pt
    """
    result = run_query(sql)
    return result["rows"]
