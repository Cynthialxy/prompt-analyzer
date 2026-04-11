"""SQLite cache for Athena query results and analysis outputs."""
from __future__ import annotations

import json
import sqlite3
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager

from app.config import settings

logger = logging.getLogger(__name__)

DB_PATH = settings.cache_db_path


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS prompts (
                project_id TEXT PRIMARY KEY,
                user_id TEXT,
                prompt TEXT,
                caption TEXT,
                name TEXT,
                llm_keyword TEXT,
                llm_object TEXT,
                llm_category TEXT,
                llm_style TEXT,
                llm_color TEXT,
                llm_use_case TEXT,
                llm_height TEXT,
                from_type TEXT,
                status TEXT,
                visibility TEXT,
                display_image TEXT,
                like_count INTEGER DEFAULT 0,
                collect_count INTEGER DEFAULT 0,
                score REAL,
                created_at TEXT,
                pt TEXT,
                fetched_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS analysis_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT,
                completed_at TEXT,
                status TEXT DEFAULT 'pending',
                current_step TEXT,
                progress REAL DEFAULT 0,
                config_json TEXT,
                error TEXT
            );

            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                result_type TEXT,
                result_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES analysis_runs(id)
            );

            CREATE TABLE IF NOT EXISTS sync_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_segments (
                user_id TEXT PRIMARY KEY,
                segment TEXT NOT NULL,
                total_prompts INTEGER DEFAULT 0,
                first_seen TEXT,
                last_seen TEXT,
                active_days INTEGER DEFAULT 0,
                avg_prompts_per_day REAL DEFAULT 0,
                top_category TEXT,
                top_style TEXT,
                avg_like_count REAL DEFAULT 0,
                avg_score REAL DEFAULT 0,
                total_like_count INTEGER DEFAULT 0,
                computed_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS prompt_quality_v2 (
                project_id TEXT PRIMARY KEY,
                intent TEXT,
                sub_intent TEXT,
                intent_confidence REAL,
                quality_score REAL,
                specificity INTEGER,
                clarity INTEGER,
                creativity INTEGER,
                technical_detail INTEGER,
                actionability INTEGER,
                optimization_suggestions TEXT,
                computed_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_prompts_category ON prompts(llm_category);
            CREATE INDEX IF NOT EXISTS idx_prompts_style ON prompts(llm_style);
            CREATE INDEX IF NOT EXISTS idx_prompts_pt ON prompts(pt);
            CREATE INDEX IF NOT EXISTS idx_results_type ON analysis_results(result_type);
            CREATE INDEX IF NOT EXISTS idx_user_segments_segment ON user_segments(segment);
        """)

    # Idempotent ALTER TABLE for existing DBs (add columns if missing)
    _ensure_prompt_columns()

    # Create indexes on new columns (after _ensure_prompt_columns adds them)
    with get_conn() as conn:
        for stmt in [
            "CREATE INDEX IF NOT EXISTS idx_prompts_user_id ON prompts(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_prompts_like_count ON prompts(like_count)",
            "CREATE INDEX IF NOT EXISTS idx_prompts_score ON prompts(score)",
        ]:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass


def _ensure_prompt_columns():
    """Add new columns to existing prompts table if they don't exist."""
    new_columns = [
        ("name", "TEXT"),
        ("status", "TEXT"),
        ("visibility", "TEXT"),
        ("display_image", "TEXT"),
        ("like_count", "INTEGER DEFAULT 0"),
        ("collect_count", "INTEGER DEFAULT 0"),
        ("score", "REAL"),
    ]
    with get_conn() as conn:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(prompts)").fetchall()}
        for col_name, col_type in new_columns:
            if col_name not in existing:
                try:
                    conn.execute(f"ALTER TABLE prompts ADD COLUMN {col_name} {col_type}")
                    logger.info("Added column prompts.%s", col_name)
                except sqlite3.OperationalError as e:
                    logger.warning("Could not add column %s: %s", col_name, e)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_prompts(rows: list[dict]):
    """Bulk insert prompts into cache."""
    # Normalize: ensure all expected keys exist
    normalized = []
    for r in rows:
        normalized.append({
            "project_id": r.get("project_id"),
            "user_id": r.get("user_id"),
            "prompt": r.get("prompt"),
            "caption": r.get("caption"),
            "name": r.get("name"),
            "llm_keyword": r.get("llm_keyword"),
            "llm_object": r.get("llm_object"),
            "llm_category": r.get("llm_category"),
            "llm_style": r.get("llm_style"),
            "llm_color": r.get("llm_color"),
            "llm_use_case": r.get("llm_use_case"),
            "llm_height": r.get("llm_height"),
            "from_type": r.get("from_type"),
            "status": r.get("status"),
            "visibility": r.get("visibility"),
            "display_image": r.get("display_image"),
            "like_count": _to_int(r.get("like_count")),
            "collect_count": _to_int(r.get("collect_count")),
            "score": _to_float(r.get("score")),
            "created_at": r.get("created_at"),
            "pt": r.get("pt"),
        })
    with get_conn() as conn:
        conn.executemany("""
            INSERT OR REPLACE INTO prompts
            (project_id, user_id, prompt, caption, name, llm_keyword, llm_object,
             llm_category, llm_style, llm_color, llm_use_case, llm_height,
             from_type, status, visibility, display_image,
             like_count, collect_count, score, created_at, pt)
            VALUES (:project_id, :user_id, :prompt, :caption, :name, :llm_keyword,
                    :llm_object, :llm_category, :llm_style, :llm_color,
                    :llm_use_case, :llm_height, :from_type, :status, :visibility,
                    :display_image, :like_count, :collect_count, :score, :created_at, :pt)
        """, normalized)
        # Update sync state
        conn.execute(
            "INSERT OR REPLACE INTO sync_state (key, value, updated_at) VALUES ('last_sync', ?, ?)",
            (datetime.now().isoformat(), datetime.now().isoformat())
        )
    logger.info("Cached %d prompts", len(normalized))


def _to_int(v) -> int:
    try:
        return int(v) if v not in (None, "") else 0
    except (ValueError, TypeError):
        return 0


def _to_float(v) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def get_prompt_count() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM prompts").fetchone()
        return row["cnt"]


def get_prompts_df():
    """Load all cached prompts as a pandas DataFrame (non-empty prompts only)."""
    import pandas as pd
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM prompts WHERE prompt IS NOT NULL AND prompt != ''",
            conn,
        )
    return df


def get_prompts_paginated(page: int = 1, page_size: int = 50,
                          search: str = None, category: str = None,
                          style: str = None, language: str = None) -> dict:
    """Get paginated prompts with optional filters."""
    conditions = []
    params = []

    if search:
        conditions.append("prompt LIKE ?")
        params.append(f"%{search}%")
    if category:
        conditions.append("llm_category = ?")
        params.append(category)
    if style:
        conditions.append("llm_style = ?")
        params.append(style)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    offset = (page - 1) * page_size

    with get_conn() as conn:
        total = conn.execute(f"SELECT COUNT(*) as cnt FROM prompts {where}", params).fetchone()["cnt"]
        rows = conn.execute(
            f"SELECT * FROM prompts {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [page_size, offset]
        ).fetchall()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": [dict(r) for r in rows]
    }


def _date_where(date_from: str = None, date_to: str = None, prefix: str = "AND") -> tuple:
    """Build date filter SQL clause and params."""
    clauses = []
    params = []
    if date_from:
        clauses.append(f"{prefix} pt >= ?")
        params.append(date_from.replace("-", ""))
    if date_to:
        clauses.append(f"{prefix} pt <= ?")
        params.append(date_to.replace("-", ""))
    return " ".join(clauses), params


def get_summary(date_from: str = None, date_to: str = None) -> dict:
    """Get overall data summary, optionally filtered by date range."""
    date_sql, date_params = _date_where(date_from, date_to, "AND")
    where = f"WHERE 1=1 {date_sql}" if date_sql else ""
    cat_where = f"WHERE llm_category IS NOT NULL AND llm_category != '' {date_sql}"

    with get_conn() as conn:
        stats = conn.execute(f"""
            SELECT
                COUNT(*) as total_prompts,
                COUNT(DISTINCT user_id) as unique_users,
                MIN(pt) as min_date,
                MAX(pt) as max_date,
                AVG(LENGTH(prompt)) as avg_prompt_length
            FROM prompts {where}
        """, date_params).fetchone()

        top_categories = conn.execute(f"""
            SELECT llm_category, COUNT(*) as cnt
            FROM prompts
            {cat_where}
            GROUP BY llm_category
            ORDER BY cnt DESC
            LIMIT 10
        """, date_params).fetchall()

    return {
        "total_prompts": stats["total_prompts"],
        "unique_users": stats["unique_users"],
        "date_range": {"min": stats["min_date"], "max": stats["max_date"]},
        "avg_prompt_length": round(stats["avg_prompt_length"] or 0, 1),
        "top_categories": [{"name": r["llm_category"], "count": r["cnt"]} for r in top_categories]
    }


def get_category_distributions() -> dict:
    """Get distributions of all LLM tag fields."""
    with get_conn() as conn:
        result = {}
        for field in ["llm_category", "llm_style", "llm_use_case"]:
            rows = conn.execute(f"""
                SELECT {field} as name, COUNT(*) as count
                FROM prompts
                WHERE {field} IS NOT NULL AND {field} != ''
                GROUP BY {field}
                ORDER BY count DESC
            """).fetchall()
            result[field] = [dict(r) for r in rows]

        # Color needs special handling - split comma-separated values
        color_rows = conn.execute("""
            SELECT llm_color FROM prompts
            WHERE llm_color IS NOT NULL AND llm_color != ''
        """).fetchall()

        color_counts = {}
        for r in color_rows:
            for color in r["llm_color"].split(","):
                color = color.strip().lower()
                if color:
                    color_counts[color] = color_counts.get(color, 0) + 1

        result["llm_color"] = sorted(
            [{"name": k, "count": v} for k, v in color_counts.items()],
            key=lambda x: x["count"], reverse=True
        )

        # Cross-tab: category x style
        cross_rows = conn.execute("""
            SELECT llm_category, llm_style, COUNT(*) as count
            FROM prompts
            WHERE llm_category IS NOT NULL AND llm_category != ''
              AND llm_style IS NOT NULL AND llm_style != ''
            GROUP BY llm_category, llm_style
            ORDER BY count DESC
        """).fetchall()
        result["category_style_cross"] = [dict(r) for r in cross_rows]

    return result


def compute_quality_from_prompts() -> dict:
    """Compute proxy quality metrics from local prompt data without LLM.

    Dimensions (all scaled 1-5):
    - specificity:    prompt length proxy (longer = more specific)
    - clarity:        has llm_category (structured = clearer)
    - creativity:     has llm_style and style is non-generic
    - technical_detail: has color / keyword / object tags
    """
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                LENGTH(prompt) as plen,
                llm_category,
                llm_style,
                llm_color,
                llm_keyword,
                llm_object
            FROM prompts
            WHERE prompt IS NOT NULL AND prompt != ''
        """).fetchall()

    if not rows:
        return {"scores": [], "summary": {}, "sample_size": 0}

    GENERIC_STYLES = {'realistic', 'stylized', ''}

    specificity_vals, clarity_vals, creativity_vals, tech_vals = [], [], [], []

    for r in rows:
        plen = r['plen'] or 0
        # specificity: 0-50→1, 51-100→2, 101-200→3, 201-400→4, 400+→5
        if plen <= 50:    spec = 1
        elif plen <= 100: spec = 2
        elif plen <= 200: spec = 3
        elif plen <= 400: spec = 4
        else:             spec = 5
        specificity_vals.append(spec)

        # clarity: has category → 4-5, else 2-3
        has_cat = bool(r['llm_category'] and r['llm_category'].strip())
        clarity_vals.append(4 if has_cat else 2)

        # creativity: non-generic style → higher
        style = (r['llm_style'] or '').strip().lower()
        if style and style not in GENERIC_STYLES:
            creativity_vals.append(4)
        elif style in GENERIC_STYLES and style:
            creativity_vals.append(3)
        else:
            creativity_vals.append(2)

        # technical_detail: count how many tag fields are filled
        filled = sum([
            bool(r['llm_color'] and r['llm_color'].strip()),
            bool(r['llm_keyword'] and r['llm_keyword'].strip()),
            bool(r['llm_object'] and r['llm_object'].strip()),
            bool(r['llm_style'] and r['llm_style'].strip()),
        ])
        tech_vals.append(max(1, min(5, filled + 1)))

    def _dim_summary(vals):
        mean = round(sum(vals) / len(vals), 2)
        return {
            "mean": mean,
            "distribution": {str(i): vals.count(i) for i in range(1, 6)},
        }

    summary = {
        "specificity":     _dim_summary(specificity_vals),
        "clarity":         _dim_summary(clarity_vals),
        "creativity":      _dim_summary(creativity_vals),
        "technical_detail": _dim_summary(tech_vals),
    }
    all_means = [summary[d]["mean"] for d in summary]
    summary["overall"] = {"mean": round(sum(all_means) / len(all_means), 2)}

    return {"scores": [], "summary": summary, "sample_size": len(rows)}


    """Get daily prompt counts, optionally filtered by date range."""
    date_sql, date_params = _date_where(date_from, date_to, "AND")
    with get_conn() as conn:
        rows = conn.execute(f"""
            SELECT pt as date, COUNT(*) as count
            FROM prompts
            WHERE pt IS NOT NULL {date_sql}
            GROUP BY pt
            ORDER BY pt
        """, date_params).fetchall()
    return [dict(r) for r in rows]


def save_analysis_run(config: dict = None) -> int:
    """Create a new analysis run record."""
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO analysis_runs (started_at, status, config_json) VALUES (?, 'running', ?)",
            (datetime.now().isoformat(), json.dumps(config or {}))
        )
        return cursor.lastrowid


def update_analysis_run(run_id: int, status: str = None, step: str = None,
                        progress: float = None, error: str = None):
    with get_conn() as conn:
        updates = []
        params = []
        if status:
            updates.append("status = ?")
            params.append(status)
        if step:
            updates.append("current_step = ?")
            params.append(step)
        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)
        if error:
            updates.append("error = ?")
            params.append(error)
        if status == "completed":
            updates.append("completed_at = ?")
            params.append(datetime.now().isoformat())

        params.append(run_id)
        conn.execute(f"UPDATE analysis_runs SET {', '.join(updates)} WHERE id = ?", params)


def get_analysis_run(run_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM analysis_runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None


def get_latest_analysis_run() -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM analysis_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def save_analysis_result(run_id: int, result_type: str, data: dict):
    with get_conn() as conn:
        # Remove old results of same type
        conn.execute("DELETE FROM analysis_results WHERE result_type = ?", (result_type,))
        conn.execute(
            "INSERT INTO analysis_results (run_id, result_type, result_json) VALUES (?, ?, ?)",
            (run_id, result_type, json.dumps(data, ensure_ascii=False))
        )


def get_analysis_result(result_type: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT result_json FROM analysis_results WHERE result_type = ? ORDER BY id DESC LIMIT 1",
            (result_type,)
        ).fetchone()
        return json.loads(row["result_json"]) if row else None
