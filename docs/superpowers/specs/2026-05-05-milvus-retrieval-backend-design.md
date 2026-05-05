# Milvus Retrieval Backend Design

## Goal

Introduce Milvus as the vector retrieval backend for the RAG platform while preserving PostgreSQL as the source of truth and keeping the current OpenSearch path available for compatibility.

The first implementation should make `SEARCH_BACKEND=milvus` usable in local and Docker-based development. It should also reshape the retrieval layer so future OpenSearch + Milvus hybrid retrieval can be added without another large rewrite.

## Non-Goals

- Do not replace PostgreSQL. Documents, chunks, jobs, traces, feedback, and evaluation data remain in the relational database.
- Do not remove the existing `memory` or `opensearch` search modes.
- Do not introduce a production reranker model in this phase.
- Do not implement advanced Milvus cluster tuning, sharding policy, or multi-tenant collection management.
- Do not silently fall back to memory retrieval when Milvus is selected and unavailable.

## Current Context

The current retrieval contract is centered on `SearchBackend` in `backend/app/services/indexing.py`:

- `InMemorySearchBackend` stores searchable chunks in process memory and computes lexical plus embedding scores locally.
- `OpenSearchSearchBackend` stores chunk fields in OpenSearch, uses OpenSearch for lexical candidate recall, and performs embedding cosine rerank in Python.
- Ingestion already generates embeddings before indexing and persists them to `chunks.embedding`.
- Only searchable chunk types, currently `fixed` and `child`, are indexed. `parent` chunks are not indexed.
- Query routes bootstrap only the memory backend from PostgreSQL.

This means Milvus does not need to create embeddings. It needs to store vectors, retrieve similar vectors, and integrate with the existing answer/citation flow.

## Recommended Architecture

Split retrieval responsibilities into clearer components while preserving the public `SearchBackend` shape used by `AnswerService`:

```text
SearchBackend / HybridSearchBackend
  -> LexicalRetriever
  -> VectorRetriever
  -> ResultFusion
```

### VectorRetriever

`VectorRetriever` owns vector index operations:

- `upsert_vectors(chunks: list[IndexedChunk])`
- `remove_document(document_id: str)`
- `search(query_embedding: list[float], knowledge_space_id: str, document_ids: list[str] | None, top_k: int)`

Implementations:

- `MemoryVectorRetriever` for tests and lightweight local mode.
- `MilvusVectorRetriever` using the official `pymilvus` client.

### LexicalRetriever

`LexicalRetriever` owns keyword candidate recall:

- `upsert_documents(chunks: list[IndexedChunk])`
- `remove_document(document_id: str)`
- `search(query: str, knowledge_space_id: str, document_ids: list[str] | None, top_k: int)`

Implementations:

- `MemoryLexicalRetriever` for lightweight local mode and optional Milvus-only scoring support.
- `OpenSearchLexicalRetriever` extracted from the existing `OpenSearchSearchBackend` behavior.
- `NullLexicalRetriever` for vector-only Milvus mode.

### ResultFusion

`ResultFusion` merges candidates by `chunk_id` and produces existing `SearchResult` objects:

- Preserve `lexical_score` and `semantic_score`.
- Preserve heading boost behavior where lexical metadata is available.
- Prefer existing score weighting initially: `0.55 lexical + 0.45 semantic + heading_boost`.
- In vector-only mode, set `lexical_score=0.0` and let semantic score dominate.

The external `SearchBackend.search()` API should continue returning `list[SearchResult]` so `AnswerService`, evaluation, and frontend citation rendering do not need broad changes.

## Backend Modes

Keep existing modes working and add Milvus-oriented modes:

```text
SEARCH_BACKEND=memory
SEARCH_BACKEND=opensearch
SEARCH_BACKEND=milvus
SEARCH_BACKEND=hybrid
```

Behavior:

- `memory`: current lightweight local behavior, implemented via memory lexical + memory vector + fusion or kept as a compatible wrapper.
- `opensearch`: current behavior remains available for compatibility.
- `milvus`: Milvus vector retrieval with `NullLexicalRetriever` by default. It can optionally use memory lexical scoring for rerank if configured, but must not depend on OpenSearch.
- `hybrid`: OpenSearch lexical retrieval + Milvus vector retrieval + fusion. This is the target long-term production shape, but the first implementation can keep it behind configuration and focused tests.

## Configuration

Add configuration fields to `Settings`:

```bash
SEARCH_BACKEND=memory
VECTOR_BACKEND=memory
LEXICAL_BACKEND=memory

MILVUS_URI=http://localhost:19530
MILVUS_TOKEN=
MILVUS_COLLECTION=rag_chunks
MILVUS_VECTOR_FIELD=embedding
MILVUS_METRIC_TYPE=COSINE
MILVUS_INDEX_TYPE=AUTOINDEX
```

Recommended defaults:

- `SEARCH_BACKEND=memory`
- `VECTOR_BACKEND=memory`
- `LEXICAL_BACKEND=memory`
- `MILVUS_COLLECTION=rag_chunks`
- `MILVUS_METRIC_TYPE=COSINE`
- `MILVUS_INDEX_TYPE=AUTOINDEX`

Mode-derived defaults:

- `SEARCH_BACKEND=milvus` should imply `VECTOR_BACKEND=milvus` and `LEXICAL_BACKEND=none` unless explicitly overridden.
- `SEARCH_BACKEND=hybrid` should imply `VECTOR_BACKEND=milvus` and `LEXICAL_BACKEND=opensearch`.
- Invalid combinations should fail during container construction with clear errors.

Supported `LEXICAL_BACKEND` values are `memory`, `opensearch`, and `none`.

## Milvus Collection Schema

Milvus stores retrieval fields, not the full business record.

Fields:

- `chunk_id`: primary key, string
- `embedding`: float vector, dimension from `EMBEDDING_DIMENSIONS` or the actual embedding provider dimensions
- `knowledge_space_id`: string scalar
- `document_id`: string scalar
- `fragment_id`: string scalar
- `chunk_type`: string scalar
- `parent_id`: nullable/string scalar when supported; empty string otherwise

Optional short fields may be duplicated for fewer database round trips:

- `document_title`
- `section_title`
- `heading_path_text`

Long chunk content should remain sourced from PostgreSQL. If the first implementation stores `content` in Milvus for simpler `SearchResult` construction, it must still treat PostgreSQL as authoritative and preserve the ability to rebuild Milvus from database chunks.

## Data Flow

### Import and Reindex

```text
PreparedChunk
  -> embedding_provider.embed_many()
  -> PostgreSQL chunks.embedding
  -> VectorRetriever.upsert_vectors()
  -> LexicalRetriever.upsert_documents()
```

Rules:

- Index only searchable chunks: `fixed` and `child`.
- Skip `parent` chunks.
- If Milvus upsert fails, fail the import or reindex job.
- A completed import/reindex still means database writes and retrieval indexes are ready to query.

### Query

```text
query
  -> embedding_provider.embed(query)
  -> VectorRetriever.search()
  -> LexicalRetriever.search()
  -> ResultFusion.merge()
  -> SearchResult[]
  -> AnswerService
```

For Milvus vector search:

- Search more than the final `top_k` when possible, such as `top_k * 3`, so fusion has enough candidates.
- Apply Milvus scalar filters for `knowledge_space_id` and optional `document_ids`.
- Return stable chunk identifiers so missing metadata can be rehydrated from PostgreSQL.

## Error Handling

- Milvus collection is created automatically if missing.
- Embedding dimension mismatch raises a clear error that instructs the operator to rebuild the index or use a matching embedding configuration.
- Milvus connection, upsert, delete, and search failures are surfaced as task or request errors.
- `SEARCH_BACKEND=milvus` does not silently downgrade to memory.
- Delete and reindex operations remove stale vectors before writing replacements.
- Unsupported `SEARCH_BACKEND`, `VECTOR_BACKEND`, or `LEXICAL_BACKEND` values raise explicit `ValueError`s.

## Docker Compose

Add Milvus standalone to `docker-compose.yml` with persistent volume and host access on port `19530`.

The compose stack should support:

```bash
docker compose up -d postgres redis opensearch minio temporal temporal-ui milvus
```

Host-run API/worker examples should include:

```bash
SEARCH_BACKEND=milvus
MILVUS_URI=http://localhost:19530
```

OpenSearch remains in compose for compatibility and future `hybrid` mode.

## Dependencies

Add the official Milvus Python client:

```toml
pymilvus
```

Keep tests independent of a running Milvus instance by injecting fake clients or small adapter protocols.

## Testing Plan

### Unit Tests

- `build_search_backend` accepts `memory`, `opensearch`, `milvus`, and `hybrid`.
- Invalid retrieval configuration fails with clear messages.
- `MilvusVectorRetriever` creates a collection when missing.
- `MilvusVectorRetriever` upserts searchable chunks and skips parent chunks.
- `MilvusVectorRetriever` deletes by `document_id`.
- `MilvusVectorRetriever` searches with `knowledge_space_id` and optional `document_ids` filters.
- Dimension mismatch raises a clear error.
- `ResultFusion` merges lexical and vector candidates by `chunk_id`, preserves citation fields, and sorts by final score.
- Existing OpenSearch and memory tests keep passing.

### Integration/Manual Verification

- Start compose middleware including Milvus.
- Run API and worker with `SEARCH_BACKEND=milvus`.
- Import a document.
- Confirm the import completes only after vectors are queryable.
- Ask a question and confirm citations are returned.
- Reindex or delete a document and confirm stale vectors are removed.

## Documentation Updates

Update:

- `README.md`
- `docs/01-architecture-overview.md`
- `docs/03-ingestion-retrieval-and-answering.md`
- `docs/06-deployment-and-operations.md`
- `docs/09-data-flow.md`

Documentation should explain:

- Milvus replaces vector retrieval, not PostgreSQL.
- OpenSearch remains available for lexical search and future hybrid retrieval.
- `SEARCH_BACKEND=milvus` requires embeddings and a running Milvus service.
- Switching embedding models requires reindexing because stored vectors must match the query embedding space.

## Acceptance Criteria

- `SEARCH_BACKEND=milvus` can be configured and constructed.
- `SEARCH_BACKEND=hybrid` can be configured as OpenSearch lexical retrieval plus Milvus vector retrieval.
- Milvus collection creation, upsert, search, and delete are covered by tests without requiring a live Milvus service.
- Docker Compose includes a Milvus service suitable for local联调.
- Existing `memory` and `opensearch` paths remain available.
- Query responses still include citations through the existing `SearchResult` and answer contracts.
- Import/reindex jobs do not report `completed` until Milvus indexing succeeds when Milvus is selected.
