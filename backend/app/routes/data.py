"""Data routes: summary, prompts list, sync."""

from flask import Blueprint, request, jsonify

from app.services import cache_service, athena_service

data_bp = Blueprint("data", __name__)


@data_bp.route("/summary")
def get_summary():
    """Get overall data summary - query Athena for accurate real-time stats."""
    date_from = request.args.get("date_from", None)
    date_to = request.args.get("date_to", None)
    source = request.args.get("source", "athena")  # athena (accurate) or cache (fast)
    try:
        if source == "cache":
            summary = cache_service.get_summary(date_from=date_from, date_to=date_to)
        else:
            summary = athena_service.fetch_summary(date_from=date_from, date_to=date_to)
        return jsonify(summary)
    except Exception as e:
        # Fallback to cache if Athena fails
        summary = cache_service.get_summary(date_from=date_from, date_to=date_to)
        summary["_source"] = "cache_fallback"
        return jsonify(summary)


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


@data_bp.route("/daily-counts")
def get_daily_counts():
    """Get daily prompt counts - query Athena for accurate real-time data."""
    date_from = request.args.get("date_from", None)
    date_to = request.args.get("date_to", None)
    source = request.args.get("source", "athena")
    try:
        if source == "cache":
            counts = cache_service.get_daily_counts(date_from=date_from, date_to=date_to)
        else:
            counts = athena_service.fetch_daily_counts_live(
                date_from=date_from, date_to=date_to
            )
        return jsonify(counts)
    except Exception:
        counts = cache_service.get_daily_counts(date_from=date_from, date_to=date_to)
        return jsonify(counts)


@data_bp.route("/export")
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
