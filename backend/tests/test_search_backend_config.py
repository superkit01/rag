import pytest

from app.core.config import Settings
from app.services.container import build_search_backend
from app.services.indexing import HybridSearchBackend, InMemorySearchBackend, MilvusVectorRetriever, OpenSearchSearchBackend
from app.services.llm import HashEmbeddingProvider


def test_build_search_backend_supports_memory() -> None:
    backend = build_search_backend(Settings(search_backend="memory"), HashEmbeddingProvider())

    assert isinstance(backend, InMemorySearchBackend)


def test_build_search_backend_supports_opensearch() -> None:
    backend = build_search_backend(
        Settings(search_backend="opensearch", opensearch_url="http://localhost:9200", opensearch_index="rag_chunks"),
        HashEmbeddingProvider(),
    )

    assert isinstance(backend, OpenSearchSearchBackend)


def test_build_search_backend_supports_milvus() -> None:
    backend = build_search_backend(
        Settings(
            search_backend="milvus",
            embedding_backend="hash",
            embedding_dimensions=8,
            milvus_uri="http://localhost:19530",
            milvus_collection="rag_chunks",
        ),
        HashEmbeddingProvider(dimensions=8),
    )

    assert isinstance(backend, HybridSearchBackend)
    assert backend.backend_name == "milvus-vector"
    assert isinstance(backend.vector_retriever, MilvusVectorRetriever)


def test_build_search_backend_supports_hybrid() -> None:
    backend = build_search_backend(
        Settings(
            search_backend="hybrid",
            embedding_backend="hash",
            embedding_dimensions=8,
            opensearch_url="http://localhost:9200",
            opensearch_index="rag_chunks",
            milvus_uri="http://localhost:19530",
            milvus_collection="rag_chunks",
        ),
        HashEmbeddingProvider(dimensions=8),
    )

    assert isinstance(backend, HybridSearchBackend)
    assert backend.backend_name == "opensearch-milvus-hybrid"


def test_build_search_backend_rejects_invalid_value() -> None:
    with pytest.raises(ValueError, match="Unsupported SEARCH_BACKEND"):
        build_search_backend(Settings(search_backend="invalid"), HashEmbeddingProvider())
