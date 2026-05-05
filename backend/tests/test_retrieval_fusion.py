from app.services.indexing import (
    HybridSearchBackend,
    IndexedChunk,
    InMemorySearchBackend,
    LexicalCandidate,
    MemoryLexicalRetriever,
    MemoryVectorRetriever,
    ResultFusion,
    VectorCandidate,
)
from app.services.llm import HashEmbeddingProvider


class StaticEmbeddingProvider:
    def __init__(self, embeddings: dict[str, list[float]]) -> None:
        self.embeddings = embeddings

    def embed(self, text: str) -> list[float]:
        return self.embeddings.get(text, [0.0, 0.0])

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class RaisingEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        del text
        raise AssertionError("upsert must not embed chunk content")

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        del texts
        raise AssertionError("upsert must not embed chunk content")


def make_chunk(
    chunk_id: str,
    content: str = "核心数据变更必须有回滚预案",
    embedding: list[float] | None = None,
) -> IndexedChunk:
    return IndexedChunk(
        chunk_id=chunk_id,
        knowledge_space_id="space-1",
        document_id=f"doc-{chunk_id}",
        document_title=f"{chunk_id}.md",
        fragment_id=f"frag-{chunk_id}",
        section_title="发布前检查",
        heading_path=["发布管理规范", "发布前检查"],
        page_number=None,
        content=content,
        embedding=embedding or [1.0, 0.0, 0.0, 0.0],
    )


def test_fusion_merges_lexical_and_vector_candidates_by_chunk_id() -> None:
    chunk = make_chunk("chunk-1")
    fusion = ResultFusion()

    results = fusion.merge(
        query="核心数据变更",
        lexical_candidates=[LexicalCandidate(chunk=chunk, lexical_score=0.8)],
        vector_candidates=[VectorCandidate(chunk=chunk, semantic_score=0.6)],
        top_k=5,
    )

    assert len(results) == 1
    assert results[0].chunk_id == "chunk-1"
    assert results[0].lexical_score == 0.8
    assert results[0].semantic_score == 0.6
    assert results[0].score > 0.0


def test_fusion_supports_vector_only_results() -> None:
    chunk = make_chunk("chunk-2")
    fusion = ResultFusion()

    results = fusion.merge(
        query="回滚预案",
        lexical_candidates=[],
        vector_candidates=[VectorCandidate(chunk=chunk, semantic_score=0.72)],
        top_k=5,
    )

    assert len(results) == 1
    assert results[0].chunk_id == "chunk-2"
    assert results[0].lexical_score == 0.0
    assert results[0].semantic_score == 0.72


def test_hybrid_backend_combines_memory_lexical_and_vector_retrieval() -> None:
    provider = HashEmbeddingProvider(dimensions=4)
    lexical = MemoryLexicalRetriever()
    vector = MemoryVectorRetriever(provider)
    backend = HybridSearchBackend("memory-hybrid", lexical, vector, provider, ResultFusion())
    content = "核心数据变更必须有回滚预案"
    backend.upsert_chunks([make_chunk("chunk-3", content, provider.embed(content))])

    results = backend.search("核心数据回滚预案", "space-1", None, 5)

    assert results
    assert results[0].chunk_id == "chunk-3"
    assert results[0].lexical_score > 0
    assert results[0].semantic_score > 0


def test_memory_backend_exhaustively_fuses_candidates_before_ranking() -> None:
    query = "alpha beta gamma delta"
    balanced_content = "alpha beta gamma balanced"
    provider = StaticEmbeddingProvider(
        {
            query: [1.0, 0.0],
        }
    )
    backend = InMemorySearchBackend(provider)
    backend.upsert_chunks(
        [
            make_chunk("lexical-1", "alpha beta gamma delta lexical one", [0.0, 0.0]),
            make_chunk("lexical-2", "alpha beta gamma delta lexical two", [0.0, 0.0]),
            make_chunk("lexical-3", "alpha beta gamma delta lexical three", [0.0, 0.0]),
            make_chunk("vector-1", "vector one", [1.0, 0.0]),
            make_chunk("vector-2", "vector two", [1.0, 0.0]),
            make_chunk("vector-3", "vector three", [1.0, 0.0]),
            make_chunk("balanced", balanced_content, [0.75, 0.661438]),
        ]
    )

    results = backend.search(query, "space-1", None, 1)

    assert results[0].chunk_id == "balanced"
    assert results[0].lexical_score == 0.75
    assert results[0].semantic_score == 0.75


def test_memory_backend_preserves_chunks_compatibility_property() -> None:
    backend = InMemorySearchBackend(HashEmbeddingProvider(dimensions=4))
    backend.upsert_chunks([make_chunk("chunk-4")])

    assert backend._chunks
    assert backend._chunks["chunk-4"].chunk_id == "chunk-4"


def test_memory_vector_retriever_preserves_stored_embedding_on_upsert() -> None:
    retriever = MemoryVectorRetriever(RaisingEmbeddingProvider())
    chunk = make_chunk("chunk-5", embedding=[0.6, 0.8])

    retriever.upsert_chunks([chunk])
    candidates = retriever.retrieve([0.6, 0.8], "space-1", None, 5)

    assert candidates
    assert candidates[0].chunk.chunk_id == "chunk-5"
    assert candidates[0].chunk.embedding == [0.6, 0.8]
    assert candidates[0].semantic_score == 1.0
