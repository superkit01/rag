from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
import json
import math
import threading
from typing import Protocol

import httpx
from sqlalchemy.orm import Session

from app.models.entities import Chunk
from app.services.text_utils import tokenize_text


@dataclass(slots=True)
class IndexedChunk:
    chunk_id: str
    knowledge_space_id: str
    document_id: str
    document_title: str
    fragment_id: str
    section_title: str
    heading_path: list[str]
    page_number: int | None
    content: str
    embedding: list[float]
    chunk_type: str = "fixed"
    parent_id: str | None = None


@dataclass(slots=True)
class SearchResult:
    chunk_id: str
    knowledge_space_id: str
    document_id: str
    document_title: str
    fragment_id: str
    section_title: str
    heading_path: list[str]
    page_number: int | None
    content: str
    score: float
    lexical_score: float
    semantic_score: float
    chunk_type: str = "fixed"
    parent_id: str | None = None


@dataclass(slots=True)
class LexicalCandidate:
    chunk: IndexedChunk
    lexical_score: float


@dataclass(slots=True)
class VectorCandidate:
    chunk: IndexedChunk
    semantic_score: float


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]:
        ...

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        ...


class SearchBackend(Protocol):
    backend_name: str

    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        ...

    def remove_document(self, document_id: str) -> None:
        ...

    def search(self, query: str, knowledge_space_id: str, document_ids: list[str] | None, top_k: int) -> list[SearchResult]:
        ...


class LexicalRetriever(Protocol):
    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        raise NotImplementedError

    def remove_document(self, document_id: str) -> None:
        raise NotImplementedError

    def retrieve(
        self,
        query: str,
        knowledge_space_id: str,
        document_ids: list[str] | None,
        top_k: int,
    ) -> list[LexicalCandidate]:
        raise NotImplementedError


class VectorRetriever(Protocol):
    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        raise NotImplementedError

    def remove_document(self, document_id: str) -> None:
        raise NotImplementedError

    def retrieve(
        self,
        query_embedding: list[float],
        knowledge_space_id: str,
        document_ids: list[str] | None,
        top_k: int,
    ) -> list[VectorCandidate]:
        raise NotImplementedError


class MilvusVectorRetriever:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.args = args
        self.kwargs = kwargs


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


class ResultFusion:
    def merge(
        self,
        query: str,
        lexical_candidates: list[LexicalCandidate],
        vector_candidates: list[VectorCandidate],
        top_k: int,
    ) -> list[SearchResult]:
        query_tokens = set(tokenize_text(query))
        by_chunk_id: dict[str, dict[str, object]] = {}

        for candidate in lexical_candidates:
            entry = by_chunk_id.setdefault(
                candidate.chunk.chunk_id,
                {"chunk": candidate.chunk, "lexical_score": 0.0, "semantic_score": 0.0},
            )
            entry["lexical_score"] = max(float(entry["lexical_score"]), candidate.lexical_score)

        for candidate in vector_candidates:
            entry = by_chunk_id.setdefault(
                candidate.chunk.chunk_id,
                {"chunk": candidate.chunk, "lexical_score": 0.0, "semantic_score": 0.0},
            )
            entry["semantic_score"] = max(float(entry["semantic_score"]), candidate.semantic_score)

        results: list[SearchResult] = []
        for entry in by_chunk_id.values():
            chunk = entry["chunk"]
            assert isinstance(chunk, IndexedChunk)
            lexical_score = round(float(entry["lexical_score"]), 4)
            semantic_score = round(float(entry["semantic_score"]), 4)
            heading_boost = 0.08 if query_tokens & set(tokenize_text(" ".join(chunk.heading_path))) else 0.0
            combined = round((0.55 * lexical_score) + (0.45 * semantic_score) + heading_boost, 4)
            if combined <= 0:
                continue
            results.append(
                SearchResult(
                    chunk_id=chunk.chunk_id,
                    knowledge_space_id=chunk.knowledge_space_id,
                    document_id=chunk.document_id,
                    document_title=chunk.document_title,
                    fragment_id=chunk.fragment_id,
                    section_title=chunk.section_title,
                    heading_path=chunk.heading_path,
                    page_number=chunk.page_number,
                    content=chunk.content,
                    score=combined,
                    lexical_score=lexical_score,
                    semantic_score=semantic_score,
                    chunk_type=chunk.chunk_type,
                    parent_id=chunk.parent_id,
                )
            )
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]


class MemoryChunkStore:
    def __init__(self) -> None:
        self.chunks: dict[str, IndexedChunk] = {}
        self.lock = threading.RLock()


class MemoryLexicalRetriever:
    def __init__(self, store: MemoryChunkStore | None = None) -> None:
        self.store = store or MemoryChunkStore()

    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        with self.store.lock:
            for chunk in chunks:
                if chunk.chunk_type == "parent":
                    continue
                self.store.chunks[chunk.chunk_id] = chunk

    def remove_document(self, document_id: str) -> None:
        with self.store.lock:
            to_remove = [chunk_id for chunk_id, chunk in self.store.chunks.items() if chunk.document_id == document_id]
            for chunk_id in to_remove:
                self.store.chunks.pop(chunk_id, None)

    def retrieve(
        self,
        query: str,
        knowledge_space_id: str,
        document_ids: list[str] | None = None,
        top_k: int = 50,
    ) -> list[LexicalCandidate]:
        query_tokens = set(tokenize_text(query))
        allowed_document_ids = set(document_ids or [])
        candidates: list[LexicalCandidate] = []
        with self.store.lock:
            chunks = list(self.store.chunks.values())
        for chunk in chunks:
            if chunk.knowledge_space_id != knowledge_space_id:
                continue
            if allowed_document_ids and chunk.document_id not in allowed_document_ids:
                continue
            content_tokens = set(tokenize_text(chunk.content))
            lexical_score = len(query_tokens & content_tokens) / max(1, len(query_tokens))
            if lexical_score <= 0:
                continue
            candidates.append(LexicalCandidate(chunk=chunk, lexical_score=lexical_score))
        candidates.sort(key=lambda item: item.lexical_score, reverse=True)
        return candidates[:top_k]


class MemoryVectorRetriever:
    def __init__(self, embedding_provider: EmbeddingProvider, store: MemoryChunkStore | None = None) -> None:
        self.embedding_provider = embedding_provider
        self.store = store or MemoryChunkStore()

    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        with self.store.lock:
            for chunk in chunks:
                if chunk.chunk_type == "parent":
                    continue
                self.store.chunks[chunk.chunk_id] = replace(chunk, embedding=self.embedding_provider.embed(chunk.content))

    def remove_document(self, document_id: str) -> None:
        with self.store.lock:
            to_remove = [chunk_id for chunk_id, chunk in self.store.chunks.items() if chunk.document_id == document_id]
            for chunk_id in to_remove:
                self.store.chunks.pop(chunk_id, None)

    def retrieve(
        self,
        query_embedding: list[float],
        knowledge_space_id: str,
        document_ids: list[str] | None = None,
        top_k: int = 50,
    ) -> list[VectorCandidate]:
        allowed_document_ids = set(document_ids or [])
        candidates: list[VectorCandidate] = []
        with self.store.lock:
            chunks = list(self.store.chunks.values())
        for chunk in chunks:
            if chunk.knowledge_space_id != knowledge_space_id:
                continue
            if allowed_document_ids and chunk.document_id not in allowed_document_ids:
                continue
            semantic_score = max(0.0, cosine_similarity(query_embedding, chunk.embedding))
            if semantic_score <= 0:
                continue
            candidates.append(VectorCandidate(chunk=chunk, semantic_score=semantic_score))
        candidates.sort(key=lambda item: item.semantic_score, reverse=True)
        return candidates[:top_k]


class NullLexicalRetriever:
    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        del chunks

    def remove_document(self, document_id: str) -> None:
        del document_id

    def retrieve(
        self,
        query: str,
        knowledge_space_id: str,
        document_ids: list[str] | None = None,
        top_k: int = 50,
    ) -> list[LexicalCandidate]:
        del query, knowledge_space_id, document_ids, top_k
        return []


class HybridSearchBackend:
    def __init__(
        self,
        backend_name: str,
        lexical_retriever: LexicalRetriever,
        vector_retriever: VectorRetriever,
        embedding_provider: EmbeddingProvider,
        fusion: ResultFusion | None = None,
        candidate_top_k_multiplier: int | None = 3,
    ) -> None:
        self.backend_name = backend_name
        self.lexical_retriever = lexical_retriever
        self.vector_retriever = vector_retriever
        self.embedding_provider = embedding_provider
        self.fusion = fusion or ResultFusion()
        self.candidate_top_k_multiplier = candidate_top_k_multiplier

    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        chunks = [chunk for chunk in chunks if chunk.chunk_type != "parent"]
        self.lexical_retriever.upsert_chunks(chunks)
        self.vector_retriever.upsert_chunks(chunks)

    def remove_document(self, document_id: str) -> None:
        self.lexical_retriever.remove_document(document_id)
        self.vector_retriever.remove_document(document_id)

    def search(
        self,
        query: str,
        knowledge_space_id: str,
        document_ids: list[str] | None = None,
        top_k: int = 50,
    ) -> list[SearchResult]:
        query_embedding = self.embedding_provider.embed(query)
        expanded_top_k = self._candidate_top_k(top_k)
        lexical_candidates = self.lexical_retriever.retrieve(query, knowledge_space_id, document_ids, expanded_top_k)
        vector_candidates = self.vector_retriever.retrieve(query_embedding, knowledge_space_id, document_ids, expanded_top_k)
        return self.fusion.merge(query, lexical_candidates, vector_candidates, top_k)

    def _candidate_top_k(self, top_k: int) -> int:
        if self.candidate_top_k_multiplier is not None:
            return max(top_k * self.candidate_top_k_multiplier, top_k)
        store = getattr(self.lexical_retriever, "store", None) or getattr(self.vector_retriever, "store", None)
        chunks = getattr(store, "chunks", None)
        if chunks is not None:
            return max(len(chunks), top_k)
        return max(top_k * 1000, top_k)


class InMemorySearchBackend:
    backend_name = "memory-hybrid"

    def __init__(self, embedding_provider: EmbeddingProvider) -> None:
        self.embedding_provider = embedding_provider
        self._store = MemoryChunkStore()
        self._backend = HybridSearchBackend(
            self.backend_name,
            MemoryLexicalRetriever(self._store),
            MemoryVectorRetriever(embedding_provider, self._store),
            embedding_provider,
            candidate_top_k_multiplier=None,
        )

    @property
    def _chunks(self) -> dict[str, IndexedChunk]:
        return self._store.chunks

    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        self._backend.upsert_chunks(chunks)

    def remove_document(self, document_id: str) -> None:
        self._backend.remove_document(document_id)

    def search(self, query: str, knowledge_space_id: str, document_ids: list[str] | None = None, top_k: int = 50) -> list[SearchResult]:
        return self._backend.search(query, knowledge_space_id, document_ids, top_k)

    def bootstrap_from_database(self, db: Session) -> None:
        chunks = db.query(Chunk).filter(Chunk.chunk_type.in_(("fixed", "child"))).all()
        indexed = [
            IndexedChunk(
                chunk_id=chunk.id,
                knowledge_space_id=chunk.knowledge_space_id,
                document_id=chunk.document_id,
                document_title=chunk.document.title,
                fragment_id=chunk.fragment_id,
                section_title=chunk.section_title,
                heading_path=chunk.heading_path,
                page_number=chunk.page_number,
                content=chunk.content,
                embedding=chunk.embedding,
                chunk_type=chunk.chunk_type,
                parent_id=chunk.parent_id,
            )
            for chunk in chunks
        ]
        with self._store.lock:
            self._store.chunks = {chunk.chunk_id: chunk for chunk in indexed}


class OpenSearchSearchBackend(InMemorySearchBackend):
    backend_name = "opensearch-hybrid"

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        base_url: str,
        index_name: str = "rag_chunks",
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(embedding_provider)
        self.base_url = base_url.rstrip("/")
        self.index_name = index_name
        self.client = client or httpx.Client(base_url=self.base_url, timeout=10.0)
        self._index_ready = False

    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        chunks = [chunk for chunk in chunks if chunk.chunk_type != "parent"]
        if not chunks:
            return
        self._ensure_index()
        operations: list[str] = []
        for chunk in chunks:
            operations.append(json.dumps({"index": {"_index": self.index_name, "_id": chunk.chunk_id}}))
            operations.append(
                json.dumps(
                    {
                        "chunk_id": chunk.chunk_id,
                        "knowledge_space_id": chunk.knowledge_space_id,
                        "document_id": chunk.document_id,
                        "document_title": chunk.document_title,
                        "document_title_terms": self._terms(chunk.document_title),
                        "fragment_id": chunk.fragment_id,
                        "chunk_type": chunk.chunk_type,
                        "parent_id": chunk.parent_id,
                        "section_title": chunk.section_title,
                        "section_title_terms": self._terms(chunk.section_title),
                        "heading_path": chunk.heading_path,
                        "heading_path_text": " / ".join(chunk.heading_path),
                        "heading_path_terms": self._terms(" ".join(chunk.heading_path)),
                        "page_number": chunk.page_number,
                        "content": chunk.content,
                        "content_terms": self._terms(chunk.content),
                        "embedding": chunk.embedding,
                    },
                    ensure_ascii=False,
                )
            )
        payload = "\n".join(operations) + "\n"
        response = self.client.post(
            "/_bulk?refresh=wait_for",
            content=payload.encode("utf-8"),
            headers={"Content-Type": "application/x-ndjson"},
        )
        self._raise_for_status(response, operation="bulk upsert chunks")
        body = response.json()
        if body.get("errors"):
            raise RuntimeError("OpenSearch bulk upsert reported item-level errors.")

    def remove_document(self, document_id: str) -> None:
        self._ensure_index()
        response = self.client.post(
            f"/{self.index_name}/_delete_by_query?refresh=true",
            json={"query": {"term": {"document_id": document_id}}},
        )
        self._raise_for_status(response, operation="delete document chunks")

    def search(
        self,
        query: str,
        knowledge_space_id: str,
        document_ids: list[str] | None = None,
        top_k: int = 50,
    ) -> list[SearchResult]:
        self._ensure_index()
        query_tokens = tokenize_text(query)
        query_terms = " ".join(query_tokens) or query
        filters: list[dict] = [{"term": {"knowledge_space_id": knowledge_space_id}}]
        if document_ids:
            filters.append({"terms": {"document_id": document_ids}})

        body = {
            "size": max(top_k * 3, top_k),
            "_source": True,
            "query": {
                "bool": {
                    "filter": filters,
                    "must": [
                        {
                            "multi_match": {
                                "query": query_terms,
                                "fields": [
                                    "content_terms^4",
                                    "section_title_terms^2",
                                    "heading_path_terms^2",
                                    "document_title_terms^2",
                                ],
                                "type": "best_fields",
                            }
                        }
                    ],
                }
            },
        }
        response = self.client.post(f"/{self.index_name}/_search", json=body)
        self._raise_for_status(response, operation="search chunks")
        payload = response.json()
        hits = payload.get("hits", {}).get("hits", [])

        if not hits:
            fallback = {
                "size": max(top_k, 20),
                "_source": True,
                "query": {"bool": {"filter": filters}},
            }
            fallback_response = self.client.post(f"/{self.index_name}/_search", json=fallback)
            self._raise_for_status(fallback_response, operation="fallback search chunks")
            hits = fallback_response.json().get("hits", {}).get("hits", [])

        max_raw_score = max((hit.get("_score") or 0.0) for hit in hits) if hits else 1.0
        max_raw_score = max(max_raw_score, 1.0)
        query_embedding = self.embedding_provider.embed(query)
        query_token_set = set(query_tokens)

        results: list[SearchResult] = []
        for hit in hits:
            source = hit.get("_source", {})
            lexical_score = round((hit.get("_score") or 0.0) / max_raw_score, 4)
            semantic_score = max(0.0, cosine_similarity(query_embedding, source.get("embedding", [])))
            heading_terms = set((source.get("heading_path_terms") or "").split())
            heading_boost = 0.08 if query_token_set & heading_terms else 0.0
            combined = round((0.55 * lexical_score) + (0.45 * semantic_score) + heading_boost, 4)
            if combined <= 0:
                continue
            results.append(
                SearchResult(
                    chunk_id=source["chunk_id"],
                    knowledge_space_id=source["knowledge_space_id"],
                    document_id=source["document_id"],
                    document_title=source["document_title"],
                    fragment_id=source["fragment_id"],
                    section_title=source["section_title"],
                    heading_path=source.get("heading_path", []),
                    page_number=source.get("page_number"),
                    content=source["content"],
                    score=combined,
                    lexical_score=lexical_score,
                    semantic_score=round(semantic_score, 4),
                    chunk_type=source.get("chunk_type", "fixed"),
                    parent_id=source.get("parent_id"),
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]

    def _ensure_index(self) -> None:
        if self._index_ready:
            return
        response = self.client.head(f"/{self.index_name}")
        if response.status_code == 404:
            create_response = self.client.put(
                f"/{self.index_name}",
                json={
                    "mappings": {
                        "properties": {
                            "chunk_id": {"type": "keyword"},
                            "knowledge_space_id": {"type": "keyword"},
                            "document_id": {"type": "keyword"},
                            "document_title": {"type": "text"},
                            "document_title_terms": {"type": "text"},
                            "fragment_id": {"type": "keyword"},
                            "chunk_type": {"type": "keyword"},
                            "parent_id": {"type": "keyword"},
                            "section_title": {"type": "text"},
                            "section_title_terms": {"type": "text"},
                            "heading_path": {"type": "keyword"},
                            "heading_path_text": {"type": "text"},
                            "heading_path_terms": {"type": "text"},
                            "page_number": {"type": "integer"},
                            "content": {"type": "text"},
                            "content_terms": {"type": "text"},
                            "embedding": {"type": "float"},
                        }
                    }
                },
            )
            if create_response.status_code not in {200, 201}:
                error_type = create_response.json().get("error", {}).get("type")
                if error_type != "resource_already_exists_exception":
                    self._raise_for_status(create_response, operation="create index")
        else:
            self._raise_for_status(response, operation="check index")
        self._index_ready = True

    def _raise_for_status(self, response: httpx.Response, operation: str) -> None:
        if response.status_code < 400:
            return
        detail = response.text
        raise RuntimeError(f"OpenSearch failed to {operation}: {response.status_code} {detail}")

    def _terms(self, value: str) -> str:
        return " ".join(tokenize_text(value))
