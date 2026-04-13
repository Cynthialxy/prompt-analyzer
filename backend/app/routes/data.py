"""Data routes: summary, prompts list, sync."""

from flask import Blueprint, request, jsonify

from app.services import cache_service, athena_service

data_bp = Blueprint("data", __name__)


@data_bp.route("/summary")
def get_summary():
    """Get overall data summary from cache (fast), with optional Athena fallback."""
    date_from = request.args.get("date_from", None)
    date_to = request.args.get("date_to", None)
    try:
        summary = cache_service.get_summary(date_from=date_from, date_to=date_to)
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@data_bp.route("/prompts")
def get_prompts():
    """Get paginated prompts with filters."""
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 50, type=int)
    search = request.args.get("search", None)
    category = request.args.get("category", None)
    style = request.args.get("style", None)
    language = request.args.get("language", None)

    result = cache_service.get_prompts_paginated(
        page=page, page_size=page_size,
        search=search, category=category,
        style=style, language=language,
    )
    return jsonify(result)


@data_bp.route("/sync", methods=["POST"])
def sync_data():
    """Sync data from Athena to local cache."""
    try:
        count = athena_service.fetch_and_cache_prompts()
        return jsonify({"status": "ok", "count": count})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@data_bp.route("/sync-and-analyze", methods=["POST"])
def sync_and_analyze():
    """Incremental sync from Athena then run full analysis pipeline in background."""
    from app.services import pipeline_service
    try:
        run_id = pipeline_service.start_sync_and_analyze()
        return jsonify({"status": "started", "run_id": run_id})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@data_bp.route("/daily-counts")
def get_daily_counts():
    """Get daily prompt counts from cache."""
    date_from = request.args.get("date_from", None)
    date_to = request.args.get("date_to", None)
    try:
        counts = cache_service.get_daily_counts(date_from=date_from, date_to=date_to)
        return jsonify(counts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@data_bp.route("/clear-cache", methods=["POST"])
def clear_cache():
    """Clear all cached prompts and reset sync state."""
    from app.services.cache_service import get_conn
    with get_conn() as conn:
        conn.execute("DELETE FROM prompts")
        conn.execute("DELETE FROM sync_state")
        conn.execute("DELETE FROM analysis_results")
        conn.execute("DELETE FROM analysis_runs")
        conn.execute("DELETE FROM user_segments")
    return jsonify({"status": "ok", "message": "Cache cleared"})


def export_csv():
    """Export prompts as CSV."""
    import io
    import csv
    from flask import Response

    df = cache_service.get_prompts_df()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(df.columns.tolist())
    for _, row in df.iterrows():
        writer.writerow(row.tolist())

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=prompts_export.csv"}
    )
