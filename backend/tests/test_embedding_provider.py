import json

import httpx
import pytest

from app.core.config import Settings
from app.services.indexing import cosine_similarity
from app.services.container import ServiceContainer
from app.services.llm import (
    HashEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    build_embedding_provider,
)
from app.services.chunking_strategies import SemanticStrategy


def test_hash_embedding_provider_supports_batch_embedding() -> None:
    provider = HashEmbeddingProvider(dimensions=8)

    embeddings = provider.embed_many(["核心数据发布", "回滚预案"])

    assert len(embeddings) == 2
    assert len(embeddings[0]) == 8
    assert embeddings[0] == provider.embed("核心数据发布")


def test_openai_compatible_embedding_provider_batches_inputs() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content.decode("utf-8")))
        assert request.url.path == "/v1/embeddings"
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0, 0.0]},
                    {"index": 0, "embedding": [1.0, 0.0, 0.0]},
                ]
            },
        )

    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://example.com/v1",
        api_key="test-key",
        model="text-embedding-demo",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    embeddings = provider.embed_many(["第一段", "第二段"])

    assert requests == [{"model": "text-embedding-demo", "input": ["第一段", "第二段"]}]
    assert embeddings == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]


def test_openai_compatible_embedding_provider_splits_large_batches() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        requests.append(payload)
        batch = payload["input"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": index, "embedding": [float(index), float(len(text))]}
                    for index, text in enumerate(batch)
                ]
            },
        )

    provider = OpenAICompatibleEmbeddingProvider(
        base_url="https://example.com/v1",
        api_key="test-key",
        model="text-embedding-demo",
        batch_size=2,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    embeddings = provider.embed_many(["第一段", "第二段", "第三段", "第四段", "第五段"])

    assert requests == [
        {"model": "text-embedding-demo", "input": ["第一段", "第二段"]},
        {"model": "text-embedding-demo", "input": ["第三段", "第四段"]},
        {"model": "text-embedding-demo", "input": ["第五段"]},
    ]
    assert embeddings == [[0.0, 3.0], [1.0, 3.0], [0.0, 3.0], [1.0, 3.0], [0.0, 3.0]]


def test_build_embedding_provider_uses_hash_by_default() -> None:
    provider = build_embedding_provider(Settings(embedding_backend="hash"))

    assert isinstance(provider, HashEmbeddingProvider)


def test_build_embedding_provider_requires_openai_config() -> None:
    with pytest.raises(ValueError, match="OPENAI_API_KEY and OPENAI_EMBEDDING_MODEL"):
        build_embedding_provider(Settings(embedding_backend="openai", openai_api_key="", openai_embedding_model=""))


def test_semantic_chunking_uses_semantic_embedding_model_for_boundary_detection() -> None:
    container = ServiceContainer(
        Settings(
            embedding_backend="openai",
            openai_api_key="test-key",
            openai_embedding_model="retrieval-embedding-model",
            chunking_strategy="semantic",
            semantic_embedding_model="semantic-boundary-model",
        )
    )

    assert isinstance(container.embedding_provider, OpenAICompatibleEmbeddingProvider)
    assert container.embedding_provider.model == "retrieval-embedding-model"
    assert isinstance(container.chunker, SemanticStrategy)
    assert isinstance(container.chunker.embedding_provider, OpenAICompatibleEmbeddingProvider)
    assert container.chunker.embedding_provider.model == "semantic-boundary-model"


def test_cosine_similarity_returns_zero_for_dimension_mismatch() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0
