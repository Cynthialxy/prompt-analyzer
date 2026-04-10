"""User demand intent classification (v2).

Classifies prompts by USER DEMAND INTENT (why they generate) rather than
by generated object (what they generate). Uses keyword-based rules for
reliability since API Router's Claude doesn't follow strict classification.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Optional

from app.services import athena_service

logger = logging.getLogger(__name__)


# ---- Intent taxonomy ----
INTENT_TAXONOMY = {
    "content_creation": {
        "label": "内容创作",
        "description": "影视动画、漫画插画、短视频、游戏内容等创意作品",
        "sub_intents": {
            "animation_film": "影视动画",
            "comic_manga": "漫画插画",
            "short_video": "短视频/Vlog",
            "cg_artwork": "CG 艺术创作",
        },
    },
    "game_development": {
        "label": "游戏开发",
        "description": "游戏角色、道具、场景、低模资产等游戏素材",
        "sub_intents": {
            "game_character": "游戏角色",
            "game_asset": "游戏道具/武器",
            "game_scene": "游戏场景",
            "low_poly": "低模/PBR 资产",
        },
    },
    "physical_production": {
        "label": "实体制作",
        "description": "3D 打印、手办模型、珠宝首饰、工业原型等可物理生产的内容",
        "sub_intents": {
            "3d_printing": "3D 打印",
            "figurine": "手办/雕像",
            "jewelry": "珠宝首饰",
            "prototype": "工业原型",
        },
    },
    "design_reference": {
        "label": "设计参考",
        "description": "产品设计、建筑可视化、概念设计、工业设计等参考用途",
        "sub_intents": {
            "product_design": "产品设计",
            "architecture_viz": "建筑可视化",
            "concept_design": "概念设计",
            "industrial_design": "工业设计",
        },
    },
    "education_research": {
        "label": "教育科研",
        "description": "教学模型、医学解剖、科普展示、历史文物等教育科研用途",
        "sub_intents": {
            "teaching_model": "教学模型",
            "anatomy": "医学解剖",
            "science_demo": "科普展示",
            "heritage": "历史文物",
        },
    },
    "general_other": {
        "label": "通用创作",
        "description": "通用建模需求，未明确指向特定场景",
        "sub_intents": {
            "general": "通用创作",
        },
    },
}


# ---- Rule definitions (keyword → intent) ----
# Order matters: more specific rules first
INTENT_RULES: list = [
    # ---- Physical production (strongest signal) ----
    ("physical_production", "3d_printing", [
        r"\b3d[\s\-]?print", r"printable", r"3d 打印", r"打印模型", r"stl", r"additive manufactur",
    ]),
    ("physical_production", "figurine", [
        r"\bfigurine\b", r"statue", r"\bmini(ature)?\b", r"手办", r"雕像", r"塑像", r"tabletop",
    ]),
    ("physical_production", "jewelry", [
        r"\bjewelry\b", r"\bring\b", r"\bnecklace\b", r"\bpendant\b", r"earring", r"珠宝", r"首饰", r"吊坠", r"戒指", r"项链",
    ]),
    ("physical_production", "prototype", [
        r"prototype", r"原型机", r"样机",
    ]),

    # ---- Game development ----
    ("game_development", "low_poly", [
        r"low[\s\-]?poly", r"\bpbr\b", r"game[\s\-]?ready", r"低模", r"低多边形", r"stylized pbr",
    ]),
    ("game_development", "game_character", [
        r"\brpg\b", r"\bmmorpg\b", r"\bnpc\b", r"\bhero\b", r"player character",
        r"游戏角色", r"游戏人物", r"游戏英雄",
    ]),
    ("game_development", "game_asset", [
        r"game asset", r"game prop", r"game weapon", r"game item", r"loot", r"inventory",
        r"游戏道具", r"游戏武器", r"游戏装备",
    ]),
    ("game_development", "game_scene", [
        r"game scene", r"game environment", r"game map", r"level design",
        r"游戏场景", r"关卡", r"游戏地图",
    ]),

    # ---- Content creation ----
    ("content_creation", "animation_film", [
        r"\banimation\b", r"\banimated\b", r"\bfilm\b", r"\bmovie\b", r"cinematic",
        r"animation rig", r"动画", r"影视", r"电影",
    ]),
    ("content_creation", "comic_manga", [
        r"\banime\b", r"\bmanga\b", r"\bcomic\b", r"chibi", r"\botaku\b",
        r"漫画", r"动漫", r"日漫",
    ]),
    ("content_creation", "short_video", [
        r"short video", r"vlog", r"\btiktok\b", r"youtube short",
        r"短视频", r"抖音", r"视频创作",
    ]),
    ("content_creation", "cg_artwork", [
        r"\bcg\b", r"concept art(work)?", r"digital art", r"artwork", r"octane", r"vray", r"unreal render",
        r"艺术作品", r"数字艺术",
    ]),

    # ---- Design reference ----
    ("design_reference", "architecture_viz", [
        r"architectur", r"building design", r"exterior design", r"interior design",
        r"建筑可视化", r"室内设计", r"建筑设计",
    ]),
    ("design_reference", "product_design", [
        r"product design", r"industrial prototype", r"design mockup",
        r"产品设计", r"工业设计", r"设计样机",
    ]),
    ("design_reference", "concept_design", [
        r"concept", r"visualization", r"design reference",
        r"概念设计", r"设计参考", r"概念图",
    ]),
    ("design_reference", "industrial_design", [
        r"industrial", r"工业", r"机械设计",
    ]),

    # ---- Education / research ----
    ("education_research", "anatomy", [
        r"\banatomy\b", r"\banatomical\b", r"medical", r"organ", r"skeleton",
        r"解剖", r"医学", r"器官", r"骨骼",
    ]),
    ("education_research", "teaching_model", [
        r"educational", r"teaching", r"classroom", r"school project",
        r"教学", r"课堂", r"学校",
    ]),
    ("education_research", "science_demo", [
        r"scientific", r"science", r"demo model", r"experiment",
        r"科普", r"科学", r"实验",
    ]),
    ("education_research", "heritage", [
        r"museum", r"artifact", r"heritage", r"historic",
        r"博物馆", r"文物", r"历史遗产",
    ]),
]


def classify_prompt(text: str) -> tuple:
    """Classify a single prompt. Returns (intent, sub_intent)."""
    if not text:
        return ("general_other", "general")

    text_lower = text.lower()
    for intent, sub_intent, patterns in INTENT_RULES:
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return (intent, sub_intent)

    return ("general_other", "general")


def compute_intent_distribution(sample_limit: int = 20000) -> dict:
    """Compute intent distribution by classifying prompts from Athena.

    Strategy:
    1. Sample non-empty prompts from Athena with their metadata
    2. Classify each prompt using keyword rules
    3. Build distribution, sub-intent breakdown, intent×category cross-tab
    4. Attach sample prompts per intent
    """
    logger.info("Computing intent v2 distribution (sample=%d)...", sample_limit)

    # Athena doesn't support true random sampling efficiently; use TABLESAMPLE
    sql = f"""
        SELECT prompt, llm_category,
               TRY_CAST(like_count AS BIGINT) AS like_count,
               TRY_CAST(collect_count AS BIGINT) AS collect_count
        FROM silver.clean_tripo_project TABLESAMPLE BERNOULLI(1)
        WHERE prompt IS NOT NULL AND prompt != ''
        LIMIT {sample_limit}
    """
    try:
        result = athena_service.run_query(sql)
    except Exception as e:
        logger.warning("TABLESAMPLE failed (%s), falling back to LIMIT", e)
        sql_fallback = f"""
            SELECT prompt, llm_category,
                   TRY_CAST(like_count AS BIGINT) AS like_count,
                   TRY_CAST(collect_count AS BIGINT) AS collect_count
            FROM silver.clean_tripo_project
            WHERE prompt IS NOT NULL AND prompt != ''
            LIMIT {sample_limit}
        """
        result = athena_service.run_query(sql_fallback)

    rows = result["rows"]
    total = len(rows)
    logger.info("Classifying %d prompts...", total)

    # Classify
    intent_counts: dict = defaultdict(int)
    sub_intent_counts: dict = defaultdict(lambda: defaultdict(int))
    intent_category_cross: dict = defaultdict(lambda: defaultdict(int))
    intent_engagement: dict = defaultdict(lambda: {"total_likes": 0, "count": 0})
    sample_prompts: dict = defaultdict(list)

    for row in rows:
        prompt = row.get("prompt", "")
        category = row.get("llm_category") or "unknown"
        likes = int(row.get("like_count") or 0)

        intent, sub_intent = classify_prompt(prompt)
        intent_counts[intent] += 1
        sub_intent_counts[intent][sub_intent] += 1

        if category and category != "unknown":
            intent_category_cross[intent][category] += 1

        intent_engagement[intent]["total_likes"] += likes
        intent_engagement[intent]["count"] += 1

        if len(sample_prompts[intent]) < 5:
            sample_prompts[intent].append(prompt[:200])

    # Build distribution (sorted by count desc)
    distribution = []
    for intent in sorted(intent_counts.keys(), key=lambda k: -intent_counts[k]):
        cnt = intent_counts[intent]
        meta = INTENT_TAXONOMY.get(intent, {})
        distribution.append({
            "intent": intent,
            "label": meta.get("label", intent),
            "description": meta.get("description", ""),
            "count": cnt,
            "percentage": round(cnt / total * 100, 2) if total else 0,
        })

    # Sub-intent breakdown
    sub_intent_list = []
    for intent, subs in sub_intent_counts.items():
        meta = INTENT_TAXONOMY.get(intent, {})
        sub_labels = meta.get("sub_intents", {})
        for sub_intent, cnt in subs.items():
            sub_intent_list.append({
                "intent": intent,
                "intent_label": meta.get("label", intent),
                "sub_intent": sub_intent,
                "sub_intent_label": sub_labels.get(sub_intent, sub_intent),
                "count": cnt,
            })
    sub_intent_list.sort(key=lambda x: -x["count"])

    # Intent × category cross (for heatmap)
    cross_matrix = []
    top_intents = [d["intent"] for d in distribution]
    # Get top categories across all intents
    all_cats: dict = defaultdict(int)
    for intent_cats in intent_category_cross.values():
        for c, v in intent_cats.items():
            all_cats[c] += v
    top_cats = sorted(all_cats.keys(), key=lambda k: -all_cats[k])[:10]

    for i, intent in enumerate(top_intents):
        for j, cat in enumerate(top_cats):
            value = intent_category_cross[intent].get(cat, 0)
            cross_matrix.append([j, i, value])

    # Intent engagement
    intent_effect = []
    for intent in top_intents:
        eng = intent_engagement[intent]
        meta = INTENT_TAXONOMY.get(intent, {})
        avg_likes = eng["total_likes"] / eng["count"] if eng["count"] else 0
        intent_effect.append({
            "intent": intent,
            "label": meta.get("label", intent),
            "avg_likes": round(avg_likes, 4),
            "total_likes": eng["total_likes"],
            "count": eng["count"],
        })
    intent_effect.sort(key=lambda x: -x["avg_likes"])

    # Insights
    insights = _generate_insights(distribution, intent_effect, sub_intent_list)

    return {
        "distribution": distribution,
        "sub_intent_distribution": sub_intent_list[:30],
        "intent_category_cross": {
            "intents": [d["label"] for d in distribution],
            "categories": top_cats,
            "matrix": cross_matrix,
        },
        "intent_engagement": intent_effect,
        "sample_prompts": {k: v for k, v in sample_prompts.items()},
        "taxonomy": {
            k: {"label": v["label"], "description": v["description"]}
            for k, v in INTENT_TAXONOMY.items()
        },
        "insights": insights,
        "sample_size": total,
        "total_prompts": total,
        "source": "keyword_rules_v2",
    }


def _generate_insights(distribution: list, intent_effect: list, sub_list: list) -> list:
    """Auto-generate business insights from the data."""
    insights = []
    if not distribution:
        return insights

    # Core insight: top intent
    top = distribution[0]
    if top["intent"] != "general_other":
        insights.append(
            f"📌 核心需求：「{top['label']}」是用户最主要的创作意图，"
            f"占比 {top['percentage']}%（{top['count']} 条）。"
            f"建议优先优化该方向的生成效果与引导。"
        )
    else:
        non_other = [d for d in distribution if d["intent"] != "general_other"]
        if non_other:
            t = non_other[0]
            insights.append(
                f"📌 明确需求中，「{t['label']}」占比最高（{t['percentage']}%），值得重点关注。"
            )

    # Best engagement
    effective = [e for e in intent_effect if e["intent"] != "general_other" and e["count"] > 50]
    if effective:
        best = effective[0]
        insights.append(
            f"🏆 高效果意图：「{best['label']}」平均点赞 {best['avg_likes']}，"
            f"是各类意图中效果最好的，适合作为爆款模板参考。"
        )

    # Other ratio warning
    other_pct = next((d["percentage"] for d in distribution if d["intent"] == "general_other"), 0)
    if other_pct > 30:
        insights.append(
            f"⚠️ 「通用创作」占比 {other_pct}%，说明大量用户 Prompt 未明确具体场景，"
            f"建议在产品中增加场景选择引导（如：影视/游戏/打印/设计）。"
        )
    elif other_pct < 10:
        insights.append(
            f"✅ 意图识别率 {100 - other_pct:.0f}%，用户需求表达清晰，产品分类引导有效。"
        )

    # Top sub-intent recommendation
    if sub_list:
        top_sub = next((s for s in sub_list if s["intent"] != "general_other"), None)
        if top_sub:
            insights.append(
                f"💡 细分方向：「{top_sub['sub_intent_label']}」（{top_sub['intent_label']}）"
                f"是最具体的需求方向（{top_sub['count']} 条），可针对性开发功能或模板库。"
            )

    return insights
