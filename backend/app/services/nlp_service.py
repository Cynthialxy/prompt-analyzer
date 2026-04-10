"""NLP analysis pipeline: language detection, TF-IDF, topic modeling."""

import logging
import re
from collections import Counter

import numpy as np
import pandas as pd
from langdetect import detect, DetectorFactory
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.manifold import TSNE

from app.utils.text_utils import clean_prompt, is_chinese, word_count, char_count

logger = logging.getLogger(__name__)

# Make langdetect deterministic
DetectorFactory.seed = 42


def detect_language(text: str) -> str:
    """Detect language of a single text."""
    try:
        if not text or len(text.strip()) < 3:
            return "unknown"
        return detect(text)
    except Exception:
        return "unknown"


def analyze_languages(df: pd.DataFrame) -> dict:
    """Detect languages for all prompts and compute distributions."""
    logger.info("Detecting languages for %d prompts...", len(df))
    languages = df["prompt"].apply(detect_language)
    df["detected_language"] = languages

    lang_counts = languages.value_counts().to_dict()
    total = len(df)

    distribution = [
        {"language": lang, "count": count, "percentage": round(count / total * 100, 2)}
        for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1])
    ]

    return {
        "distribution": distribution,
        "total": total,
    }


def analyze_text_statistics(df: pd.DataFrame) -> dict:
    """Compute text statistics for prompts."""
    logger.info("Computing text statistics for %d prompts...", len(df))
    df["char_count"] = df["prompt"].apply(char_count)
    df["word_count"] = df["prompt"].apply(word_count)

    # Lexical diversity (for English prompts)
    def lexical_diversity(text):
        if not text:
            return 0
        words = text.lower().split()
        if len(words) == 0:
            return 0
        return len(set(words)) / len(words)

    df["lexical_diversity"] = df["prompt"].apply(lexical_diversity)

    # Length histogram bins
    char_counts = df["char_count"]
    bins = [0, 10, 20, 50, 100, 200, 500, 1000, float('inf')]
    labels = ["0-10", "11-20", "21-50", "51-100", "101-200", "201-500", "501-1000", "1000+"]
    length_hist = pd.cut(char_counts, bins=bins, labels=labels).value_counts().sort_index()

    word_counts = df["word_count"]

    return {
        "char_count": {
            "mean": round(char_counts.mean(), 1),
            "median": round(char_counts.median(), 1),
            "p95": round(char_counts.quantile(0.95), 1),
            "min": int(char_counts.min()),
            "max": int(char_counts.max()),
        },
        "word_count": {
            "mean": round(word_counts.mean(), 1),
            "median": round(word_counts.median(), 1),
            "p95": round(word_counts.quantile(0.95), 1),
        },
        "length_histogram": [
            {"range": label, "count": int(count)}
            for label, count in zip(labels, length_hist.values)
        ],
        "lexical_diversity": {
            "mean": round(df["lexical_diversity"].mean(), 3),
            "median": round(df["lexical_diversity"].median(), 3),
        },
    }


def extract_keywords(df: pd.DataFrame, top_n: int = 100) -> dict:
    """Extract keywords using TF-IDF."""
    logger.info("Extracting keywords via TF-IDF from %d prompts...", len(df))

    # Separate Chinese and English for proper tokenization
    texts = []
    for prompt in df["prompt"]:
        cleaned = clean_prompt(prompt)
        if is_chinese(cleaned):
            import jieba
            texts.append(" ".join(jieba.lcut(cleaned)))
        else:
            texts.append(cleaned.lower())

    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words="english",
        min_df=2,
        max_df=0.95,
    )
    tfidf_matrix = vectorizer.fit_transform(texts)
    feature_names = vectorizer.get_feature_names_out()

    # Global keyword scores
    scores = tfidf_matrix.mean(axis=0).A1
    top_indices = scores.argsort()[-top_n:][::-1]
    keywords = [
        {"keyword": feature_names[i], "score": round(float(scores[i]), 4)}
        for i in top_indices
    ]

    return {
        "keywords": keywords,
        "tfidf_matrix": tfidf_matrix,
        "feature_names": feature_names,
        "vectorizer": vectorizer,
        "texts": texts,
    }


def build_topic_model(df: pd.DataFrame, tfidf_matrix, feature_names,
                      n_topics: int = 15) -> dict:
    """Build LDA topic model and generate 2D coordinates."""
    logger.info("Building LDA topic model with %d topics...", n_topics)

    lda = LatentDirichletAllocation(
        n_components=n_topics,
        random_state=42,
        max_iter=20,
        learning_method="online",
    )
    topic_dist = lda.fit_transform(tfidf_matrix)

    # Extract top words per topic
    clusters = []
    for idx, topic in enumerate(lda.components_):
        top_word_indices = topic.argsort()[-10:][::-1]
        top_words = [feature_names[i] for i in top_word_indices]
        cluster_size = int((topic_dist.argmax(axis=1) == idx).sum())
        clusters.append({
            "id": idx,
            "label": f"Topic {idx + 1}",
            "keywords": top_words,
            "size": cluster_size,
        })

    # Assign topics to prompts
    prompt_topics = topic_dist.argmax(axis=1)
    df["topic_id"] = prompt_topics

    # Get representative prompts per cluster (skip empty)
    for cluster in clusters:
        mask = prompt_topics == cluster["id"]
        subset = df[mask]
        non_empty = subset[subset["prompt"].fillna("").str.strip() != ""]
        cluster["representative_prompts"] = non_empty.head(5)["prompt"].tolist()

    # Generate 2D scatter coordinates via t-SNE
    logger.info("Running t-SNE for 2D projection...")
    n_samples = min(len(df), 5000)  # Limit for performance
    if len(df) > n_samples:
        sample_idx = np.random.RandomState(42).choice(len(df), n_samples, replace=False)
        matrix_sample = tfidf_matrix[sample_idx]
        topics_sample = prompt_topics[sample_idx]
        prompts_sample = df.iloc[sample_idx]["prompt"].values
    else:
        matrix_sample = tfidf_matrix
        topics_sample = prompt_topics
        prompts_sample = df["prompt"].values

    perplexity = min(30, n_samples - 1)
    tsne = TSNE(n_components=2, random_state=42, perplexity=perplexity)
    coords = tsne.fit_transform(matrix_sample.toarray())

    scatter_data = [
        {
            "x": round(float(coords[i, 0]), 2),
            "y": round(float(coords[i, 1]), 2),
            "topic_id": int(topics_sample[i]),
            "prompt_preview": str(prompts_sample[i])[:200],
        }
        for i in range(len(coords))
    ]

    return {
        "clusters": clusters,
        "scatter_data": scatter_data,
        "n_topics": n_topics,
    }


def analyze_trends(df: pd.DataFrame) -> dict:
    """Analyze trends over time."""
    logger.info("Analyzing trends...")

    if "pt" not in df.columns or df["pt"].isna().all():
        return {"daily_counts": [], "trending_keywords": [], "category_trends": []}

    # Daily counts
    daily = df.groupby("pt").size().reset_index(name="count")
    daily_counts = daily.to_dict("records")

    # Category trends
    cat_daily = df.groupby(["pt", "llm_category"]).size().reset_index(name="count")
    category_trends = cat_daily.to_dict("records")

    # Trending keywords: compare recent vs previous period
    dates_sorted = sorted(df["pt"].dropna().unique())
    if len(dates_sorted) >= 2:
        mid = len(dates_sorted) // 2
        recent_dates = set(dates_sorted[mid:])
        previous_dates = set(dates_sorted[:mid])

        recent_prompts = df[df["pt"].isin(recent_dates)]["prompt"]
        previous_prompts = df[df["pt"].isin(previous_dates)]["prompt"]

        def get_word_counts(prompts):
            counter = Counter()
            for p in prompts:
                if p:
                    words = clean_prompt(p).lower().split()
                    counter.update(w for w in words if len(w) > 2)
            return counter

        recent_counts = get_word_counts(recent_prompts)
        previous_counts = get_word_counts(previous_prompts)

        trending = []
        for word, count in recent_counts.most_common(100):
            prev = previous_counts.get(word, 0)
            if prev > 0:
                momentum = (count - prev) / prev
            else:
                momentum = 1.0 if count > 5 else 0
            trending.append({
                "keyword": word,
                "recent_count": count,
                "previous_count": prev,
                "momentum": round(momentum, 2),
                "direction": "up" if momentum > 0.1 else ("down" if momentum < -0.1 else "stable"),
            })
        trending.sort(key=lambda x: x["momentum"], reverse=True)
        trending_keywords = trending[:50]
    else:
        trending_keywords = []

    # Word cloud data (recent period)
    recent_kw = []
    if trending_keywords:
        recent_kw = [{"name": t["keyword"], "value": t["recent_count"]}
                     for t in trending_keywords[:80]]

    return {
        "daily_counts": daily_counts,
        "trending_keywords": trending_keywords,
        "category_trends": category_trends,
        "word_cloud": recent_kw,
    }
