from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # AWS Athena
    aws_region: str = "us-west-2"
    athena_workgroup: str = "data-agent"
    athena_output_location: str = "s3://tripo-telescope/data-agent/athena-results/"
    athena_query_timeout_sec: int = 300
    athena_poll_interval_sec: float = 1.5

    # Claude API
    claude_api_key: str = ""
    claude_base_url: str = ""
    claude_model: str = "claude-sonnet-4-6"

    # Cache
    cache_db_path: str = "./cache/analysis_cache.db"
    cache_ttl_hours: int = 24

    # Analysis
    llm_sample_size: int = 500
    llm_quality_sample_size: int = 100
    topic_num_clusters: int = 15

    # Embedding / FAISS
    faiss_index_path: str = "./cache/faiss_index.bin"
    faiss_id_map_path: str = "./cache/faiss_id_map.json"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # PostgreSQL / pgvector (Phase 3)
    pg_connection_string: str = ""
    pg_enabled: bool = False
    pgvector_table: str = "prompt_embedding"

    # Redis (Phase 3)
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False
    redis_default_ttl: int = 600  # 10 min

    # Celery (Phase 3)
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_enabled: bool = False

    # BERTopic (Phase 2)
    bertopic_min_topic_size: int = 20
    bertopic_sample_size: int = 10000
    bertopic_enabled: bool = True

    # Retention (Phase 2)
    retention_cohort_window_days: int = 60

    # Template mining (Phase 2)
    template_min_likes: int = 1
    template_max_templates: int = 100

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
