from __future__ import annotations

from dataclasses import dataclass
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


class InMemorySearchBackend:
    backend_name = "memory-hybrid"

    def __init__(self, embedding_provider: EmbeddingProvider) -> None:
        self.embedding_provider = embedding_provider
        self._chunks: dict[str, IndexedChunk] = {}
        self._lock = threading.RLock()

    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        with self._lock:
            for chunk in chunks:
                self._chunks[chunk.chunk_id] = chunk

    def remove_document(self, document_id: str) -> None:
        with self._lock:
            to_remove = [chunk_id for chunk_id, chunk in self._chunks.items() if chunk.document_id == document_id]
            for chunk_id in to_remove:
                self._chunks.pop(chunk_id, None)

    def search(self, query: str, knowledge_space_id: str, document_ids: list[str] | None = None, top_k: int = 50) -> list[SearchResult]:
        query_tokens = set(tokenize_text(query))
        query_embedding = self.embedding_provider.embed(query)
        results: list[SearchResult] = []
        allowed_document_ids = set(document_ids or [])
        with self._lock:
            chunks = list(self._chunks.values())
        for chunk in chunks:
            if chunk.knowledge_space_id != knowledge_space_id:
                continue
            if allowed_document_ids and chunk.document_id not in allowed_document_ids:
                continue
            content_tokens = set(tokenize_text(chunk.content))
            lexical_score = len(query_tokens & content_tokens) / max(1, len(query_tokens))
            semantic_score = max(0.0, cosine_similarity(query_embedding, chunk.embedding))
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
                )
            )
        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]

    def bootstrap_from_database(self, db: Session) -> None:
        chunks = db.query(Chunk).all()
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
            )
            for chunk in chunks
        ]
        self.upsert_chunks(indexed)


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
