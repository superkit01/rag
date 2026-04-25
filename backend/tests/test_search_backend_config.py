import pytest

from app.core.config import Settings
from app.services.container import build_search_backend
from app.services.indexing import InMemorySearchBackend, OpenSearchSearchBackend
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


def test_build_search_backend_rejects_invalid_value() -> None:
    with pytest.raises(ValueError, match="Unsupported SEARCH_BACKEND"):
        build_search_backend(Settings(search_backend="invalid"), HashEmbeddingProvider())
