from __future__ import annotations

import pytest

from app.services.indexing import IndexedChunk, MilvusVectorRetriever


class FakeMilvusClient:
    def __init__(self) -> None:
        self.collections: set[str] = set()
        self.created_collections: list[dict] = []
        self.created_indexes: list[dict] = []
        self.loaded_collections: list[str] = []
        self.inserted_rows: list[dict] = []
        self.deleted_filters: list[str] = []
        self.search_kwargs: list[dict] = []
        self.search_results: list[list[dict]] = []

    def has_collection(self, collection_name: str) -> bool:
        return collection_name in self.collections

    def create_collection(self, **kwargs: object) -> None:
        self.created_collections.append(kwargs)
        self.collections.add(str(kwargs["collection_name"]))

    def create_index(self, **kwargs: object) -> None:
        self.created_indexes.append(kwargs)

    def load_collection(self, collection_name: str) -> None:
        self.loaded_collections.append(collection_name)

    def upsert(self, **kwargs: object) -> None:
        self.inserted_rows.extend(kwargs["data"])

    def delete(self, **kwargs: object) -> None:
        self.deleted_filters.append(str(kwargs["filter"]))

    def search(self, **kwargs: object) -> list[list[dict]]:
        self.search_kwargs.append(kwargs)
        return self.search_results


def make_chunk(chunk_id: str = "chunk-1", chunk_type: str = "fixed") -> IndexedChunk:
    return IndexedChunk(
        chunk_id=chunk_id,
        knowledge_space_id="space-1",
        document_id="doc-1",
        document_title="Runbook.md",
        fragment_id="frag-1",
        section_title="Rollback",
        heading_path=["Runbook", "Rollback"],
        page_number=3,
        content="Rollback requires a tested recovery plan.",
        embedding=[1.0, 0.0, 0.0, 0.0],
        chunk_type=chunk_type,
        parent_id=None,
    )


def make_retriever(client: FakeMilvusClient) -> MilvusVectorRetriever:
    return MilvusVectorRetriever(
        uri="http://localhost:19530",
        token="token",
        collection_name="rag_chunks",
        vector_field="embedding",
        metric_type="COSINE",
        index_type="AUTOINDEX",
        dimensions=4,
        client=client,
    )


def test_upsert_vectors_creates_collection_and_skips_parent_chunks() -> None:
    client = FakeMilvusClient()
    retriever = make_retriever(client)

    retriever.upsert_vectors([make_chunk(), make_chunk("parent-1", chunk_type="parent")])

    assert client.created_collections == [
        {
            "collection_name": "rag_chunks",
            "dimension": 4,
            "primary_field_name": "chunk_id",
            "vector_field_name": "embedding",
            "metric_type": "COSINE",
            "auto_id": False,
        }
    ]
    assert client.created_indexes == [
        {
            "collection_name": "rag_chunks",
            "field_name": "embedding",
            "index_params": {"index_type": "AUTOINDEX", "metric_type": "COSINE"},
        }
    ]
    assert client.loaded_collections == ["rag_chunks"]
    assert len(client.inserted_rows) == 1
    assert client.inserted_rows[0]["chunk_id"] == "chunk-1"
    assert client.inserted_rows[0]["embedding"] == [1.0, 0.0, 0.0, 0.0]


def test_search_filters_by_space_and_documents_and_returns_candidates() -> None:
    client = FakeMilvusClient()
    client.collections.add("rag_chunks")
    client.search_results = [
        [
            {
                "distance": 0.87654,
                "entity": {
                    "chunk_id": "chunk-1",
                    "knowledge_space_id": "space-1",
                    "document_id": "doc-1",
                    "document_title": "Runbook.md",
                    "fragment_id": "frag-1",
                    "chunk_type": "fixed",
                    "parent_id": "",
                    "section_title": "Rollback",
                    "heading_path": ["Runbook", "Rollback"],
                    "page_number": 3,
                    "content": "Rollback requires a tested recovery plan.",
                },
            }
        ]
    ]
    retriever = make_retriever(client)

    candidates = retriever.retrieve([1.0, 0.0, 0.0, 0.0], "space-1", ["doc-1", "doc-2"], 5)

    assert len(candidates) == 1
    assert candidates[0].chunk.chunk_id == "chunk-1"
    assert candidates[0].chunk.parent_id is None
    assert candidates[0].chunk.embedding == []
    assert candidates[0].semantic_score == 0.8765
    assert client.search_kwargs[0]["filter"] == 'knowledge_space_id == "space-1" and document_id in ["doc-1", "doc-2"]'
    assert client.search_kwargs[0]["limit"] == 5


def test_upsert_vectors_rejects_embedding_dimension_mismatch() -> None:
    client = FakeMilvusClient()
    retriever = make_retriever(client)
    chunk = make_chunk()
    chunk.embedding = [1.0, 0.0]

    with pytest.raises(ValueError, match="Embedding dimension mismatch"):
        retriever.upsert_vectors([chunk])


def test_remove_document_records_document_filter() -> None:
    client = FakeMilvusClient()
    client.collections.add("rag_chunks")
    retriever = make_retriever(client)

    retriever.remove_document("doc-1")

    assert client.deleted_filters == ['document_id == "doc-1"']
