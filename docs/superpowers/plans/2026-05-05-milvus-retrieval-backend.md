# Milvus Retrieval Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Milvus-backed vector retrieval, keep existing memory/OpenSearch modes working, and introduce clear lexical/vector/fusion boundaries for future hybrid retrieval.

**Architecture:** Keep the public `SearchBackend` API consumed by `IngestionService` and `AnswerService`, but split implementation internals into `LexicalRetriever`, `VectorRetriever`, and `ResultFusion`. `SEARCH_BACKEND=milvus` uses Milvus for vector recall and a null lexical retriever; `SEARCH_BACKEND=hybrid` combines OpenSearch lexical recall with Milvus vector recall.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, httpx, pymilvus, Docker Compose, existing hash/OpenAI-compatible embedding providers.

---

## File Structure

- Modify `backend/app/core/config.py`: add vector, lexical, and Milvus settings.
- Modify `backend/app/services/indexing.py`: add candidate dataclasses, retriever protocols, memory retrievers, null lexical retriever, fusion, Milvus vector retriever, and hybrid wrappers while preserving `SearchBackend`.
- Modify `backend/app/services/container.py`: build search backends for `memory`, `opensearch`, `milvus`, and `hybrid`.
- Modify `backend/pyproject.toml`: add `pymilvus`.
- Modify `docker-compose.yml`: add Milvus standalone and volume.
- Modify `backend/tests/test_search_backend_config.py`: cover new config combinations.
- Create `backend/tests/test_retrieval_fusion.py`: cover candidate merge/scoring.
- Create `backend/tests/test_milvus_backend.py`: cover Milvus adapter with fake client.
- Modify docs: `README.md`, `docs/01-architecture-overview.md`, `docs/03-ingestion-retrieval-and-answering.md`, `docs/06-deployment-and-operations.md`, `docs/09-data-flow.md`.

## Task 1: Add Retrieval Configuration

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/tests/test_search_backend_config.py`

- [ ] **Step 1: Write failing config tests**

Add these imports and tests to `backend/tests/test_search_backend_config.py`:

```python
from app.services.indexing import HybridSearchBackend, MilvusVectorRetriever
```

```python
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
```

Update the invalid-value assertion:

```python
with pytest.raises(ValueError, match="Unsupported SEARCH_BACKEND"):
    build_search_backend(Settings(search_backend="invalid"), HashEmbeddingProvider())
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/test_search_backend_config.py -v
```

Expected: FAIL because `HybridSearchBackend`, `MilvusVectorRetriever`, and Milvus settings do not exist yet.

- [ ] **Step 3: Add settings fields**

In `backend/app/core/config.py`, add these fields after `search_backend` and OpenSearch settings:

```python
    vector_backend: str = os.getenv("VECTOR_BACKEND", "memory")
    lexical_backend: str = os.getenv("LEXICAL_BACKEND", "memory")
```

```python
    milvus_uri: str = os.getenv("MILVUS_URI", "http://localhost:19530")
    milvus_token: str = os.getenv("MILVUS_TOKEN", "")
    milvus_collection: str = os.getenv("MILVUS_COLLECTION", "rag_chunks")
    milvus_vector_field: str = os.getenv("MILVUS_VECTOR_FIELD", "embedding")
    milvus_metric_type: str = os.getenv("MILVUS_METRIC_TYPE", "COSINE")
    milvus_index_type: str = os.getenv("MILVUS_INDEX_TYPE", "AUTOINDEX")
```

- [ ] **Step 4: Add temporary class shells for import progress**

In `backend/app/services/indexing.py`, add these minimal class shells near the existing backend classes. Later tasks expand them into full implementations:

```python
class MilvusVectorRetriever:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs


class HybridSearchBackend:
    def __init__(self, backend_name: str, vector_retriever: object, lexical_retriever: object | None = None) -> None:
        self.backend_name = backend_name
        self.vector_retriever = vector_retriever
        self.lexical_retriever = lexical_retriever
```

- [ ] **Step 5: Wire the factory minimally**

Update imports in `backend/app/services/container.py`:

```python
from app.services.indexing import HybridSearchBackend, InMemorySearchBackend, MilvusVectorRetriever, OpenSearchSearchBackend
```

Update `build_search_backend` with temporary Milvus/hybrid branches:

```python
    if settings.search_backend == "milvus":
        return HybridSearchBackend(
            "milvus-vector",
            MilvusVectorRetriever(
                uri=settings.milvus_uri,
                token=settings.milvus_token,
                collection_name=settings.milvus_collection,
                vector_field=settings.milvus_vector_field,
                metric_type=settings.milvus_metric_type,
                index_type=settings.milvus_index_type,
                dimensions=settings.embedding_dimensions,
            ),
        )
    if settings.search_backend == "hybrid":
        return HybridSearchBackend(
            "opensearch-milvus-hybrid",
            MilvusVectorRetriever(
                uri=settings.milvus_uri,
                token=settings.milvus_token,
                collection_name=settings.milvus_collection,
                vector_field=settings.milvus_vector_field,
                metric_type=settings.milvus_metric_type,
                index_type=settings.milvus_index_type,
                dimensions=settings.embedding_dimensions,
            ),
        )
```

Change the final error message:

```python
    raise ValueError("Unsupported SEARCH_BACKEND. Expected one of: memory, opensearch, milvus, hybrid.")
```

- [ ] **Step 6: Run config tests**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/test_search_backend_config.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/config.py backend/app/services/container.py backend/app/services/indexing.py backend/tests/test_search_backend_config.py
git commit -m "feat: add milvus retrieval configuration"
```

## Task 2: Add Candidate Models and Fusion

**Files:**
- Modify: `backend/app/services/indexing.py`
- Create: `backend/tests/test_retrieval_fusion.py`

- [ ] **Step 1: Write failing fusion tests**

Create `backend/tests/test_retrieval_fusion.py`:

```python
from app.services.indexing import IndexedChunk, LexicalCandidate, ResultFusion, VectorCandidate


def make_chunk(chunk_id: str, content: str = "核心数据变更必须有回滚预案") -> IndexedChunk:
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
        embedding=[1.0, 0.0, 0.0, 0.0],
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
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/test_retrieval_fusion.py -v
```

Expected: FAIL because `LexicalCandidate`, `VectorCandidate`, and `ResultFusion` do not exist.

- [ ] **Step 3: Add candidate dataclasses and fusion**

In `backend/app/services/indexing.py`, add after `SearchResult`:

```python
@dataclass(slots=True)
class LexicalCandidate:
    chunk: IndexedChunk
    lexical_score: float


@dataclass(slots=True)
class VectorCandidate:
    chunk: IndexedChunk
    semantic_score: float
```

Add this class after `cosine_similarity`:

```python
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
```

- [ ] **Step 4: Run fusion tests**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/test_retrieval_fusion.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/indexing.py backend/tests/test_retrieval_fusion.py
git commit -m "feat: add retrieval result fusion"
```

## Task 3: Extract Memory Retrievers and Hybrid Wrapper

**Files:**
- Modify: `backend/app/services/indexing.py`
- Modify: `backend/tests/test_retrieval_fusion.py`

- [ ] **Step 1: Add failing hybrid backend test**

Append to `backend/tests/test_retrieval_fusion.py`:

```python
from app.services.indexing import HybridSearchBackend, MemoryLexicalRetriever, MemoryVectorRetriever
from app.services.llm import HashEmbeddingProvider


def test_hybrid_backend_combines_memory_lexical_and_vector_retrieval() -> None:
    provider = HashEmbeddingProvider(dimensions=4)
    lexical = MemoryLexicalRetriever()
    vector = MemoryVectorRetriever(provider)
    backend = HybridSearchBackend("memory-hybrid", lexical, vector, provider, ResultFusion())
    backend.upsert_chunks([make_chunk("chunk-3")])

    results = backend.search("核心数据回滚预案", "space-1", None, 5)

    assert results
    assert results[0].chunk_id == "chunk-3"
    assert results[0].lexical_score > 0
    assert results[0].semantic_score > 0
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/test_retrieval_fusion.py::test_hybrid_backend_combines_memory_lexical_and_vector_retrieval -v
```

Expected: FAIL because memory retrievers and full `HybridSearchBackend` behavior do not exist.

- [ ] **Step 3: Add retriever protocols**

In `backend/app/services/indexing.py`, add after `SearchBackend`:

```python
class LexicalRetriever(Protocol):
    def upsert_documents(self, chunks: list[IndexedChunk]) -> None:
        raise NotImplementedError

    def remove_document(self, document_id: str) -> None:
        raise NotImplementedError

    def search(self, query: str, knowledge_space_id: str, document_ids: list[str] | None, top_k: int) -> list[LexicalCandidate]:
        raise NotImplementedError


class VectorRetriever(Protocol):
    def upsert_vectors(self, chunks: list[IndexedChunk]) -> None:
        raise NotImplementedError

    def remove_document(self, document_id: str) -> None:
        raise NotImplementedError

    def search(
        self,
        query_embedding: list[float],
        knowledge_space_id: str,
        document_ids: list[str] | None,
        top_k: int,
    ) -> list[VectorCandidate]:
        raise NotImplementedError
```

- [ ] **Step 4: Add memory and null retrievers**

Add these classes before `InMemorySearchBackend`:

```python
class MemoryChunkStore:
    def __init__(self) -> None:
        self.chunks: dict[str, IndexedChunk] = {}
        self.lock = threading.RLock()


class MemoryLexicalRetriever:
    def __init__(self, store: MemoryChunkStore | None = None) -> None:
        self.store = store or MemoryChunkStore()

    def upsert_documents(self, chunks: list[IndexedChunk]) -> None:
        with self.store.lock:
            for chunk in chunks:
                if chunk.chunk_type != "parent":
                    self.store.chunks[chunk.chunk_id] = chunk

    def remove_document(self, document_id: str) -> None:
        with self.store.lock:
            chunk_ids = [chunk_id for chunk_id, chunk in self.store.chunks.items() if chunk.document_id == document_id]
            for chunk_id in chunk_ids:
                self.store.chunks.pop(chunk_id, None)

    def search(self, query: str, knowledge_space_id: str, document_ids: list[str] | None, top_k: int) -> list[LexicalCandidate]:
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
            score = len(query_tokens & content_tokens) / max(1, len(query_tokens))
            if score > 0:
                candidates.append(LexicalCandidate(chunk=chunk, lexical_score=round(score, 4)))
        candidates.sort(key=lambda item: item.lexical_score, reverse=True)
        return candidates[:top_k]


class MemoryVectorRetriever:
    def __init__(self, embedding_provider: EmbeddingProvider, store: MemoryChunkStore | None = None) -> None:
        self.embedding_provider = embedding_provider
        self.store = store or MemoryChunkStore()

    def upsert_vectors(self, chunks: list[IndexedChunk]) -> None:
        with self.store.lock:
            for chunk in chunks:
                if chunk.chunk_type != "parent":
                    self.store.chunks[chunk.chunk_id] = chunk

    def remove_document(self, document_id: str) -> None:
        with self.store.lock:
            chunk_ids = [chunk_id for chunk_id, chunk in self.store.chunks.items() if chunk.document_id == document_id]
            for chunk_id in chunk_ids:
                self.store.chunks.pop(chunk_id, None)

    def search(
        self,
        query_embedding: list[float],
        knowledge_space_id: str,
        document_ids: list[str] | None,
        top_k: int,
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
            score = max(0.0, cosine_similarity(query_embedding, chunk.embedding))
            if score > 0:
                candidates.append(VectorCandidate(chunk=chunk, semantic_score=round(score, 4)))
        candidates.sort(key=lambda item: item.semantic_score, reverse=True)
        return candidates[:top_k]


class NullLexicalRetriever:
    def upsert_documents(self, chunks: list[IndexedChunk]) -> None:
        return None

    def remove_document(self, document_id: str) -> None:
        return None

    def search(self, query: str, knowledge_space_id: str, document_ids: list[str] | None, top_k: int) -> list[LexicalCandidate]:
        return []
```

- [ ] **Step 5: Replace the temporary HybridSearchBackend**

Replace the temporary `HybridSearchBackend` shell with:

```python
class HybridSearchBackend:
    def __init__(
        self,
        backend_name: str,
        lexical_retriever: LexicalRetriever,
        vector_retriever: VectorRetriever,
        embedding_provider: EmbeddingProvider,
        fusion: ResultFusion | None = None,
    ) -> None:
        self.backend_name = backend_name
        self.lexical_retriever = lexical_retriever
        self.vector_retriever = vector_retriever
        self.embedding_provider = embedding_provider
        self.fusion = fusion or ResultFusion()

    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        searchable = [chunk for chunk in chunks if chunk.chunk_type != "parent"]
        self.lexical_retriever.upsert_documents(searchable)
        self.vector_retriever.upsert_vectors(searchable)

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
        expanded_top_k = max(top_k * 3, top_k)
        query_embedding = self.embedding_provider.embed(query)
        lexical_candidates = self.lexical_retriever.search(query, knowledge_space_id, document_ids, expanded_top_k)
        vector_candidates = self.vector_retriever.search(query_embedding, knowledge_space_id, document_ids, expanded_top_k)
        return self.fusion.merge(query, lexical_candidates, vector_candidates, top_k)
```

- [ ] **Step 6: Update InMemorySearchBackend to use the new wrapper**

Replace `InMemorySearchBackend.__init__`, `upsert_chunks`, `remove_document`, and `search` with delegation to a shared store:

```python
    def __init__(self, embedding_provider: EmbeddingProvider) -> None:
        self.embedding_provider = embedding_provider
        self._store = MemoryChunkStore()
        self._backend = HybridSearchBackend(
            self.backend_name,
            MemoryLexicalRetriever(self._store),
            MemoryVectorRetriever(embedding_provider, self._store),
            embedding_provider,
        )

    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        self._backend.upsert_chunks(chunks)

    def remove_document(self, document_id: str) -> None:
        self._backend.remove_document(document_id)

    def search(self, query: str, knowledge_space_id: str, document_ids: list[str] | None = None, top_k: int = 50) -> list[SearchResult]:
        return self._backend.search(query, knowledge_space_id, document_ids, top_k)
```

Keep `bootstrap_from_database`, but replace the final lock assignment with:

```python
        self._store.chunks = {chunk.chunk_id: chunk for chunk in indexed}
```

- [ ] **Step 7: Run retrieval tests**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/test_retrieval_fusion.py tests/test_search_backend_config.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/indexing.py backend/tests/test_retrieval_fusion.py
git commit -m "refactor: split retrieval fusion internals"
```

## Task 4: Extract OpenSearch Lexical Retriever

**Files:**
- Modify: `backend/app/services/indexing.py`
- Modify: `backend/tests/test_opensearch_backend.py`

- [ ] **Step 1: Add OpenSearch lexical retriever test**

In `backend/tests/test_opensearch_backend.py`, add:

```python
from app.services.indexing import OpenSearchLexicalRetriever
```

Append:

```python
def test_opensearch_lexical_retriever_returns_candidates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "HEAD" and request.url.path == "/rag_chunks":
            return httpx.Response(200)
        if request.method == "POST" and request.url.path == "/rag_chunks/_search":
            return httpx.Response(
                200,
                json={
                    "hits": {
                        "hits": [
                            {
                                "_score": 4.0,
                                "_source": {
                                    "chunk_id": "chunk-1",
                                    "knowledge_space_id": "space-1",
                                    "document_id": "doc-1",
                                    "document_title": "发布管理规范.md",
                                    "fragment_id": "frag-1",
                                    "chunk_type": "fixed",
                                    "parent_id": None,
                                    "section_title": "发布前检查",
                                    "heading_path": ["发布管理规范", "发布前检查"],
                                    "page_number": None,
                                    "content": "核心数据变更必须完成测试准入和回滚预案确认。",
                                    "embedding": [0.2, 0.1, 0.3, 0.4],
                                },
                            }
                        ]
                    }
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    retriever = OpenSearchLexicalRetriever(
        base_url="http://opensearch:9200",
        index_name="rag_chunks",
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://opensearch:9200"),
    )

    candidates = retriever.search("核心数据变更", "space-1", None, 5)

    assert len(candidates) == 1
    assert candidates[0].chunk.chunk_id == "chunk-1"
    assert candidates[0].lexical_score == 1.0
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/test_opensearch_backend.py::test_opensearch_lexical_retriever_returns_candidates -v
```

Expected: FAIL because `OpenSearchLexicalRetriever` does not exist.

- [ ] **Step 3: Implement OpenSearchLexicalRetriever**

Add `OpenSearchLexicalRetriever` with this full behavior. The request bodies match the current `OpenSearchSearchBackend`; the output changes from `SearchResult` to `LexicalCandidate`.

```python
class OpenSearchLexicalRetriever:
    def __init__(self, base_url: str, index_name: str = "rag_chunks", client: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.index_name = index_name
        self.client = client or httpx.Client(base_url=self.base_url, timeout=10.0)
        self._index_ready = False

    def upsert_documents(self, chunks: list[IndexedChunk]) -> None:
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

    def search(self, query: str, knowledge_space_id: str, document_ids: list[str] | None, top_k: int) -> list[LexicalCandidate]:
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
        hits = response.json().get("hits", {}).get("hits", [])

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
        candidates: list[LexicalCandidate] = []
        for hit in hits:
            source = hit.get("_source", {})
            lexical_score = round((hit.get("_score") or 0.0) / max_raw_score, 4)
            chunk = IndexedChunk(
                chunk_id=source["chunk_id"],
                knowledge_space_id=source["knowledge_space_id"],
                document_id=source["document_id"],
                document_title=source["document_title"],
                fragment_id=source["fragment_id"],
                section_title=source["section_title"],
                heading_path=source.get("heading_path", []),
                page_number=source.get("page_number"),
                content=source["content"],
                embedding=source.get("embedding", []),
                chunk_type=source.get("chunk_type", "fixed"),
                parent_id=source.get("parent_id"),
            )
            candidates.append(LexicalCandidate(chunk=chunk, lexical_score=lexical_score))
        return candidates[:top_k]

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
        raise RuntimeError(f"OpenSearch failed to {operation}: {response.status_code} {response.text}")

    def _terms(self, value: str) -> str:
        return " ".join(tokenize_text(value))
```

- [ ] **Step 4: Rebuild OpenSearchSearchBackend as wrapper**

Replace `OpenSearchSearchBackend` internals with:

```python
class OpenSearchSearchBackend(HybridSearchBackend):
    backend_name = "opensearch-hybrid"

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        base_url: str,
        index_name: str = "rag_chunks",
        client: httpx.Client | None = None,
    ) -> None:
        store = MemoryChunkStore()
        lexical = OpenSearchLexicalRetriever(base_url, index_name, client)
        vector = MemoryVectorRetriever(embedding_provider, store)
        super().__init__(self.backend_name, lexical, vector, embedding_provider)

    def upsert_chunks(self, chunks: list[IndexedChunk]) -> None:
        searchable = [chunk for chunk in chunks if chunk.chunk_type != "parent"]
        self.lexical_retriever.upsert_documents(searchable)
        self.vector_retriever.upsert_vectors(searchable)
```

This keeps existing `test_opensearch_backend_indexes_and_reranks` passing and keeps OpenSearch mode's local semantic rerank using the same chunk embeddings.

- [ ] **Step 5: Run OpenSearch tests**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/test_opensearch_backend.py tests/test_search_backend_config.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/indexing.py backend/tests/test_opensearch_backend.py
git commit -m "refactor: extract opensearch lexical retriever"
```

## Task 5: Implement Milvus Vector Retriever

**Files:**
- Modify: `backend/app/services/indexing.py`
- Create: `backend/tests/test_milvus_backend.py`

- [ ] **Step 1: Write fake-client Milvus tests**

Create `backend/tests/test_milvus_backend.py`:

```python
from app.services.indexing import IndexedChunk, MilvusVectorRetriever


class FakeMilvusClient:
    def __init__(self) -> None:
        self.collections: set[str] = set()
        self.inserted: list[dict] = []
        self.deleted_filters: list[str] = []

    def has_collection(self, collection_name: str) -> bool:
        return collection_name in self.collections

    def create_collection(self, **kwargs) -> None:
        self.collections.add(kwargs["collection_name"])
        self.create_kwargs = kwargs

    def create_index(self, **kwargs) -> None:
        self.index_kwargs = kwargs

    def load_collection(self, collection_name: str) -> None:
        self.loaded_collection = collection_name

    def upsert(self, collection_name: str, data: list[dict]) -> None:
        self.collections.add(collection_name)
        self.inserted.extend(data)

    def delete(self, collection_name: str, filter: str) -> None:
        self.deleted_filters.append(filter)

    def search(self, **kwargs):
        return [
            [
                {
                    "id": "chunk-1",
                    "distance": 0.91,
                    "entity": {
                        "chunk_id": "chunk-1",
                        "knowledge_space_id": "space-1",
                        "document_id": "doc-1",
                        "document_title": "发布管理规范.md",
                        "fragment_id": "frag-1",
                        "chunk_type": "fixed",
                        "parent_id": "",
                        "section_title": "发布前检查",
                        "heading_path": ["发布管理规范", "发布前检查"],
                        "page_number": None,
                        "content": "核心数据变更必须有回滚预案。",
                    },
                }
            ]
        ]


def make_chunk(chunk_id: str = "chunk-1", chunk_type: str = "fixed") -> IndexedChunk:
    return IndexedChunk(
        chunk_id=chunk_id,
        knowledge_space_id="space-1",
        document_id="doc-1",
        document_title="发布管理规范.md",
        fragment_id="frag-1",
        section_title="发布前检查",
        heading_path=["发布管理规范", "发布前检查"],
        page_number=None,
        content="核心数据变更必须有回滚预案。",
        embedding=[1.0, 0.0, 0.0, 0.0],
        chunk_type=chunk_type,
    )


def test_milvus_vector_retriever_creates_collection_and_upserts_chunks() -> None:
    client = FakeMilvusClient()
    retriever = MilvusVectorRetriever(
        uri="http://localhost:19530",
        token="",
        collection_name="rag_chunks",
        vector_field="embedding",
        metric_type="COSINE",
        index_type="AUTOINDEX",
        dimensions=4,
        client=client,
    )

    retriever.upsert_vectors([make_chunk(), make_chunk("parent-1", "parent")])

    assert "rag_chunks" in client.collections
    assert len(client.inserted) == 1
    assert client.inserted[0]["chunk_id"] == "chunk-1"
    assert client.inserted[0]["embedding"] == [1.0, 0.0, 0.0, 0.0]


def test_milvus_vector_retriever_searches_with_filters() -> None:
    client = FakeMilvusClient()
    retriever = MilvusVectorRetriever(
        uri="http://localhost:19530",
        token="",
        collection_name="rag_chunks",
        vector_field="embedding",
        metric_type="COSINE",
        index_type="AUTOINDEX",
        dimensions=4,
        client=client,
    )

    results = retriever.search([1.0, 0.0, 0.0, 0.0], "space-1", ["doc-1"], 5)

    assert results[0].chunk.chunk_id == "chunk-1"
    assert results[0].semantic_score == 0.91


def test_milvus_vector_retriever_rejects_dimension_mismatch() -> None:
    client = FakeMilvusClient()
    retriever = MilvusVectorRetriever(
        uri="http://localhost:19530",
        token="",
        collection_name="rag_chunks",
        vector_field="embedding",
        metric_type="COSINE",
        index_type="AUTOINDEX",
        dimensions=4,
        client=client,
    )

    try:
        retriever.upsert_vectors([make_chunk()])
        retriever.search([1.0, 0.0], "space-1", None, 5)
    except ValueError as exc:
        assert "Embedding dimension mismatch" in str(exc)
    else:
        raise AssertionError("Expected dimension mismatch")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/test_milvus_backend.py -v
```

Expected: FAIL because `MilvusVectorRetriever` is only a temporary shell.

- [ ] **Step 3: Add pymilvus dependency**

In `backend/pyproject.toml`, add:

```toml
  "pymilvus>=2.4.0,<3.0.0",
```

- [ ] **Step 4: Implement MilvusVectorRetriever**

Replace the temporary shell with:

```python
class MilvusVectorRetriever:
    def __init__(
        self,
        uri: str,
        token: str,
        collection_name: str,
        vector_field: str,
        metric_type: str,
        index_type: str,
        dimensions: int,
        client: object | None = None,
    ) -> None:
        self.uri = uri
        self.token = token
        self.collection_name = collection_name
        self.vector_field = vector_field
        self.metric_type = metric_type
        self.index_type = index_type
        self.dimensions = dimensions
        self.client = client or self._build_client()
        self._collection_ready = False

    def _build_client(self) -> object:
        try:
            from pymilvus import MilvusClient
        except ImportError as exc:
            raise RuntimeError("pymilvus is required when SEARCH_BACKEND uses Milvus.") from exc
        if self.token:
            return MilvusClient(uri=self.uri, token=self.token)
        return MilvusClient(uri=self.uri)

    def upsert_vectors(self, chunks: list[IndexedChunk]) -> None:
        searchable = [chunk for chunk in chunks if chunk.chunk_type != "parent"]
        if not searchable:
            return
        self._ensure_collection()
        rows = [self._chunk_to_row(chunk) for chunk in searchable]
        self.client.upsert(collection_name=self.collection_name, data=rows)

    def remove_document(self, document_id: str) -> None:
        self._ensure_collection()
        self.client.delete(collection_name=self.collection_name, filter=f'document_id == "{document_id}"')

    def search(
        self,
        query_embedding: list[float],
        knowledge_space_id: str,
        document_ids: list[str] | None,
        top_k: int,
    ) -> list[VectorCandidate]:
        self._validate_embedding(query_embedding)
        self._ensure_collection()
        filters = [f'knowledge_space_id == "{knowledge_space_id}"']
        if document_ids:
            quoted = ", ".join(f'"{document_id}"' for document_id in document_ids)
            filters.append(f"document_id in [{quoted}]")
        response = self.client.search(
            collection_name=self.collection_name,
            data=[query_embedding],
            anns_field=self.vector_field,
            limit=top_k,
            filter=" and ".join(filters),
            output_fields=[
                "chunk_id",
                "knowledge_space_id",
                "document_id",
                "document_title",
                "fragment_id",
                "chunk_type",
                "parent_id",
                "section_title",
                "heading_path",
                "page_number",
                "content",
            ],
        )
        hits = response[0] if response else []
        candidates: list[VectorCandidate] = []
        for hit in hits:
            entity = hit.get("entity", {})
            chunk = IndexedChunk(
                chunk_id=entity["chunk_id"],
                knowledge_space_id=entity["knowledge_space_id"],
                document_id=entity["document_id"],
                document_title=entity.get("document_title", ""),
                fragment_id=entity["fragment_id"],
                section_title=entity.get("section_title", ""),
                heading_path=entity.get("heading_path", []),
                page_number=entity.get("page_number"),
                content=entity.get("content", ""),
                embedding=[],
                chunk_type=entity.get("chunk_type", "fixed"),
                parent_id=entity.get("parent_id") or None,
            )
            candidates.append(VectorCandidate(chunk=chunk, semantic_score=round(float(hit.get("distance", 0.0)), 4)))
        return candidates

    def _ensure_collection(self) -> None:
        if self._collection_ready:
            return
        if not self.client.has_collection(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                dimension=self.dimensions,
                primary_field_name="chunk_id",
                vector_field_name=self.vector_field,
                metric_type=self.metric_type,
                auto_id=False,
            )
            self.client.create_index(
                collection_name=self.collection_name,
                field_name=self.vector_field,
                index_params={"index_type": self.index_type, "metric_type": self.metric_type},
            )
        self.client.load_collection(self.collection_name)
        self._collection_ready = True

    def _chunk_to_row(self, chunk: IndexedChunk) -> dict:
        self._validate_embedding(chunk.embedding)
        return {
            "chunk_id": chunk.chunk_id,
            self.vector_field: chunk.embedding,
            "knowledge_space_id": chunk.knowledge_space_id,
            "document_id": chunk.document_id,
            "document_title": chunk.document_title,
            "fragment_id": chunk.fragment_id,
            "chunk_type": chunk.chunk_type,
            "parent_id": chunk.parent_id or "",
            "section_title": chunk.section_title,
            "heading_path": chunk.heading_path,
            "page_number": chunk.page_number,
            "content": chunk.content,
        }

    def _validate_embedding(self, embedding: list[float]) -> None:
        if len(embedding) != self.dimensions:
            raise ValueError(
                f"Embedding dimension mismatch for Milvus collection {self.collection_name}: "
                f"expected {self.dimensions}, got {len(embedding)}. Rebuild the index or use matching embedding settings."
            )
```

- [ ] **Step 5: Run Milvus tests**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/test_milvus_backend.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/indexing.py backend/pyproject.toml backend/tests/test_milvus_backend.py
git commit -m "feat: add milvus vector retriever"
```

## Task 6: Wire Milvus and Hybrid Backends

**Files:**
- Modify: `backend/app/services/container.py`
- Modify: `backend/tests/test_search_backend_config.py`

- [ ] **Step 1: Add config behavior tests**

Append to `backend/tests/test_search_backend_config.py`:

```python
def test_milvus_backend_uses_null_lexical_retriever_by_default() -> None:
    backend = build_search_backend(
        Settings(search_backend="milvus", embedding_dimensions=8),
        HashEmbeddingProvider(dimensions=8),
    )

    assert backend.backend_name == "milvus-vector"
    assert backend.lexical_retriever.__class__.__name__ == "NullLexicalRetriever"


def test_hybrid_backend_uses_opensearch_lexical_and_milvus_vector() -> None:
    backend = build_search_backend(
        Settings(search_backend="hybrid", embedding_dimensions=8),
        HashEmbeddingProvider(dimensions=8),
    )

    assert backend.backend_name == "opensearch-milvus-hybrid"
    assert backend.lexical_retriever.__class__.__name__ == "OpenSearchLexicalRetriever"
    assert backend.vector_retriever.__class__.__name__ == "MilvusVectorRetriever"
```

- [ ] **Step 2: Run and verify failure**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/test_search_backend_config.py -v
```

Expected: FAIL until factory wiring passes real retrievers to `HybridSearchBackend`.

- [ ] **Step 3: Update container imports**

Use this import block in `backend/app/services/container.py`:

```python
from app.services.indexing import (
    HybridSearchBackend,
    InMemorySearchBackend,
    MilvusVectorRetriever,
    NullLexicalRetriever,
    OpenSearchLexicalRetriever,
    OpenSearchSearchBackend,
)
```

- [ ] **Step 4: Add Milvus helper**

Add below `get_container`:

```python
def build_milvus_vector_retriever(settings: Settings) -> MilvusVectorRetriever:
    return MilvusVectorRetriever(
        uri=settings.milvus_uri,
        token=settings.milvus_token,
        collection_name=settings.milvus_collection,
        vector_field=settings.milvus_vector_field,
        metric_type=settings.milvus_metric_type,
        index_type=settings.milvus_index_type,
        dimensions=settings.embedding_dimensions,
    )
```

- [ ] **Step 5: Update build_search_backend**

Use:

```python
def build_search_backend(settings: Settings, embedding_provider: object) -> InMemorySearchBackend | OpenSearchSearchBackend | HybridSearchBackend:
    if settings.search_backend == "memory":
        return InMemorySearchBackend(embedding_provider)
    if settings.search_backend == "opensearch":
        return OpenSearchSearchBackend(
            embedding_provider,
            base_url=settings.opensearch_url,
            index_name=settings.opensearch_index,
        )
    if settings.search_backend == "milvus":
        return HybridSearchBackend(
            "milvus-vector",
            NullLexicalRetriever(),
            build_milvus_vector_retriever(settings),
            embedding_provider,
        )
    if settings.search_backend == "hybrid":
        return HybridSearchBackend(
            "opensearch-milvus-hybrid",
            OpenSearchLexicalRetriever(
                base_url=settings.opensearch_url,
                index_name=settings.opensearch_index,
            ),
            build_milvus_vector_retriever(settings),
            embedding_provider,
        )
    raise ValueError("Unsupported SEARCH_BACKEND. Expected one of: memory, opensearch, milvus, hybrid.")
```

- [ ] **Step 6: Run backend config tests**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/test_search_backend_config.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/container.py backend/tests/test_search_backend_config.py
git commit -m "feat: wire milvus search backend"
```

## Task 7: Add Docker Compose Milvus

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add Milvus service**

In `docker-compose.yml`, add after `opensearch`:

```yaml
  milvus:
    image: docker.m.daocloud.io/milvusdb/milvus:v2.4.15
    command: ["milvus", "run", "standalone"]
    environment:
      ETCD_USE_EMBED: "true"
      ETCD_DATA_DIR: /var/lib/milvus/etcd
      COMMON_STORAGETYPE: local
    ports:
      - "19530:19530"
      - "9091:9091"
    volumes:
      - milvus_data:/var/lib/milvus
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9091/healthz"]
      interval: 30s
      timeout: 10s
      retries: 5
```

Add a volume:

```yaml
  milvus_data:
```

- [ ] **Step 2: Validate compose config**

Run:

```bash
docker compose config
```

Expected: PASS and rendered config includes `milvus`.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "chore: add milvus compose service"
```

## Task 8: Update Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/01-architecture-overview.md`
- Modify: `docs/03-ingestion-retrieval-and-answering.md`
- Modify: `docs/06-deployment-and-operations.md`
- Modify: `docs/09-data-flow.md`

- [ ] **Step 1: Update README overview**

Change the architecture line from:

```text
Hybrid Retrieval (OpenSearch adapter / memory fallback)
```

to:

```text
Hybrid Retrieval (memory / OpenSearch / Milvus / OpenSearch+Milvus)
```

Update Docker Compose command examples to include `milvus`:

```bash
docker compose up -d postgres redis opensearch milvus minio temporal temporal-ui
```

Update `SEARCH_BACKEND` notes:

```text
SEARCH_BACKEND=memory: no external search dependency.
SEARCH_BACKEND=opensearch: OpenSearch lexical recall with local embedding rerank.
SEARCH_BACKEND=milvus: Milvus vector recall.
SEARCH_BACKEND=hybrid: OpenSearch lexical recall plus Milvus vector recall.
```

- [ ] **Step 2: Update architecture docs**

In `docs/01-architecture-overview.md`, update retrieval section to state:

```text
检索层现在保留 memory 和 opensearch 兼容路径，并新增 Milvus 向量检索路径。
长期生产形态是 OpenSearch 负责词法召回，Milvus 负责向量召回，应用层融合排序。
PostgreSQL 仍然是 documents/chunks/jobs/traces 等业务事实源。
```

- [ ] **Step 3: Update ingestion/retrieval docs**

In `docs/03-ingestion-retrieval-and-answering.md`, add:

```text
Milvus 不生成 embedding。导入阶段仍由 embedding provider 生成 chunk embedding，并写入 PostgreSQL 的 chunks.embedding；当 SEARCH_BACKEND=milvus 或 hybrid 时，同一份向量会写入 Milvus collection。
```

- [ ] **Step 4: Update deployment docs**

In `docs/06-deployment-and-operations.md`, add environment variables:

```bash
MILVUS_URI=http://localhost:19530
MILVUS_COLLECTION=rag_chunks
MILVUS_METRIC_TYPE=COSINE
MILVUS_INDEX_TYPE=AUTOINDEX
```

Add host-run example:

```bash
SEARCH_BACKEND=milvus \
MILVUS_URI=http://localhost:19530 \
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 5: Update data flow docs**

In `docs/09-data-flow.md`, update backend list:

```text
- memory-hybrid
- opensearch-hybrid
- milvus-vector
- opensearch-milvus-hybrid
```

- [ ] **Step 6: Commit**

```bash
git add README.md docs/01-architecture-overview.md docs/03-ingestion-retrieval-and-answering.md docs/06-deployment-and-operations.md docs/09-data-flow.md
git commit -m "docs: document milvus retrieval backend"
```

## Task 9: Full Verification

**Files:**
- No code edits unless verification reveals a bug.

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
cd backend
.venv/bin/python -m pytest tests/test_search_backend_config.py tests/test_retrieval_fusion.py tests/test_milvus_backend.py tests/test_opensearch_backend.py -v
```

Expected: PASS.

- [ ] **Step 2: Run full backend tests**

Run:

```bash
cd backend
SEARCH_BACKEND=memory EMBEDDING_BACKEND=hash .venv/bin/python -m pytest tests -v
```

Expected: PASS.

- [ ] **Step 3: Validate compose config**

Run:

```bash
docker compose config
```

Expected: PASS.

- [ ] **Step 4: Check git status**

Run:

```bash
git status --short
```

Expected: clean working tree after all task commits.

## Self-Review

- Spec coverage: plan covers retrieval split, Milvus vector retriever, `milvus` and `hybrid` modes, compose service, docs, and tests.
- Completeness scan: implementation steps avoid open-ended notes and include concrete code for new units.
- Type consistency: public `SearchBackend` remains `upsert_chunks`, `remove_document`, and `search`; internal retrievers use `LexicalCandidate`, `VectorCandidate`, and `ResultFusion`.
