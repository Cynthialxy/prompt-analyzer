-- pgvector initialization script
-- Run this once on your PostgreSQL instance to set up vector storage

-- Enable the vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Main embedding table
CREATE TABLE IF NOT EXISTS prompt_embedding (
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
    embedding vector(384),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Cosine similarity index (IVFFlat)
CREATE INDEX IF NOT EXISTS idx_prompt_embedding_cosine
ON prompt_embedding
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Lookup indexes
CREATE INDEX IF NOT EXISTS idx_prompt_embedding_project ON prompt_embedding (project_id);
CREATE INDEX IF NOT EXISTS idx_prompt_embedding_category ON prompt_embedding (llm_category);
CREATE INDEX IF NOT EXISTS idx_prompt_embedding_user ON prompt_embedding (user_id);
CREATE INDEX IF NOT EXISTS idx_prompt_embedding_likes ON prompt_embedding (like_count DESC);

-- LLM response cache (avoid re-analyzing same prompt)
CREATE TABLE IF NOT EXISTS llm_cache (
    id SERIAL PRIMARY KEY,
    prompt_hash TEXT UNIQUE NOT NULL,
    prompt_text TEXT,
    response_type TEXT NOT NULL,  -- 'intent_v2', 'quality_v2', 'optimization'
    response_json JSONB NOT NULL,
    model TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '7 days'
);

CREATE INDEX IF NOT EXISTS idx_llm_cache_hash ON llm_cache (prompt_hash);
CREATE INDEX IF NOT EXISTS idx_llm_cache_type ON llm_cache (response_type);

-- Task tracking (for Celery async tasks)
CREATE TABLE IF NOT EXISTS async_tasks (
    id SERIAL PRIMARY KEY,
    task_id TEXT UNIQUE NOT NULL,
    task_name TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, running, completed, failed
    params_json JSONB,
    result_json JSONB,
    error TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_async_tasks_status ON async_tasks (status);
