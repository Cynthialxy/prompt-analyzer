"""Analysis routes: categories, topics, intents, language, trends."""

from flask import Blueprint, jsonify

from app.services import cache_service, athena_service

analysis_bp = Blueprint("analysis", __name__)


@analysis_bp.route("/categories")
def get_categories():
    """Get category/tag distributions - query Athena for accurate data."""
    try:
        result = athena_service.fetch_category_distributions()
        return jsonify(result)
    except Exception:
        result = cache_service.get_category_distributions()
        return jsonify(result)


@analysis_bp.route("/topics")
def get_topics():
    """Get topic clustering results."""
    result = cache_service.get_analysis_result("topics")
    if not result:
        return jsonify({"error": "No topic analysis results. Run the pipeline first."}), 404
    return jsonify(result)


@analysis_bp.route("/intents")
def get_intents():
    """Get USER DEMAND INTENT distribution (v2: why users generate, not what)."""
    from app.services import intent_v2_service
    try:
        result = intent_v2_service.compute_intent_distribution(sample_limit=15000)
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def _get_intents_from_athena() -> dict:
    """Build intent distribution from Athena llm_category + sample prompts."""
    # Distribution
    dist_sql = """
        SELECT llm_category AS intent, COUNT(*) AS count
        FROM silver.clean_tripo_project
        WHERE prompt IS NOT NULL AND prompt != ''
          AND llm_category IS NOT NULL AND llm_category != ''
        GROUP BY llm_category
        ORDER BY count DESC
    """
    dist_result = athena_service.run_query(dist_sql)
    total = sum(int(r.get("count", 0)) for r in dist_result["rows"])
    distribution = [
        {
            "intent": r["intent"],
            "count": int(r["count"]),
            "percentage": round(int(r["count"]) / total * 100, 2) if total else 0,
        }
        for r in dist_result["rows"]
    ]

    # Sample prompts per intent (top 5)
    sample_prompts: dict = {}
    for item in distribution[:10]:
        intent = item["intent"]
        sample_sql = f"""
            SELECT prompt FROM silver.clean_tripo_project
            WHERE prompt IS NOT NULL AND prompt != ''
              AND llm_category = '{intent}'
            LIMIT 5
        """
        try:
            sample_result = athena_service.run_query(sample_sql)
            sample_prompts[intent] = [
                r["prompt"][:200] for r in sample_result["rows"]
                if r.get("prompt") and r["prompt"].strip()
            ]
        except Exception:
            sample_prompts[intent] = []

    return {
        "distribution": distribution,
        "sample_prompts": sample_prompts,
        "sample_size": total,
        "total_prompts": total,
        "source": "athena_llm_category",
    }


@analysis_bp.route("/language")
def get_language():
    """Get language and text statistics."""
    lang = cache_service.get_analysis_result("language")
    stats = cache_service.get_analysis_result("text_stats")
    quality = cache_service.get_analysis_result("quality")

    if not lang:
        return jsonify({"error": "No language analysis results. Run the pipeline first."}), 404

    # If quality is missing or summary is empty, compute from local data
    if not quality or not quality.get("summary"):
        quality = cache_service.compute_quality_from_prompts()

    return jsonify({
        "language": lang,
        "text_stats": stats or {},
        "quality": quality,
    })


@analysis_bp.route("/trends")
def get_trends():
    """Get trend analysis results."""
    result = cache_service.get_analysis_result("trends")
    if not result:
        return jsonify({"error": "No trend analysis results. Run the pipeline first."}), 404
    return jsonify(result)


@analysis_bp.route("/keywords")
def get_keywords():
    """Get extracted keywords."""
    result = cache_service.get_analysis_result("keywords")
    if not result:
        return jsonify({"error": "No keyword results. Run the pipeline first."}), 404
    return jsonify(result)


@analysis_bp.route("/theme-summary")
def get_theme_summary():
    """Get LLM-generated theme summary."""
    result = cache_service.get_analysis_result("theme_summary")
    if not result:
        return jsonify({"text": "No theme summary available. Run the pipeline first."})
    return jsonify(result)
