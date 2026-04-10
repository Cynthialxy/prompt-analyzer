"""Celery configuration and task definitions (Phase 3)."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_celery_app = None


def get_celery_app():
    """Lazy-init Celery app."""
    global _celery_app
    if _celery_app is not None:
        return _celery_app

    try:
        from celery import Celery
        from app.config import settings

        _celery_app = Celery(
            "prompt_analyzer",
            broker=settings.celery_broker_url,
            backend=settings.celery_result_backend,
        )
        _celery_app.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            timezone="UTC",
            enable_utc=True,
            task_track_started=True,
            task_time_limit=1800,  # 30 min hard limit
            task_soft_time_limit=1500,  # 25 min soft limit
            worker_prefetch_multiplier=1,
            worker_concurrency=2,
        )
        logger.info("Celery app initialized: broker=%s", settings.celery_broker_url)
        return _celery_app
    except ImportError:
        logger.warning("Celery not installed, async tasks unavailable")
        return None


def is_available() -> bool:
    from app.config import settings
    return settings.celery_enabled


# ---- Task definitions ----
# These are importable by the Celery worker process.
# Usage: from app.celery_config import task_run_bertopic; task_run_bertopic.delay()

def _register_tasks():
    """Register Celery tasks (called once on app init)."""
    app = get_celery_app()
    if not app:
        return

    @app.task(name="pipeline.run_full", bind=True)
    def task_run_full_pipeline(self):
        """Run the full 22-step pipeline as async task."""
        from app.services import pipeline_service
        run_id = pipeline_service.start_pipeline()
        return {"run_id": run_id, "status": "started"}

    @app.task(name="analysis.bertopic", bind=True)
    def task_run_bertopic(self):
        """Run BERTopic topic modeling."""
        from app.services import bertopic_service
        return bertopic_service.compute_bertopic()

    @app.task(name="analysis.user_segments", bind=True)
    def task_run_user_segments(self):
        """Run user segmentation."""
        from app.services import user_service
        return user_service.compute_user_segments()

    @app.task(name="analysis.retention", bind=True)
    def task_run_retention(self):
        """Run retention analysis."""
        from app.services import retention_service
        return retention_service.compute_retention()

    @app.task(name="analysis.embeddings", bind=True)
    def task_build_embeddings(self):
        """Build FAISS index."""
        from app.services import embedding_service
        return {"indexed": embedding_service.build_index()}

    @app.task(name="analysis.effect", bind=True)
    def task_run_effect(self, metric="like_count"):
        """Run effect analysis."""
        from app.services import effect_service
        return effect_service.compute_effect_analysis(metric)

    @app.task(name="analysis.templates", bind=True)
    def task_mine_templates(self):
        """Mine hot templates."""
        from app.services import template_service
        return template_service.mine_hot_templates()

    @app.task(name="analysis.user_paths", bind=True)
    def task_run_user_paths(self):
        """Run user path analysis."""
        from app.services import path_service
        return path_service.compute_user_paths()

    return {
        "pipeline.run_full": task_run_full_pipeline,
        "analysis.bertopic": task_run_bertopic,
        "analysis.user_segments": task_run_user_segments,
        "analysis.retention": task_run_retention,
        "analysis.embeddings": task_build_embeddings,
        "analysis.effect": task_run_effect,
        "analysis.templates": task_mine_templates,
        "analysis.user_paths": task_run_user_paths,
    }
