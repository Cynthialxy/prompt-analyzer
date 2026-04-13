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
    return _start(incremental_sync=False)


def start_sync_and_analyze() -> int:
    return _start(incremental_sync=True)


def _start(incremental_sync: bool) -> int:
    global _current_run_id

    with _lock:
        if _current_run_id:
            run = cache_service.get_analysis_run(_current_run_id)
            if run and run["status"] == "running":
                return _current_run_id

        latest = cache_service.get_latest_analysis_run()
        if latest and latest["status"] == "running":
            cache_service.update_analysis_run(
                latest["id"], status="failed",
                error="Interrupted by backend restart"
            )

    run_id = cache_service.save_analysis_run()
    _current_run_id = run_id

    thread = threading.Thread(
        target=_run_pipeline, args=(run_id, incremental_sync), daemon=True
    )
    thread.start()
    return run_id


def get_status() -> dict:
    if _current_run_id:
        run = cache_service.get_analysis_run(_current_run_id)
        if run:
            return run
    latest = cache_service.get_latest_analysis_run()
    return latest or {"status": "no_runs", "progress": 0}


def _run_pipeline(run_id: int, incremental_sync: bool = False):
    global _current_run_id
    try:
        # ── Phase 1: 数据同步 ──
        if incremental_sync:
            _update(run_id, "running", "正在连接 Athena，准备增量同步...", 0.0,
                    phase="sync", phase_progress=0.1)
            new_count = athena_service.fetch_incremental()
            logger.info("Incremental sync: %d new rows", new_count)
            _update(run_id, "running", f"数据同步完成，新增 {new_count:,} 条", 0.0,
                    phase="sync", phase_progress=1.0)
        else:
            count = cache_service.get_prompt_count()
            if count == 0:
                _update(run_id, "running", "从 Athena 拉取数据...", 0.0,
                        phase="sync", phase_progress=0.1)
                row_count = athena_service.fetch_and_cache_prompts()
                _update(run_id, "running", f"数据同步完成，共 {row_count:,} 条", 0.0,
                        phase="sync", phase_progress=1.0)
            else:
                _update(run_id, "running", f"使用已缓存数据（{count:,} 条）", 0.0,
                        phase="sync", phase_progress=1.0)

        # ── Phase 2: 数据分析 ──
        _update(run_id, "running", "加载数据...", 0.05, phase="analysis", phase_progress=0.02)
        df = cache_service.get_prompts_df()
        df = df[df["prompt"].fillna("").str.strip() != ""].reset_index(drop=True)
        total = len(df)
        logger.info("Pipeline working with %d non-empty prompts", total)

        if df.empty:
            _update(run_id, "completed", "无数据", 1.0, phase="analysis", phase_progress=1.0)
            return

        _update(run_id, "running", f"语言检测（共 {total:,} 条）", 0.10, phase="analysis", phase_progress=0.06)
        lang_result = nlp_service.analyze_languages(df)
        cache_service.save_analysis_result(run_id, "language", lang_result)
        lang_count = len(lang_result.get("distribution", []))
        _update(run_id, "running", f"语言检测完成，检测到 {lang_count} 种语言", 0.10,
                phase="analysis", phase_progress=0.08)

        _update(run_id, "running", "文本统计...", 0.18, phase="analysis", phase_progress=0.12)
        stats_result = nlp_service.analyze_text_statistics(df)
        cache_service.save_analysis_result(run_id, "text_stats", stats_result)
        avg_len = stats_result.get("avg_length", 0)
        _update(run_id, "running", f"文本统计完成，平均长度 {avg_len:.0f} 字符", 0.18,
                phase="analysis", phase_progress=0.14)

        _update(run_id, "running", "关键词提取 (TF-IDF)...", 0.26, phase="analysis", phase_progress=0.20)
        kw_result = nlp_service.extract_keywords(df)
        cache_service.save_analysis_result(run_id, "keywords", {"keywords": kw_result["keywords"]})
        kw_count = len(kw_result.get("keywords", []))
        _update(run_id, "running", f"关键词提取完成，共 {kw_count} 个关键词", 0.26,
                phase="analysis", phase_progress=0.24)

        _update(run_id, "running", "主题建模 (LDA + t-SNE)...", 0.36, phase="analysis", phase_progress=0.30)
        topic_result = nlp_service.build_topic_model(
            kw_result["sample_df"], kw_result["tfidf_matrix"], kw_result["feature_names"]
        )
        cache_service.save_analysis_result(run_id, "topics", topic_result)
        n_topics = topic_result.get("n_topics", 0)
        _update(run_id, "running", f"主题建模完成，发现 {n_topics} 个主题", 0.36,
                phase="analysis", phase_progress=0.34)

        _update(run_id, "running", "趋势分析...", 0.44, phase="analysis", phase_progress=0.38)
        trend_result = nlp_service.analyze_trends(df)
        cache_service.save_analysis_result(run_id, "trends", trend_result)

        _update(run_id, "running", "意图分析...", 0.50, phase="analysis", phase_progress=0.44)
        try:
            from app.services import intent_v2_service
            intent_v2_result = intent_v2_service.compute_intent_distribution(sample_limit=15000)
            cache_service.save_analysis_result(run_id, "intents_v2", intent_v2_result)
            top = (intent_v2_result.get("distribution") or [{}])[0]
            _update(run_id, "running",
                    f"意图分析完成，Top: {top.get('label','')} {top.get('percentage',0):.0f}%",
                    0.50, phase="analysis", phase_progress=0.47)
        except Exception as e:
            logger.warning("Intent v2 skipped: %s", e)

        _update(run_id, "running", "意图分类 (Claude API)...", 0.52, phase="analysis", phase_progress=0.46)
        try:
            intent_result = llm_service.classify_intents(df)
            cache_service.save_analysis_result(run_id, "intents", intent_result)
        except Exception as e:
            logger.warning("Intent classification skipped: %s", e)
            cache_service.save_analysis_result(run_id, "intents", {"distribution": [], "error": str(e)})

        _update(run_id, "running", "质量评估 (Claude API)...", 0.58, phase="analysis", phase_progress=0.52)
        try:
            quality_result = llm_service.assess_quality(df)
            cache_service.save_analysis_result(run_id, "quality", quality_result)
        except Exception as e:
            logger.warning("Quality assessment skipped: %s", e)
            cache_service.save_analysis_result(run_id, "quality", {"scores": [], "error": str(e)})

        _update(run_id, "running", "主题总结 (Claude API)...", 0.62, phase="analysis", phase_progress=0.56)
        try:
            summary = cache_service.get_summary()
            categories = cache_service.get_category_distributions()
            theme = llm_service.generate_theme_summary(summary, categories, kw_result["keywords"][:20])
            cache_service.save_analysis_result(run_id, "theme_summary", {"text": theme})
        except Exception as e:
            logger.warning("Theme summary skipped: %s", e)

        _update(run_id, "running", "质量评估 v2 (Claude API)...", 0.65, phase="analysis", phase_progress=0.60)
        try:
            quality_v2 = llm_service.assess_quality_v2(df)
            cache_service.save_analysis_result(run_id, "quality_v2", quality_v2)
        except Exception as e:
            logger.warning("Quality v2 skipped: %s", e)

        _update(run_id, "running", "用户分层...", 0.70, phase="analysis", phase_progress=0.65)
        try:
            seg = user_service.compute_user_segments(days=90)
            total_users = seg.get("total_users", 0)
            _update(run_id, "running", f"用户分层完成，共 {total_users:,} 位用户", 0.70,
                    phase="analysis", phase_progress=0.68)
        except Exception as e:
            logger.warning("User segmentation skipped: %s", e)

        _update(run_id, "running", "向量索引 (FAISS)...", 0.75, phase="analysis", phase_progress=0.70)
        try:
            n_indexed = embedding_service.build_index()
            _update(run_id, "running", f"向量索引完成，索引 {n_indexed:,} 条", 0.75,
                    phase="analysis", phase_progress=0.73)
        except Exception as e:
            logger.warning("Embedding index skipped: %s", e)

        _update(run_id, "running", "效果分析...", 0.80, phase="analysis", phase_progress=0.76)
        try:
            eff = effect_service.compute_effect_analysis("like_count")
            hit_count = len(eff.get("hit_prompts", []))
            sig_count = eff.get("significant_count", 0)
            _update(run_id, "running",
                    f"效果分析完成，爆款 {hit_count} 条，显著特征 {sig_count} 个",
                    0.80, phase="analysis", phase_progress=0.78)
        except Exception as e:
            logger.warning("Effect analysis skipped: %s", e)

        _update(run_id, "running", "留存分析...", 0.84, phase="analysis", phase_progress=0.80)
        try:
            retention_service.compute_retention()
        except Exception as e:
            logger.warning("Retention analysis skipped: %s", e)

        _update(run_id, "running", "创作路径分析...", 0.87, phase="analysis", phase_progress=0.84)
        try:
            path_service.compute_user_paths()
        except Exception as e:
            logger.warning("User path analysis skipped: %s", e)

        _update(run_id, "running", "BERTopic 主题模型...", 0.90, phase="analysis", phase_progress=0.87)
        try:
            bt = bertopic_service.compute_bertopic()
            _update(run_id, "running",
                    f"主题模型完成，{bt.get('n_topics', 0)} 个主题 ({bt.get('model', '-')})",
                    0.90, phase="analysis", phase_progress=0.89)
        except Exception as e:
            logger.warning("BERTopic skipped: %s", e)

        _update(run_id, "running", "爆款模板挖掘...", 0.93, phase="analysis", phase_progress=0.91)
        try:
            tmpl = template_service.mine_hot_templates()
            tmpl_count = len(tmpl.get("templates", []))
            _update(run_id, "running", f"模板挖掘完成，共 {tmpl_count} 个模板", 0.93,
                    phase="analysis", phase_progress=0.92)
        except Exception as e:
            logger.warning("Template mining skipped: %s", e)

        _update(run_id, "running", "多指标效果分析...", 0.96, phase="analysis", phase_progress=0.95)
        try:
            effect_service.compute_effect_analysis("collect_count")
            effect_service.compute_effect_analysis("score")
        except Exception as e:
            logger.warning("Multi-metric effect analysis skipped: %s", e)

        _update(run_id, "completed", "分析完成", 1.0, phase="analysis", phase_progress=1.0)
        logger.info("Pipeline completed for run %d", run_id)

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
    logger.info("[Run %d] %s (%.0f%%)", run_id, step, progress * 100)
