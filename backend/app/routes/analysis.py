"""Analysis routes: categories, topics, intents, language, trends."""

from flask import Blueprint, jsonify

from app.services import cache_service

analysis_bp = Blueprint("analysis", __name__)


@analysis_bp.route("/categories")
def get_categories():
    """Get category/tag distributions from cache."""
    result = cache_service.get_category_distributions()
    return jsonify(result)


@analysis_bp.route("/topics")
def get_topics():
    """Get topic clustering results."""
    result = cache_service.get_analysis_result("topics")
    if not result:
        return jsonify({"topics": [], "n_topics": 0})
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


@analysis_bp.route("/language")
def get_language():
    """Get language and text statistics."""
    lang = cache_service.get_analysis_result("language")
    stats = cache_service.get_analysis_result("text_stats")
    quality = cache_service.get_analysis_result("quality")

    if not lang:
        return jsonify({"language": {}, "text_stats": {}, "quality": {}})

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
        return jsonify({"trends": [], "weekly": [], "monthly": []})
    return jsonify(result)


@analysis_bp.route("/keywords")
def get_keywords():
    """Get extracted keywords."""
    result = cache_service.get_analysis_result("keywords")
    if not result:
        return jsonify({"keywords": []})
    return jsonify(result)


@analysis_bp.route("/theme-summary")
def get_theme_summary():
    """Get LLM-generated theme summary."""
    result = cache_service.get_analysis_result("theme_summary")
    if not result:
        return jsonify({"text": "No theme summary available. Run the pipeline first."})
    return jsonify(result)
