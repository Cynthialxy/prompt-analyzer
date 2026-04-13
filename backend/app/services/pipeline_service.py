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
    """Start the analysis pipeline in a background thread (uses existing cache data)."""
    return _start(incremental_sync=False)


def start_sync_and_analyze() -> int:
    """Incremental sync from Athena then run full analysis pipeline."""
    return _start(incremental_sync=True)


def _start(incremental_sync: bool) -> int:
    global _current_run_id

    with _lock:
        if _current_run_id:
            run = cache_service.get_analysis_run(_current_run_id)
            if run and run["status"] == "running":
                return _current_run_id

    run_id = cache_service.save_analysis_run()
    _current_run_id = run_id

    thread = threading.Thread(
        target=_run_pipeline, args=(run_id, incremental_sync), daemon=True
    )
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


def _run_pipeline(run_id: int, incremental_sync: bool = False):
    """Execute the full analysis pipeline."""
    global _current_run_id
    try:
        if incremental_sync:
            # ── Phase 1: 数据同步 ──
            _update(run_id, "running", "正在增量同步最新数据...", 0.0,
                    phase="sync", phase_progress=0.1)
            new_count = athena_service.fetch_incremental()
            logger.info("Incremental sync: %d new rows", new_count)
            _update(run_id, "running", f"同步完成，新增 {new_count} 条数据", 0.0,
                    phase="sync", phase_progress=1.0)
        else:
            count = cache_service.get_prompt_count()
            if count == 0:
                _update(run_id, "running", "Fetching data from Athena", 0.0,
                        phase="sync", phase_progress=0.1)
                row_count = athena_service.fetch_and_cache_prompts()
                logger.info("Fetched %d prompts from Athena", row_count)
                _update(run_id, "running", "同步完成", 0.0,
                        phase="sync", phase_progress=1.0)
            else:
                _update(run_id, "running", "使用已缓存数据", 0.0,
                        phase="sync", phase_progress=1.0)

        # ── Phase 2: 数据分析 ──
        _update(run_id, "running", "加载数据", 0.05, phase="analysis", phase_progress=0.02)
        df = cache_service.get_prompts_df()
        df = df[df["prompt"].fillna("").str.strip() != ""].reset_index(drop=True)
        logger.info("Pipeline working with %d non-empty prompts", len(df))

        if df.empty:
            _update(run_id, "completed", "No data found", 1.0, phase="analysis", phase_progress=1.0)
            return

        _update(run_id, "running", "语言检测", 0.10, phase="analysis", phase_progress=0.06)
        lang_result = nlp_service.analyze_languages(df)
        cache_service.save_analysis_result(run_id, "language", lang_result)

        _update(run_id, "running", "文本统计", 0.18, phase="analysis", phase_progress=0.12)
        stats_result = nlp_service.analyze_text_statistics(df)
        cache_service.save_analysis_result(run_id, "text_stats", stats_result)

        _update(run_id, "running", "关键词提取 (TF-IDF)", 0.26, phase="analysis", phase_progress=0.20)
        kw_result = nlp_service.extract_keywords(df)
        cache_service.save_analysis_result(run_id, "keywords", {"keywords": kw_result["keywords"]})

        _update(run_id, "running", "主题建模 (LDA + t-SNE)", 0.36, phase="analysis", phase_progress=0.30)
        topic_result = nlp_service.build_topic_model(
            kw_result["sample_df"], kw_result["tfidf_matrix"], kw_result["feature_names"]
        )
        cache_service.save_analysis_result(run_id, "topics", topic_result)

        _update(run_id, "running", "趋势分析", 0.44, phase="analysis", phase_progress=0.38)
        trend_result = nlp_service.analyze_trends(df)
        cache_service.save_analysis_result(run_id, "trends", trend_result)

        _update(run_id, "running", "意图分类 (Claude API)", 0.52, phase="analysis", phase_progress=0.46)
        try:
            intent_result = llm_service.classify_intents(df)
            cache_service.save_analysis_result(run_id, "intents", intent_result)
        except Exception as e:
            logger.warning("Intent classification skipped: %s", e)
            cache_service.save_analysis_result(run_id, "intents", {"distribution": [], "error": str(e)})

        _update(run_id, "running", "质量评估 (Claude API)", 0.58, phase="analysis", phase_progress=0.52)
        try:
            quality_result = llm_service.assess_quality(df)
            cache_service.save_analysis_result(run_id, "quality", quality_result)
        except Exception as e:
            logger.warning("Quality assessment skipped: %s", e)
            cache_service.save_analysis_result(run_id, "quality", {"scores": [], "error": str(e)})

        _update(run_id, "running", "主题总结 (Claude API)", 0.62, phase="analysis", phase_progress=0.56)
        try:
            summary = cache_service.get_summary()
            categories = cache_service.get_category_distributions()
            theme = llm_service.generate_theme_summary(summary, categories, kw_result["keywords"][:20])
            cache_service.save_analysis_result(run_id, "theme_summary", {"text": theme})
        except Exception as e:
            logger.warning("Theme summary skipped: %s", e)

        _update(run_id, "running", "质量评估 v2 (Claude API)", 0.65, phase="analysis", phase_progress=0.60)
        try:
            quality_v2 = llm_service.assess_quality_v2(df)
            cache_service.save_analysis_result(run_id, "quality_v2", quality_v2)
        except Exception as e:
            logger.warning("Quality v2 skipped: %s", e)

        _update(run_id, "running", "用户分层", 0.70, phase="analysis", phase_progress=0.65)
        try:
            user_service.compute_user_segments(days=90)
        except Exception as e:
            logger.warning("User segmentation skipped: %s", e)

        _update(run_id, "running", "向量索引 (FAISS)", 0.75, phase="analysis", phase_progress=0.70)
        try:
            n_indexed = embedding_service.build_index()
            logger.info("FAISS index built with %d vectors", n_indexed)
        except Exception as e:
            logger.warning("Embedding index skipped: %s", e)

        _update(run_id, "running", "效果分析", 0.80, phase="analysis", phase_progress=0.76)
        try:
            effect_service.compute_effect_analysis("like_count")
        except Exception as e:
            logger.warning("Effect analysis skipped: %s", e)

        _update(run_id, "running", "留存分析", 0.84, phase="analysis", phase_progress=0.80)
        try:
            retention_service.compute_retention()
        except Exception as e:
            logger.warning("Retention analysis skipped: %s", e)

        _update(run_id, "running", "创作路径分析", 0.87, phase="analysis", phase_progress=0.84)
        try:
            path_service.compute_user_paths()
        except Exception as e:
            logger.warning("User path analysis skipped: %s", e)

        _update(run_id, "running", "BERTopic 主题模型", 0.90, phase="analysis", phase_progress=0.87)
        try:
            bertopic_service.compute_bertopic()
        except Exception as e:
            logger.warning("BERTopic skipped: %s", e)

        _update(run_id, "running", "爆款模板挖掘", 0.93, phase="analysis", phase_progress=0.91)
        try:
            template_service.mine_hot_templates()
        except Exception as e:
            logger.warning("Template mining skipped: %s", e)

        _update(run_id, "running", "多指标效果分析", 0.96, phase="analysis", phase_progress=0.95)
        try:
            effect_service.compute_effect_analysis("collect_count")
            effect_service.compute_effect_analysis("score")
        except Exception as e:
            logger.warning("Multi-metric effect analysis skipped: %s", e)

        _update(run_id, "running", "收尾", 0.99, phase="analysis", phase_progress=0.99)

        # pgvector / Redis (optional, skip silently)
        try:
            from app.services import pg_service
            if pg_service.is_available():
                pg_service.init_pgvector()
        except Exception:
            pass
        try:
            from app.services import redis_cache
            if redis_cache.is_available():
                for key in ["retention", "user_paths", "bertopic", "hot_templates"]:
                    result = cache_service.get_analysis_result(key)
                    if result:
                        redis_cache.set(f"analysis:{key}", result)
        except Exception:
            pass

        _update(run_id, "completed", "分析完成", 1.0, phase="analysis", phase_progress=1.0)
        logger.info("Pipeline completed successfully for run %d", run_id)

    except Exception as e:
        logger.error("Pipeline failed: %s", e, exc_info=True)
        cache_service.update_analysis_run(run_id, status="failed", error=str(e))
    finally:
        with _lock:
            _current_run_id = None


def _update(run_id, status, step, progress, phase="analysis", phase_progress=None):
    cache_service.update_analysis_run(
        run_id, status=status, step=step, progress=progress,
        phase=phase, phase_progress=phase_progress if phase_progress is not None else progress,
    )
    logger.info("[Run %d] %s: %s (%.0f%%)", run_id, status, step, progress * 100)
