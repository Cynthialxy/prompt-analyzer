"""User creation path analysis: sequence mining + Sankey diagram."""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime

import pandas as pd

from app.services import cache_service

logger = logging.getLogger(__name__)


def compute_user_paths(max_users: int = 500, min_seq_len: int = 2) -> dict:
    """Analyze user creation paths: category/style progression + Sankey flow.

    Mining logic:
    - Group prompts by user_id, ordered by created_at
    - For each user, build a sequence of (category, style) pairs
    - Aggregate transitions for Sankey diagram
    - Detect iteration patterns: prompt_length growth, specificity improvement

    Returns:
        {
          "sankey": {"nodes": [...], "links": [...]},
          "iteration_patterns": {
            "avg_length_growth": 0.42,
            "avg_prompts_per_user": 5.8,
            "users_analyzed": 500
          },
          "top_transitions": [{"from": "Character", "to": "Creatures & Animals", "count": 45}],
          "category_entry_exit": {...}
        }
    """
    logger.info("Computing user creation paths (max %d users)...", max_users)

    df = cache_service.get_prompts_df()
    if df.empty:
        return {"error": "No data"}

    # Keep users with at least min_seq_len prompts
    user_counts = df.groupby("user_id").size()
    qualified_users = user_counts[user_counts >= min_seq_len].head(max_users).index.tolist()
    df = df[df["user_id"].isin(qualified_users)].copy()

    if df.empty:
        return {"error": "No users with enough sequence data"}

    # Sort by user_id + created_at (fall back to project_id)
    df["_sort_key"] = df["created_at"].fillna("")
    df = df.sort_values(["user_id", "_sort_key"])

    # Build transitions: category -> category, style -> style
    cat_transitions: Counter = Counter()
    style_transitions: Counter = Counter()
    cat_style_links: Counter = Counter()  # (category, style) pairs
    length_growths = []
    per_user_prompt_counts = []

    for user_id, user_df in df.groupby("user_id"):
        cats = user_df["llm_category"].fillna("unknown").tolist()
        styles = user_df["llm_style"].fillna("unknown").tolist()
        lengths = user_df["prompt"].fillna("").str.len().tolist()

        per_user_prompt_counts.append(len(cats))

        # Category transitions
        for i in range(len(cats) - 1):
            src = cats[i] or "unknown"
            dst = cats[i + 1] or "unknown"
            if src and dst:
                cat_transitions[(src, dst)] += 1

        # Style transitions
        for i in range(len(styles) - 1):
            src = styles[i] or "unknown"
            dst = styles[i + 1] or "unknown"
            if src and dst:
                style_transitions[(src, dst)] += 1

        # Category -> Style links (for mixed Sankey)
        for c, s in zip(cats, styles):
            if c and s and c != "unknown" and s != "unknown":
                cat_style_links[(c, s)] += 1

        # Length growth
        if len(lengths) >= 2 and lengths[0] > 0:
            growth = (lengths[-1] - lengths[0]) / lengths[0]
            length_growths.append(growth)

    # Build Sankey: Initial Category -> Style -> (flattened)
    top_cats = [c for c, _ in Counter(
        {k[0]: v for k, v in cat_style_links.items()}
    ).most_common(10)]
    top_styles = [s for s, _ in Counter(
        {k[1]: v for k, v in cat_style_links.items()}
    ).most_common(10)]

    nodes = []
    node_ids = {}

    def _add_node(name: str, prefix: str):
        key = f"{prefix}:{name}"
        if key not in node_ids:
            node_ids[key] = len(nodes)
            nodes.append({"name": f"{prefix}-{name}"})
        return key

    links = []
    # Category -> Style
    for (cat, style), count in cat_style_links.most_common(50):
        if cat not in top_cats or style not in top_styles:
            continue
        src_key = _add_node(cat, "类别")
        dst_key = _add_node(style, "风格")
        links.append({
            "source": nodes[node_ids[src_key]]["name"],
            "target": nodes[node_ids[dst_key]]["name"],
            "value": count,
        })

    # Top category transitions (for separate display)
    top_transitions = [
        {"from": src, "to": dst, "count": cnt}
        for (src, dst), cnt in cat_transitions.most_common(20)
        if src != "unknown" and dst != "unknown"
    ]

    # Category entry/exit analysis
    cat_entry_exit: dict = defaultdict(lambda: {"in": 0, "out": 0, "stay": 0})
    for (src, dst), cnt in cat_transitions.items():
        if src == dst:
            cat_entry_exit[src]["stay"] += cnt
        else:
            cat_entry_exit[dst]["in"] += cnt
            cat_entry_exit[src]["out"] += cnt

    cat_entry_exit_list = [
        {"category": cat, **stats}
        for cat, stats in sorted(cat_entry_exit.items(), key=lambda x: -sum(x[1].values()))
        if cat != "unknown"
    ][:15]

    avg_length_growth = sum(length_growths) / len(length_growths) if length_growths else 0
    avg_prompts = sum(per_user_prompt_counts) / len(per_user_prompt_counts) if per_user_prompt_counts else 0

    result = {
        "sankey": {
            "nodes": nodes,
            "links": links,
        },
        "iteration_patterns": {
            "avg_length_growth": round(avg_length_growth, 3),
            "avg_prompts_per_user": round(avg_prompts, 1),
            "users_analyzed": len(qualified_users),
            "users_with_growth": sum(1 for g in length_growths if g > 0),
            "users_with_shrinkage": sum(1 for g in length_growths if g < 0),
        },
        "top_transitions": top_transitions,
        "category_entry_exit": cat_entry_exit_list,
        "computed_at": datetime.now().isoformat(),
    }

    cache_service.save_analysis_result(0, "user_paths", result)
    logger.info("User paths: %d users, %d sankey links, avg growth=%.2f",
                len(qualified_users), len(links), avg_length_growth)
    return result
