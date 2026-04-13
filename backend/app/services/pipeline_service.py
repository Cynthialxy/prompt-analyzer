"""Analysis pipeline orchestration - runs all analysis steps in background."""

import logging
import threading
from contextlib import contextmanager

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


@contextmanager
def _step(run_id: int, name: str, progress: float, phase: str = "analysis",
          phase_progress: float = None):
    """Context manager: records step start/end, duration, and handles errors."""
    _update(run_id, "running", name, progress, phase=phase,
            phase_progress=phase_progress if phase_progress is not None else progress)
    step_id = cache_service.start_run_step(run_id, name)
    result_holder = {"rows": None, "detail": None, "error": None}
    try:
        yield result_holder
        cache_service.finish_run_step(
            step_id, status="completed",
            rows_affected=result_holder["rows"],
            detail=result_holder["detail"],
        )
    except Exception as e:
        result_holder["error"] = str(e)
        cache_service.finish_run_step(step_id, status="failed", detail=str(e))
        logger.warning("[Run %d] Step '%s' failed: %s", run_id, name, e)


def _run_pipeline(run_id: int, incremental_sync: bool = False):
    global _current_run_id
    try:
        # ── Phase 1: 数据同步 ──
        if incremental_sync:
            with _step(run_id, "增量同步数据", 0.0, phase="sync", phase_progress=0.1) as s:
                new_count = athena_service.fetch_incremental()
                s["rows"] = new_count
                s["detail"] = f"新增 {new_count} 条数据"
            _update(run_id, "running", f"同步完成，新增 {new_count} 条", 0.0,
                    phase="sync", phase_progress=1.0)
        else:
            count = cache_service.get_prompt_count()
            if count == 0:
                with _step(run_id, "从 Athena 拉取数据", 0.0, phase="sync", phase_progress=0.1) as s:
                    row_count = athena_service.fetch_and_cache_prompts()
                    s["rows"] = row_count
                _update(run_id, "running", "同步完成", 0.0, phase="sync", phase_progress=1.0)
            else:
                with _step(run_id, "使用已缓存数据", 0.0, phase="sync", phase_progress=1.0) as s:
                    s["rows"] = count
                    s["detail"] = f"缓存中已有 {count} 条数据"

        # ── Phase 2: 数据分析 ──
        with _step(run_id, "加载数据", 0.05, phase_progress=0.02) as s:
            df = cache_service.get_prompts_df()
            df = df[df["prompt"].fillna("").str.strip() != ""].reset_index(drop=True)
            s["rows"] = len(df)
            s["detail"] = f"有效 Prompt {len(df)} 条"

        if df.empty:
            _update(run_id, "completed", "无数据", 1.0, phase="analysis", phase_progress=1.0)
            return

        with _step(run_id, "语言检测", 0.10, phase_progress=0.06) as s:
            lang_result = nlp_service.analyze_languages(df)
            cache_service.save_analysis_result(run_id, "language", lang_result)
            dist = lang_result.get("distribution", [])
            s["rows"] = sum(d.get("count", 0) for d in dist)
            s["detail"] = f"检测到 {len(dist)} 种语言"

        with _step(run_id, "文本统计", 0.18, phase_progress=0.12) as s:
            stats_result = nlp_service.analyze_text_statistics(df)
            cache_service.save_analysis_result(run_id, "text_stats", stats_result)
            s["rows"] = len(df)
            avg_len = stats_result.get("avg_length", 0)
            s["detail"] = f"平均长度 {avg_len:.0f} 字符"

        with _step(run_id, "关键词提取 (TF-IDF)", 0.26, phase_progress=0.20) as s:
            kw_result = nlp_service.extract_keywords(df)
            cache_service.save_analysis_result(run_id, "keywords", {"keywords": kw_result["keywords"]})
            s["rows"] = len(kw_result.get("keywords", []))
            s["detail"] = f"提取 {s['rows']} 个关键词"

        with _step(run_id, "主题建模 (LDA + t-SNE)", 0.36, phase_progress=0.30) as s:
            topic_result = nlp_service.build_topic_model(
                kw_result["sample_df"], kw_result["tfidf_matrix"], kw_result["feature_names"]
            )
            cache_service.save_analysis_result(run_id, "topics", topic_result)
            s["rows"] = topic_result.get("n_topics", 0)
            s["detail"] = f"发现 {s['rows']} 个主题"

        with _step(run_id, "趋势分析", 0.44, phase_progress=0.38) as s:
            trend_result = nlp_service.analyze_trends(df)
            cache_service.save_analysis_result(run_id, "trends", trend_result)
            s["rows"] = len(df)

        with _step(run_id, "意图分析", 0.50, phase_progress=0.44) as s:
            from app.services import intent_v2_service
            intent_v2_result = intent_v2_service.compute_intent_distribution(sample_limit=15000)
            cache_service.save_analysis_result(run_id, "intents_v2", intent_v2_result)
            s["rows"] = intent_v2_result.get("sample_size", 0)
            top = (intent_v2_result.get("distribution") or [{}])[0]
            s["detail"] = f"Top: {top.get('label','')} {top.get('percentage',0)}%"

        with _step(run_id, "意图分类 (Claude API)", 0.52, phase_progress=0.46) as s:
            try:
                intent_result = llm_service.classify_intents(df)
                cache_service.save_analysis_result(run_id, "intents", intent_result)
                s["rows"] = len(intent_result.get("distribution", []))
            except Exception as e:
                cache_service.save_analysis_result(run_id, "intents", {"distribution": [], "error": str(e)})
                s["detail"] = f"跳过: {e}"

        with _step(run_id, "质量评估 (Claude API)", 0.58, phase_progress=0.52) as s:
            try:
                quality_result = llm_service.assess_quality(df)
                cache_service.save_analysis_result(run_id, "quality", quality_result)
                s["rows"] = len(quality_result.get("scores", []))
            except Exception as e:
                cache_service.save_analysis_result(run_id, "quality", {"scores": [], "error": str(e)})
                s["detail"] = f"跳过: {e}"

        with _step(run_id, "主题总结 (Claude API)", 0.62, phase_progress=0.56) as s:
            try:
                summary = cache_service.get_summary()
                categories = cache_service.get_category_distributions()
                theme = llm_service.generate_theme_summary(summary, categories, kw_result["keywords"][:20])
                cache_service.save_analysis_result(run_id, "theme_summary", {"text": theme})
                s["detail"] = "生成成功"
            except Exception as e:
                s["detail"] = f"跳过: {e}"

        with _step(run_id, "质量评估 v2 (Claude API)", 0.65, phase_progress=0.60) as s:
            try:
                quality_v2 = llm_service.assess_quality_v2(df)
                cache_service.save_analysis_result(run_id, "quality_v2", quality_v2)
                s["rows"] = quality_v2.get("sample_size", 0)
            except Exception as e:
                s["detail"] = f"跳过: {e}"

        with _step(run_id, "用户分层", 0.70, phase_progress=0.65) as s:
            try:
                seg = user_service.compute_user_segments(days=90)
                s["rows"] = seg.get("total_users", 0)
                segs = seg.get("segments", {})
                s["detail"] = "  ".join(f"{k}:{v}" for k, v in segs.items())
            except Exception as e:
                s["detail"] = f"跳过: {e}"

        with _step(run_id, "向量索引 (FAISS)", 0.75, phase_progress=0.70) as s:
            try:
                n_indexed = embedding_service.build_index()
                s["rows"] = n_indexed
                s["detail"] = f"索引 {n_indexed} 条向量"
            except Exception as e:
                s["detail"] = f"跳过: {e}"

        with _step(run_id, "效果分析 (like_count)", 0.80, phase_progress=0.76) as s:
            try:
                eff = effect_service.compute_effect_analysis("like_count")
                s["rows"] = eff.get("total_prompts", 0)
                s["detail"] = f"爆款 {len(eff.get('hit_prompts', []))} 条，显著特征 {eff.get('significant_count', 0)} 个"
            except Exception as e:
                s["detail"] = f"跳过: {e}"

        with _step(run_id, "留存分析", 0.84, phase_progress=0.80) as s:
            try:
                ret = retention_service.compute_retention()
                s["rows"] = len(ret.get("cohorts", []))
                s["detail"] = f"{s['rows']} 个留存队列"
            except Exception as e:
                s["detail"] = f"跳过: {e}"

        with _step(run_id, "创作路径分析", 0.87, phase_progress=0.84) as s:
            try:
                paths = path_service.compute_user_paths()
                s["rows"] = len(paths.get("links", []))
                s["detail"] = f"{len(paths.get('nodes', []))} 节点 / {s['rows']} 路径"
            except Exception as e:
                s["detail"] = f"跳过: {e}"

        with _step(run_id, "BERTopic 主题模型", 0.90, phase_progress=0.87) as s:
            try:
                bt = bertopic_service.compute_bertopic()
                s["rows"] = bt.get("n_topics", 0)
                s["detail"] = f"{s['rows']} 个主题 (model={bt.get('model','-')})"
            except Exception as e:
                s["detail"] = f"跳过: {e}"

        with _step(run_id, "爆款模板挖掘", 0.93, phase_progress=0.91) as s:
            try:
                tmpl = template_service.mine_hot_templates()
                s["rows"] = len(tmpl.get("templates", []))
                s["detail"] = f"挖掘 {s['rows']} 个模板"
            except Exception as e:
                s["detail"] = f"跳过: {e}"

        with _step(run_id, "多指标效果分析", 0.96, phase_progress=0.95) as s:
            try:
                effect_service.compute_effect_analysis("collect_count")
                effect_service.compute_effect_analysis("score")
                s["detail"] = "collect_count / score 完成"
            except Exception as e:
                s["detail"] = f"跳过: {e}"

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
    logger.info("[Run %d] %s: %s (%.0f%%)", run_id, status, step, progress * 100)
