"""Pipeline routes: trigger and monitor analysis pipeline."""

from flask import Blueprint, jsonify

from app.services import pipeline_service, cache_service

pipeline_bp = Blueprint("pipeline", __name__)


@pipeline_bp.route("/run", methods=["POST"])
def run_pipeline():
    run_id = pipeline_service.start_pipeline()
    return jsonify({"run_id": run_id, "status": "started"})


@pipeline_bp.route("/status")
def get_status():
    status = pipeline_service.get_status()
    return jsonify(status)


@pipeline_bp.route("/runs")
def get_runs():
    """Return recent pipeline run history (newest first)."""
    runs = cache_service.get_analysis_runs(limit=20)
    return jsonify(runs)


@pipeline_bp.route("/runs/<int:run_id>")
def get_run_detail(run_id: int):
    """Return a single run with its step details."""
    run = cache_service.get_analysis_run(run_id)
    if not run:
        return jsonify({"error": "Run not found"}), 404
    steps = cache_service.get_run_steps(run_id)
    return jsonify({**run, "steps": steps})
