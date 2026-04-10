"""Prompt embedding + FAISS similarity search."""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

import numpy as np

from app.config import settings
from app.services import cache_service

logger = logging.getLogger(__name__)

# Module-level state (lazy-loaded)
_model = None
_index = None
_id_map: list = []
_prompt_map: dict = {}  # project_id -> {prompt, llm_category, llm_style, like_count, display_image, ...}


def get_model():
    """Lazy-load the sentence transformer model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model: %s", settings.embedding_model_name)
        _model = SentenceTransformer(settings.embedding_model_name)
    return _model


def build_index(prompts: Optional[list[dict]] = None, max_prompts: int = 50000) -> int:
    """Build FAISS index from given prompt dicts (or all cached prompts).

    Args:
        prompts: list of {project_id, prompt, ...}. If None, loads from cache.
        max_prompts: max number of prompts to embed (for cost/time bound).

    Returns:
        Number of prompts indexed.
    """
    import faiss

    if prompts is None:
        df = cache_service.get_prompts_df()
        if df.empty:
            logger.warning("No prompts in cache for embedding")
            return 0
        df = df.head(max_prompts)
        prompts = df.to_dict("records")
    else:
        prompts = prompts[:max_prompts]

    # Filter valid prompts
    valid = [p for p in prompts if p.get("prompt") and str(p["prompt"]).strip()]
    if not valid:
        logger.warning("No valid prompts to index")
        return 0

    logger.info("Building embeddings for %d prompts...", len(valid))
    model = get_model()
    texts = [str(p["prompt"]) for p in valid]
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=64,
        convert_to_numpy=True,
    ).astype(np.float32)

    # Build index
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    # Persist
    os.makedirs(os.path.dirname(settings.faiss_index_path) or ".", exist_ok=True)
    faiss.write_index(index, settings.faiss_index_path)

    id_map = [p.get("project_id") for p in valid]
    # Store metadata map for quick lookups during search
    prompt_meta = {
        p.get("project_id"): {
            "project_id": p.get("project_id"),
            "prompt": p.get("prompt"),
            "llm_category": p.get("llm_category"),
            "llm_style": p.get("llm_style"),
            "like_count": p.get("like_count", 0),
            "collect_count": p.get("collect_count", 0),
            "score": p.get("score"),
            "display_image": p.get("display_image"),
            "user_id": p.get("user_id"),
        }
        for p in valid
    }
    with open(settings.faiss_id_map_path, "w", encoding="utf-8") as f:
        json.dump({"id_map": id_map, "meta": prompt_meta}, f, ensure_ascii=False)

    # Update global state
    global _index, _id_map, _prompt_map
    _index = index
    _id_map = id_map
    _prompt_map = prompt_meta

    logger.info("FAISS index built: %d vectors, dim=%d, saved to %s",
                len(id_map), dim, settings.faiss_index_path)
    return len(id_map)


def load_index() -> bool:
    """Load persisted FAISS index + id_map from disk."""
    import faiss

    global _index, _id_map, _prompt_map

    if not os.path.exists(settings.faiss_index_path):
        logger.info("No persisted FAISS index found at %s", settings.faiss_index_path)
        return False

    try:
        _index = faiss.read_index(settings.faiss_index_path)
        with open(settings.faiss_id_map_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            _id_map = data.get("id_map", [])
            _prompt_map = data.get("meta", {})
        logger.info("Loaded FAISS index: %d vectors", len(_id_map))
        return True
    except Exception as e:
        logger.error("Failed to load FAISS index: %s", e)
        return False


def _ensure_loaded():
    if _index is None:
        if not load_index():
            raise RuntimeError("FAISS index not built. Run the pipeline first.")


def search_similar(query_text: str, top_k: int = 10) -> list[dict]:
    """Search for prompts similar to a free-text query."""
    _ensure_loaded()
    model = get_model()
    query_vec = model.encode(
        [query_text],
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).astype(np.float32)

    scores, indices = _index.search(query_vec, min(top_k, len(_id_map)))

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(_id_map):
            continue
        pid = _id_map[idx]
        meta = _prompt_map.get(pid, {})
        results.append({
            **meta,
            "project_id": pid,
            "similarity_score": round(float(score), 4),
        })
    return results


def search_similar_by_id(project_id: str, top_k: int = 10) -> list[dict]:
    """Search for prompts similar to an existing prompt (by project_id)."""
    _ensure_loaded()

    if project_id not in _id_map:
        # Try to embed on the fly from cache
        with cache_service.get_conn() as conn:
            row = conn.execute(
                "SELECT prompt FROM prompts WHERE project_id = ?", (project_id,)
            ).fetchone()
        if not row or not row["prompt"]:
            raise ValueError(f"Prompt not found: {project_id}")
        return search_similar(row["prompt"], top_k=top_k)

    idx = _id_map.index(project_id)
    vec = _index.reconstruct(idx).reshape(1, -1).astype(np.float32)
    # +1 to drop self
    k = min(top_k + 1, len(_id_map))
    scores, indices = _index.search(vec, k)

    results = []
    for score, i in zip(scores[0], indices[0]):
        if i < 0 or i >= len(_id_map):
            continue
        pid = _id_map[i]
        if pid == project_id:
            continue
        meta = _prompt_map.get(pid, {})
        results.append({
            **meta,
            "project_id": pid,
            "similarity_score": round(float(score), 4),
        })
        if len(results) >= top_k:
            break
    return results


def get_index_info() -> dict:
    """Return info about the current FAISS index."""
    if _index is None:
        loaded = load_index()
        if not loaded:
            return {"loaded": False, "size": 0, "model": settings.embedding_model_name}
    return {
        "loaded": True,
        "size": len(_id_map),
        "model": settings.embedding_model_name,
        "dim": settings.embedding_dim,
    }
