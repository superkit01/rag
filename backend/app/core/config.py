from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Enterprise RAG Knowledge Hub")
    app_env: str = os.getenv("APP_ENV", "development")
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./rag.db")
    workflow_backend: str = os.getenv("WORKFLOW_BACKEND", "temporal")
    search_backend: str = os.getenv("SEARCH_BACKEND", "memory")
    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "hash")
    opensearch_url: str = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
    opensearch_index: str = os.getenv("OPENSEARCH_INDEX", "rag_chunks")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    object_storage_endpoint: str = os.getenv("OBJECT_STORAGE_ENDPOINT", "http://localhost:9000")
    object_storage_bucket: str = os.getenv("OBJECT_STORAGE_BUCKET", "rag-documents")
    object_storage_access_key: str = os.getenv("OBJECT_STORAGE_ACCESS_KEY", "minioadmin")
    object_storage_secret_key: str = os.getenv("OBJECT_STORAGE_SECRET_KEY", "minioadmin")
    object_storage_local_root: str = os.getenv("OBJECT_STORAGE_LOCAL_ROOT", "./data/object_storage")
    object_storage_backend: str = os.getenv("OBJECT_STORAGE_BACKEND", "local")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "")
    openai_embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "")
    openai_embedding_batch_size: int = int(os.getenv("OPENAI_EMBEDDING_BATCH_SIZE", "10"))
    temporal_host: str = os.getenv("TEMPORAL_HOST", "localhost:7233")
    temporal_namespace: str = os.getenv("TEMPORAL_NAMESPACE", "default")
    temporal_task_queue: str = os.getenv("TEMPORAL_TASK_QUEUE", "rag-jobs")
    temporal_connect_retries: int = int(os.getenv("TEMPORAL_CONNECT_RETRIES", "20"))
    temporal_connect_delay_seconds: float = float(os.getenv("TEMPORAL_CONNECT_DELAY_SECONDS", "1.0"))
    retrieval_top_k: int = int(os.getenv("RETRIEVAL_TOP_K", "50"))
    rerank_top_k: int = int(os.getenv("RERANK_TOP_K", "8"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "700"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "100"))
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "128"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
