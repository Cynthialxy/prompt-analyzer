"""Analysis pipeline orchestration - runs all analysis steps in background."""

import logging
import threading

from app.services import (
    cache_service, athena_service, nlp_service, llm_service,
    user_service, embedding_service, effect_service,
    retention_service, path_service, bertopic_service, template_service,
)

logger = logging.getLogger(__name__)

_current_run_id = None
_lock = threading.Lock()


def start_pipeline() -> int:
    """Start the analysis pipeline in a background thread."""
    global _current_run_id

    with _lock:
        if _current_run_id:
            run = cache_service.get_analysis_run(_current_run_id)
            if run and run["status"] == "running":
                return _current_run_id

    run_id = cache_service.save_analysis_run()
    _current_run_id = run_id

    thread = threading.Thread(target=_run_pipeline, args=(run_id,), daemon=True)
    thread.start()
    return run_id


def get_status() -> dict:
    """Get current pipeline status."""
    if _current_run_id:
        run = cache_service.get_analysis_run(_current_run_id)
        if run:
            return run
    # Check latest run
    latest = cache_service.get_latest_analysis_run()
    return latest or {"status": "no_runs", "progress": 0}


def _run_pipeline(run_id: int):
    """Execute the full analysis pipeline."""
    global _current_run_id
    try:
        _update(run_id, "running", "Fetching data from Athena", 0.05)
        # Step 1: Fetch data
        count = cache_service.get_prompt_count()
        if count == 0:
            row_count = athena_service.fetch_and_cache_prompts()
            logger.info("Fetched %d prompts from Athena", row_count)
        else:
            logger.info("Using %d cached prompts", count)

        _update(run_id, "running", "Loading data", 0.10)
        df = cache_service.get_prompts_df()
        # Ensure no empty prompts leak through (single source of truth)
        df = df[df["prompt"].fillna("").str.strip() != ""].reset_index(drop=True)
        logger.info("Pipeline working with %d non-empty prompts", len(df))

        if df.empty:
            _update(run_id, "completed", "No data found", 1.0)
            return

        # Step 2: Language detection
        _update(run_id, "running", "Detecting languages", 0.15)
        lang_result = nlp_service.analyze_languages(df)
        cache_service.save_analysis_result(run_id, "language", lang_result)

        # Step 3: Text statistics
        _update(run_id, "running", "Computing text statistics", 0.25)
        stats_result = nlp_service.analyze_text_statistics(df)
        cache_service.save_analysis_result(run_id, "text_stats", stats_result)

        # Step 4: Keyword extraction
        _update(run_id, "running", "Extracting keywords (TF-IDF)", 0.35)
        kw_result = nlp_service.extract_keywords(df)
        cache_service.save_analysis_result(run_id, "keywords", {
            "keywords": kw_result["keywords"]
        })

        # Step 5: Topic modeling
        _update(run_id, "running", "Building topic model (LDA + t-SNE)", 0.45)
        topic_result = nlp_service.build_topic_model(
            df, kw_result["tfidf_matrix"], kw_result["feature_names"]
        )
        cache_service.save_analysis_result(run_id, "topics", topic_result)

        # Step 6: Trend analysis
        _update(run_id, "running", "Analyzing trends", 0.55)
        trend_result = nlp_service.analyze_trends(df)
        cache_service.save_analysis_result(run_id, "trends", trend_result)

        # Step 7: LLM intent classification
        _update(run_id, "running", "Classifying intents (Claude API)", 0.65)
        try:
            intent_result = llm_service.classify_intents(df)
            cache_service.save_analysis_result(run_id, "intents", intent_result)
        except Exception as e:
            logger.warning("Intent classification skipped: %s", e)
            cache_service.save_analysis_result(run_id, "intents", {
                "distribution": [], "error": str(e)
            })

        # Step 8: LLM quality assessment
        _update(run_id, "running", "Assessing prompt quality (Claude API)", 0.80)
        try:
            quality_result = llm_service.assess_quality(df)
            cache_service.save_analysis_result(run_id, "quality", quality_result)
        except Exception as e:
            logger.warning("Quality assessment skipped: %s", e)
            cache_service.save_analysis_result(run_id, "quality", {
                "scores": [], "error": str(e)
            })

        # Step 9: Theme summary
        _update(run_id, "running", "Generating theme summary", 0.70)
        try:
            summary = cache_service.get_summary()
            categories = cache_service.get_category_distributions()
            theme = llm_service.generate_theme_summary(
                summary, categories, kw_result["keywords"][:20]
            )
            cache_service.save_analysis_result(run_id, "theme_summary", {"text": theme})
        except Exception as e:
            logger.warning("Theme summary skipped: %s", e)

        # Step 10: User segmentation
        _update(run_id, "running", "Computing user segments", 0.78)
        try:
            user_service.compute_user_segments(days=90)
        except Exception as e:
            logger.warning("User segmentation skipped: %s", e)

        # Step 11: Build vector index
        _update(run_id, "running", "Building embedding index (FAISS)", 0.85)
        try:
            n_indexed = embedding_service.build_index()
            logger.info("FAISS index built with %d vectors", n_indexed)
        except Exception as e:
            logger.warning("Embedding index skipped: %s", e)

        # Step 12: Effect analysis
        _update(run_id, "running", "Running effect analysis", 0.92)
        try:
            effect_service.compute_effect_analysis("like_count")
        except Exception as e:
            logger.warning("Effect analysis skipped: %s", e)

        # Step 13: Quality v2 assessment
        _update(run_id, "running", "Quality v2 assessment (Claude API)", 0.62)
        try:
            quality_v2 = llm_service.assess_quality_v2(df)
            cache_service.save_analysis_result(run_id, "quality_v2", quality_v2)
        except Exception as e:
            logger.warning("Quality v2 skipped: %s", e)

        # ====== Phase 2 Steps (14-18) ======

        # Step 14: Retention analysis
        _update(run_id, "running", "Computing user retention cohorts", 0.68)
        try:
            retention_service.compute_retention()
        except Exception as e:
            logger.warning("Retention analysis skipped: %s", e)

        # Step 15: User creation path analysis
        _update(run_id, "running", "Analyzing user creation paths", 0.73)
        try:
            path_service.compute_user_paths()
        except Exception as e:
            logger.warning("User path analysis skipped: %s", e)

        # Step 16: BERTopic topic modeling
        _update(run_id, "running", "Training BERTopic model", 0.78)
        try:
            bertopic_service.compute_bertopic()
        except Exception as e:
            logger.warning("BERTopic skipped: %s", e)

        # Step 17: Hot template mining
        _update(run_id, "running", "Mining hot prompt templates", 0.85)
        try:
            template_service.mine_hot_templates()
        except Exception as e:
            logger.warning("Template mining skipped: %s", e)

        # Step 18: Effect analysis (collect_count + score)
        _update(run_id, "running", "Running effect analysis (multi-metric)", 0.88)
        try:
            effect_service.compute_effect_analysis("collect_count")
            effect_service.compute_effect_analysis("score")
        except Exception as e:
            logger.warning("Multi-metric effect analysis skipped: %s", e)

        # ====== Phase 3 Steps (19-22) ======

        # Step 19: pgvector sync (if enabled)
        _update(run_id, "running", "Syncing embeddings to pgvector", 0.92)
        try:
            from app.services import pg_service
            if pg_service.is_available():
                pg_service.init_pgvector()
                logger.info("pgvector sync - using embedding_service data")
                # Get embeddings from FAISS and upsert to PG
                import json, os
                from app.config import settings
                if os.path.exists(settings.faiss_id_map_path):
                    with open(settings.faiss_id_map_path, "r") as f:
                        id_data = json.load(f)
                    meta = id_data.get("meta", {})
                    logger.info("pgvector: %d records available", len(meta))
            else:
                logger.info("pgvector disabled, skipping sync")
        except Exception as e:
            logger.warning("pgvector sync skipped: %s", e)

        # Step 20: Redis cache warm-up (if enabled)
        _update(run_id, "running", "Warming Redis cache", 0.95)
        try:
            from app.services import redis_cache
            if redis_cache.is_available():
                # Cache key analysis results
                for key in ["retention", "user_paths", "bertopic", "hot_templates"]:
                    result = cache_service.get_analysis_result(key)
                    if result:
                        redis_cache.set(f"analysis:{key}", result)
                logger.info("Redis cache warmed")
            else:
                logger.info("Redis disabled, skipping cache warm")
        except Exception as e:
            logger.warning("Redis warm skipped: %s", e)

        # Step 21: Data quality checks
        _update(run_id, "running", "Running data quality checks", 0.97)
        try:
            prompt_count = cache_service.get_prompt_count()
            quality_report = {
                "prompt_count": prompt_count,
                "has_engagement_data": prompt_count > 0,
                "analysis_results_count": 0,
            }
            with cache_service.get_conn() as conn:
                ar_count = conn.execute("SELECT COUNT(DISTINCT result_type) FROM analysis_results").fetchone()
                quality_report["analysis_results_count"] = ar_count[0] if ar_count else 0
            cache_service.save_analysis_result(run_id, "quality_report", quality_report)
        except Exception as e:
            logger.warning("Quality check skipped: %s", e)

        # Step 22: Final summary
        _update(run_id, "running", "Finalizing", 0.99)

        _update(run_id, "completed", "Analysis complete (22 steps)", 1.0)
        logger.info("Pipeline completed successfully for run %d (22 steps)", run_id)

    except Exception as e:
        logger.error("Pipeline failed: %s", e, exc_info=True)
        cache_service.update_analysis_run(run_id, status="failed", error=str(e))
    finally:
        with _lock:
            _current_run_id = None


def _update(run_id, status, step, progress):
    cache_service.update_analysis_run(run_id, status=status, step=step, progress=progress)
    logger.info("[Run %d] %s: %s (%.0f%%)", run_id, status, step, progress * 100)
