"""PostgreSQL / pgvector service for production-grade vector storage."""
from __future__ import annotations

import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

_pool = None


def is_available() -> bool:
    return bool(settings.pg_enabled and settings.pg_connection_string)


def get_conn():
    """Get a connection from the pool."""
    global _pool
    if _pool is None:
        try:
            import psycopg2
            from psycopg2 import pool as pg_pool
            _pool = pg_pool.ThreadedConnectionPool(
                1, 10, settings.pg_connection_string
            )
        except Exception as e:
            logger.error("PG pool init failed: %s", e)
            raise
    return _pool.getconn()


def return_conn(conn):
    if _pool:
        _pool.putconn(conn)


def init_pgvector():
    """Initialize pgvector extension and tables."""
    if not is_available():
        logger.info("pgvector disabled (pg_enabled=False or no connection string)")
        return

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {settings.pgvector_table} (
                id SERIAL PRIMARY KEY,
                project_id TEXT UNIQUE NOT NULL,
                user_id TEXT,
                prompt TEXT,
                llm_category TEXT,
                llm_style TEXT,
                like_count INTEGER DEFAULT 0,
                collect_count INTEGER DEFAULT 0,
                score REAL,
                display_image TEXT,
                embedding vector({settings.embedding_dim}),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{settings.pgvector_table}_embedding
            ON {settings.pgvector_table}
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{settings.pgvector_table}_project
            ON {settings.pgvector_table} (project_id)
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{settings.pgvector_table}_category
            ON {settings.pgvector_table} (llm_category)
        """)
        conn.commit()
        logger.info("pgvector table '%s' initialized", settings.pgvector_table)
    except Exception as e:
        conn.rollback()
        logger.error("pgvector init failed: %s", e)
        raise
    finally:
        return_conn(conn)


def upsert_embeddings(records: list[dict]):
    """Batch upsert prompt embeddings into pgvector.

    records: [{project_id, user_id, prompt, embedding(list[float]), ...}]
    """
    if not is_available():
        return 0

    conn = get_conn()
    try:
        cur = conn.cursor()
        for r in records:
            emb = r.get("embedding")
            if emb is None:
                continue
            emb_str = "[" + ",".join(str(v) for v in emb) + "]"
            cur.execute(f"""
                INSERT INTO {settings.pgvector_table}
                    (project_id, user_id, prompt, llm_category, llm_style,
                     like_count, collect_count, score, display_image, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (project_id)
                DO UPDATE SET embedding = EXCLUDED.embedding
            """, (
                r.get("project_id"), r.get("user_id"), r.get("prompt"),
                r.get("llm_category"), r.get("llm_style"),
                r.get("like_count", 0), r.get("collect_count", 0),
                r.get("score"), r.get("display_image"), emb_str,
            ))
        conn.commit()
        logger.info("Upserted %d embeddings to pgvector", len(records))
        return len(records)
    except Exception as e:
        conn.rollback()
        logger.error("pgvector upsert failed: %s", e)
        raise
    finally:
        return_conn(conn)


def search_similar_pg(query_embedding: list[float], top_k: int = 10,
                      category: Optional[str] = None) -> list[dict]:
    """Cosine similarity search in pgvector with optional category filter."""
    if not is_available():
        return []

    emb_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    where = ""
    params = [emb_str, top_k]
    if category:
        where = "AND llm_category = %s"
        params = [emb_str, category, top_k]

    conn = get_conn()
    try:
        cur = conn.cursor()
        sql = f"""
            SELECT project_id, user_id, prompt, llm_category, llm_style,
                   like_count, collect_count, score, display_image,
                   1 - (embedding <=> %s::vector) AS similarity_score
            FROM {settings.pgvector_table}
            WHERE embedding IS NOT NULL {where}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        if category:
            cur.execute(sql, (emb_str, category, emb_str, top_k))
        else:
            cur.execute(sql.replace("{where}", ""), (emb_str, emb_str, top_k))
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in rows]
    except Exception as e:
        logger.error("pgvector search failed: %s", e)
        return []
    finally:
        return_conn(conn)
