"""Pipeline routes: trigger and monitor analysis pipeline."""

from flask import Blueprint, jsonify

from app.services import pipeline_service

pipeline_bp = Blueprint("pipeline", __name__)


@pipeline_bp.route("/run", methods=["POST"])
def run_pipeline():
    """Start the analysis pipeline."""
    run_id = pipeline_service.start_pipeline()
    return jsonify({"run_id": run_id, "status": "started"})


@pipeline_bp.route("/status")
def get_status():
    """Get pipeline status."""
    status = pipeline_service.get_status()
    return jsonify(status)
