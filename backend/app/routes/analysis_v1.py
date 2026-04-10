"""V1 analysis routes: user segments, prompt intent/quality/similar, effect, retention, path, topics, templates."""

from flask import Blueprint, request, jsonify

from app.services import (
    cache_service, embedding_service, effect_service,
    user_service, llm_service, retention_service,
    path_service, bertopic_service, template_service,
)

analysis_v1_bp = Blueprint("analysis_v1", __name__)


# --- User Endpoints ---

@analysis_v1_bp.route("/user/segment")
def get_user_segments():
    """Get user segmentation overview."""
    segment = request.args.get("segment", None)
    sort_by = request.args.get("sort_by", "total_prompts")
    limit = request.args.get("limit", 100, type=int)

    try:
        result = user_service.get_segment_overview(
            segment=segment, sort_by=sort_by, limit=limit
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@analysis_v1_bp.route("/user/profile")
def get_user_profile():
    """Get detailed user profile."""
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400

    try:
        result = user_service.get_user_profile(user_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Prompt Endpoints ---

@analysis_v1_bp.route("/prompt/intent")
def get_prompt_intent():
    """Get intent classification. Single prompt (project_id) or batch distribution."""
    project_id = request.args.get("project_id")

    if project_id:
        # Single prompt analysis
        with cache_service.get_conn() as conn:
            row = conn.execute(
                "SELECT prompt FROM prompts WHERE project_id = ?", (project_id,)
            ).fetchone()
        if not row or not row["prompt"]:
            return jsonify({"error": "Prompt not found"}), 404

        result = llm_service.classify_intent_v2(row["prompt"])
        result["project_id"] = project_id
        result["prompt"] = row["prompt"]
        return jsonify(result)
    else:
        # Batch distribution (from cached analysis)
        result = cache_service.get_analysis_result("intents")
        if not result:
            return jsonify({"error": "No intent analysis. Run the pipeline first."}), 404
        return jsonify(result)


@analysis_v1_bp.route("/prompt/quality")
def get_prompt_quality():
    """Get quality assessment. Single prompt (project_id) or aggregate."""
    project_id = request.args.get("project_id")

    if project_id:
        # Single prompt quality
        with cache_service.get_conn() as conn:
            row = conn.execute(
                "SELECT prompt FROM prompts WHERE project_id = ?", (project_id,)
            ).fetchone()
        if not row or not row["prompt"]:
            return jsonify({"error": "Prompt not found"}), 404

        result = llm_service.classify_intent_v2(row["prompt"])
        result["project_id"] = project_id
        result["prompt"] = row["prompt"]
        return jsonify(result)
    else:
        # Aggregate quality (from cached analysis)
        result = cache_service.get_analysis_result("quality_v2")
        if not result:
            result = cache_service.get_analysis_result("quality")
        if not result:
            return jsonify({"error": "No quality analysis. Run the pipeline first."}), 404
        return jsonify(result)


@analysis_v1_bp.route("/prompt/similar")
def get_similar_prompts():
    """Find similar prompts via vector search."""
    project_id = request.args.get("project_id")
    query = request.args.get("query")
    top_k = request.args.get("top_k", 10, type=int)
    top_k = min(top_k, 50)

    try:
        if project_id:
            results = embedding_service.search_similar_by_id(project_id, top_k=top_k)
            query_prompt = None
            with cache_service.get_conn() as conn:
                row = conn.execute(
                    "SELECT prompt FROM prompts WHERE project_id = ?", (project_id,)
                ).fetchone()
                if row:
                    query_prompt = row["prompt"]
        elif query:
            results = embedding_service.search_similar(query, top_k=top_k)
            query_prompt = query
        else:
            return jsonify({"error": "project_id or query is required"}), 400

        info = embedding_service.get_index_info()
        return jsonify({
            "query_prompt": query_prompt,
            "results": results,
            "index_size": info.get("size", 0),
            "model": info.get("model", ""),
        })
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Effect Analysis ---

@analysis_v1_bp.route("/effect")
def get_effect_analysis():
    """Get effect analysis: always compute fresh from Athena."""
    metric = request.args.get("metric", "like_count")
    try:
        result = effect_service.compute_effect_analysis(metric=metric)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Phase 2: Retention ---

@analysis_v1_bp.route("/user/retention")
def get_user_retention():
    """Get user retention cohort analysis."""
    # Try cached first
    result = cache_service.get_analysis_result("retention")
    if result:
        return jsonify(result)
    try:
        result = retention_service.compute_retention()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Phase 2: User Path ---

@analysis_v1_bp.route("/user/path")
def get_user_path():
    """Get user creation path analysis (Sankey)."""
    result = cache_service.get_analysis_result("user_paths")
    if result:
        return jsonify(result)
    try:
        result = path_service.compute_user_paths()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Phase 2: BERTopic ---

@analysis_v1_bp.route("/prompt/topics")
def get_bertopic_topics():
    """Get BERTopic analysis results."""
    result = cache_service.get_analysis_result("bertopic")
    if result and result.get("topic_prompt_samples") is not None:
        return jsonify(result)
    try:
        result = bertopic_service.compute_bertopic()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- Phase 2: Hot Templates ---

@analysis_v1_bp.route("/prompt/hot-templates")
def get_hot_templates():
    """Get hot prompt templates mined from high-engagement prompts."""
    metric = request.args.get("metric", "like_count")
    try:
        result = template_service.mine_hot_templates(metric=metric)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
