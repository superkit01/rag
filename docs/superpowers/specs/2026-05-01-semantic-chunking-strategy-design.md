# Semantic Chunking Strategy Design

## Goal

Add a configurable semantic document chunking strategy for the RAG backend. The strategy should use embedding similarity over sliding windows to choose better chunk boundaries than fixed-size splitting, while preserving the existing ingestion, indexing, retrieval, and citation contracts.

The strategy is enabled with:

```bash
CHUNKING_STRATEGY=semantic
```

It reuses the existing `EmbeddingProvider`:

- `EMBEDDING_BACKEND=hash` gives deterministic local/test behavior.
- `EMBEDDING_BACKEND=openai` gives real OpenAI-compatible semantic similarity.

## Non-Goals

- Do not introduce new database fields.
- Do not introduce parent/child chunk relationships.
- Do not change frontend citation rendering.
- Do not silently downgrade semantic chunking if embedding calls fail during chunking.

## Current Context

The backend already has a strategy framework:

- `ChunkingStrategy` and `PreparedChunk` in `backend/app/services/chunking_strategies/base.py`
- `FixedSizeStrategy`
- `ParentChildStrategy`
- `ChunkingStrategyFactory`

Ingestion persists all `PreparedChunk` records, then generates embeddings and indexes chunks whose `chunk_type` is searchable. The semantic strategy should output regular searchable chunks:

- `chunk_type="fixed"`
- `parent_id=None`
- `fragment_id="semantic-0001"` style IDs

This keeps the rest of the RAG flow unchanged.

## Recommended Approach

Use sliding-window embedding similarity.

The strategy first splits each parsed section into semantic units such as sentences, list items, and short paragraphs. It then groups nearby units into overlapping windows, embeds each window, and detects low-similarity transitions between adjacent windows. Candidate transition points become chunk boundaries, subject to a max-size guard.

This was chosen over simple adjacent-sentence comparison because enterprise docs often contain short bullets and fragments. Window-level embeddings reduce noise and better capture local topic shifts.

## Algorithm

### 1. Build Semantic Units

For each `ParsedSection`:

1. Normalize whitespace only for the emitted content.
2. Split section content into ordered units using:
   - Markdown-like list item boundaries
   - Chinese sentence punctuation: `。！？；`
   - English sentence punctuation: `.?!;`
   - Paragraph boundaries when present before normalization
3. Track each unit's start and end offsets relative to the normalized section text.
4. Drop empty units.

Short units are not discarded. They remain available to window construction and chunk assembly.

### 2. Build Sliding Windows

Create windows by accumulating consecutive semantic units until their combined length is near `SLIDING_WINDOW_SIZE`.

Configuration:

- `SLIDING_WINDOW_SIZE`: target window size in characters, default `300`
- `SLIDING_OVERLAP_RATIO`: overlap between windows, default `0.3`
- Effective overlap is clamped to `[0.0, 0.9)`

Each window records:

- text
- first unit index
- last unit index
- approximate boundary unit index for transitions

If a section is too short to form two windows, skip similarity analysis and assemble chunks by max size.

### 3. Embed Windows

Call the configured `EmbeddingProvider.embed_many()` once per section for all windows.

If the provider raises or returns a mismatched count, semantic chunking fails. This should fail the import/reindex job and record the error, because a silent fallback would make `CHUNKING_STRATEGY=semantic` misleading.

### 4. Detect Semantic Boundaries

For each adjacent window pair:

1. Compute cosine similarity between their embeddings.
2. If similarity is below `SEMANTIC_SIMILARITY_THRESHOLD`, create a candidate break near the boundary between those windows.
3. Merge nearby duplicate candidate breaks.

Configuration:

- `SEMANTIC_SIMILARITY_THRESHOLD`: default `0.75`

### 5. Assemble Chunks

Walk semantic units in order and emit a chunk when either condition is met:

- The current unit index reaches a semantic boundary.
- The current chunk would exceed `SEMANTIC_CHUNK_MAX_SIZE`.

Configuration:

- `SEMANTIC_CHUNK_MAX_SIZE`: default `500`

When max-size splitting is required, prefer the nearest unit boundary. If a single unit exceeds the max size, split it with the existing fixed-size splitter as a safety fallback.

Output chunks:

- `fragment_id="semantic-0001"`, `semantic-0002`, continuing with the same zero-padded sequence
- `section_title`, `heading_path`, `page_number` inherited from the section
- `start_offset`, `end_offset` from normalized section offsets
- `token_count` from `estimate_token_count`
- `chunk_type="fixed"`
- `parent_id=None`

## Integration

### New Module

Add:

```text
backend/app/services/chunking_strategies/semantic.py
```

Class:

```python
class SemanticStrategy(ChunkingStrategy):
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        max_chunk_size: int = 500,
        similarity_threshold: float = 0.75,
        window_size: int = 300,
        overlap_ratio: float = 0.3,
    ) -> None:
        # Store normalized configuration and the embedding provider.
```

The implementation should avoid importing heavyweight app containers. If type imports create cycles, use `typing.Protocol` locally for the embedding provider shape.

### Factory

Update `ChunkingStrategyFactory.create` to accept:

```python
create(settings: Settings, embedding_provider: EmbeddingProvider | None = None)
```

Behavior:

- `fixed-size`: unchanged
- `parent-child`: unchanged
- `semantic`: requires an embedding provider
- unknown strategy: fall back to `FixedSizeStrategy`, matching current behavior
- semantic selected without embedding provider: log a clear error and fall back to `FixedSizeStrategy`

### Container

`ServiceContainer` already builds `embedding_provider` before `chunker`. Pass it to the factory:

```python
self.chunker = ChunkingStrategyFactory.create(settings, self.embedding_provider)
```

### Exports

Update `backend/app/services/chunking_strategies/__init__.py` to export `SemanticStrategy`.

### Documentation

Update:

- `.env.example`: mention `CHUNKING_STRATEGY=semantic`
- `README.md`: document that semantic chunking calls the embedding provider during import/reindex and may increase cost in `openai` mode

## Failure Handling

- Embedding errors during semantic chunking should fail the import/reindex job.
- Empty sections are skipped.
- Sections with no useful semantic units produce no chunks.
- Sections with one useful unit produce one chunk unless the unit exceeds max size.
- Invalid overlap values are clamped.
- Non-positive max/window sizes are normalized to safe minimums.

## Testing Plan

### Unit Tests

Add tests in `backend/tests/test_chunking_strategies.py`:

- `SemanticStrategy` splits a multi-topic section into multiple `semantic-*` chunks when window similarity drops below threshold.
- High-similarity long text still splits by `SEMANTIC_CHUNK_MAX_SIZE`.
- Short text produces one chunk.
- Output chunks use `chunk_type="fixed"` and `parent_id=None`.
- Factory creates `SemanticStrategy` when `CHUNKING_STRATEGY=semantic` and an embedding provider is supplied.
- Factory falls back to `FixedSizeStrategy` when semantic is selected without an embedding provider.

Use deterministic fake embedding providers in unit tests rather than relying on network or model behavior.

### Integration Test

Add or extend an ingestion integration test:

- Configure `CHUNKING_STRATEGY=semantic`
- Use `EMBEDDING_BACKEND=hash`
- Import a markdown document
- Verify chunks are persisted, embeddings are non-empty, memory search can retrieve them, and answer citations still work

### Regression Tests

Run:

```bash
SEARCH_BACKEND=memory EMBEDDING_BACKEND=hash backend/.venv/bin/python -m pytest backend/tests -v
```

## Acceptance Criteria

- `CHUNKING_STRATEGY=semantic` imports documents successfully with `hash` embedding.
- Semantic chunks are searchable and answer citations work without frontend changes.
- `fixed-size` and `parent-child` behavior remains unchanged.
- Embedding failures during semantic chunking fail the job visibly.
- Full backend test suite passes.
