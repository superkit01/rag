# Semantic Chunking Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `CHUNKING_STRATEGY=semantic`, using sliding-window embedding similarity to choose chunk boundaries while preserving existing ingestion, indexing, retrieval, and citation contracts.

**Architecture:** Implement a focused `SemanticStrategy` in the existing `chunking_strategies` package. The strategy splits parsed sections into semantic units, embeds overlapping windows with the existing `EmbeddingProvider`, turns low-similarity transitions into chunk boundaries, and emits normal searchable chunks with `chunk_type="fixed"`. The factory and service container pass the configured embedding provider into this strategy.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, pytest, existing `EmbeddingProvider` protocol, existing chunking strategy framework.

---

## File Structure

```text
backend/app/services/chunking_strategies/
├── __init__.py        # Export SemanticStrategy
├── base.py            # Existing PreparedChunk and ChunkingStrategy
├── fixed_size.py      # Existing safety fallback for oversized units
├── parent_child.py    # Existing parent-child strategy, unchanged
└── semantic.py        # New sliding-window embedding strategy

backend/app/services/
├── chunking_factory.py  # Add semantic factory branch and embedding_provider argument
└── container.py         # Pass embedding_provider to ChunkingStrategyFactory

backend/tests/
├── test_chunking_strategies.py       # Add semantic unit/factory tests
└── test_semantic_chunking_integration.py  # New ingestion/query integration test

.env.example  # Document semantic option and embedding cost
README.md     # Document semantic chunking behavior
```

## Task 1: Add SemanticStrategy Unit Tests First

**Files:**
- Modify: `backend/tests/test_chunking_strategies.py`

- [ ] **Step 1: Add imports for semantic tests**

At the top of `backend/tests/test_chunking_strategies.py`, change the existing imports to include `SemanticStrategy`.

```python
from app.services.chunking_strategies import ChunkingStrategy, FixedSizeStrategy, ParentChildStrategy, SemanticStrategy
```

- [ ] **Step 2: Add deterministic fake embedding provider**

Add this helper class near `MockChunkingStrategy`:

```python
class FakeSemanticEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in texts:
            if "财务" in text or "预算" in text or "发票" in text:
                embeddings.append([1.0, 0.0, 0.0])
            elif "发布" in text or "回滚" in text or "测试" in text:
                embeddings.append([0.0, 1.0, 0.0])
            else:
                embeddings.append([0.0, 0.0, 1.0])
        return embeddings
```

- [ ] **Step 3: Add failing test for semantic topic boundary splitting**

Add this test:

```python
def test_semantic_strategy_splits_at_low_similarity_window_boundary() -> None:
    strategy = SemanticStrategy(
        embedding_provider=FakeSemanticEmbeddingProvider(),
        max_chunk_size=500,
        similarity_threshold=0.5,
        window_size=35,
        overlap_ratio=0.0,
    )
    sections = [
        ParsedSection(
            title="混合制度",
            heading_path=["混合制度"],
            page_number=2,
            content=(
                "财务预算需要月度复核。发票归档需要双人检查。"
                "系统发布必须完成测试准入。回滚预案需要提前演练。"
            ),
        )
    ]

    chunks = strategy.chunk_sections(sections)

    assert len(chunks) >= 2
    assert chunks[0].fragment_id == "semantic-0001"
    assert chunks[1].fragment_id == "semantic-0002"
    assert "财务" in chunks[0].content
    assert "回滚" in chunks[-1].content
    assert all(chunk.chunk_type == "fixed" for chunk in chunks)
    assert all(chunk.parent_id is None for chunk in chunks)
    assert all(chunk.page_number == 2 for chunk in chunks)
```

- [ ] **Step 4: Add failing test for max chunk size guard**

Add this test:

```python
def test_semantic_strategy_splits_high_similarity_text_by_max_size() -> None:
    strategy = SemanticStrategy(
        embedding_provider=FakeSemanticEmbeddingProvider(),
        max_chunk_size=45,
        similarity_threshold=0.1,
        window_size=80,
        overlap_ratio=0.0,
    )
    sections = [
        ParsedSection(
            title="发布制度",
            heading_path=["发布制度"],
            page_number=None,
            content="系统发布必须完成测试准入。回滚预案需要提前演练。发布窗口需要审批确认。" * 3,
        )
    ]

    chunks = strategy.chunk_sections(sections)

    assert len(chunks) > 1
    assert all(len(chunk.content) <= 70 for chunk in chunks)
    assert all(chunk.fragment_id.startswith("semantic-") for chunk in chunks)
```

- [ ] **Step 5: Add failing test for short text**

Add this test:

```python
def test_semantic_strategy_keeps_short_text_as_single_chunk() -> None:
    strategy = SemanticStrategy(
        embedding_provider=FakeSemanticEmbeddingProvider(),
        max_chunk_size=500,
        similarity_threshold=0.5,
        window_size=300,
        overlap_ratio=0.3,
    )
    sections = [ParsedSection(title="短制度", heading_path=["短制度"], page_number=None, content="发布前需要测试准入。")]

    chunks = strategy.chunk_sections(sections)

    assert len(chunks) == 1
    assert chunks[0].fragment_id == "semantic-0001"
    assert chunks[0].content == "发布前需要测试准入。"
    assert chunks[0].chunk_type == "fixed"
    assert chunks[0].parent_id is None
```

- [ ] **Step 6: Run tests to verify semantic imports fail**

Run:

```bash
SEARCH_BACKEND=memory EMBEDDING_BACKEND=hash backend/.venv/bin/python -m pytest backend/tests/test_chunking_strategies.py -v
```

Expected: fail during import with `ImportError` or `NameError` because `SemanticStrategy` does not exist yet.

- [ ] **Step 7: Commit failing tests**

```bash
git add backend/tests/test_chunking_strategies.py
git commit -m "test: add semantic chunking strategy expectations"
```

## Task 2: Implement SemanticStrategy

**Files:**
- Create: `backend/app/services/chunking_strategies/semantic.py`
- Modify: `backend/app/services/chunking_strategies/__init__.py`

- [ ] **Step 1: Create semantic.py with implementation**

Create `backend/app/services/chunking_strategies/semantic.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

from app.services.chunking_strategies.base import ChunkingStrategy, PreparedChunk
from app.services.chunking_strategies.fixed_size import FixedSizeStrategy
from app.services.indexing import cosine_similarity
from app.services.parser import ParsedSection
from app.services.text_utils import estimate_token_count, normalize_whitespace


class EmbeddingProviderLike(Protocol):
    def embed_many(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


@dataclass(slots=True)
class SemanticUnit:
    content: str
    start_offset: int
    end_offset: int


@dataclass(slots=True)
class SemanticWindow:
    text: str
    first_unit_index: int
    last_unit_index: int


class SemanticStrategy(ChunkingStrategy):
    def __init__(
        self,
        embedding_provider: EmbeddingProviderLike,
        max_chunk_size: int = 500,
        similarity_threshold: float = 0.75,
        window_size: int = 300,
        overlap_ratio: float = 0.3,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.max_chunk_size = max(20, max_chunk_size)
        self.similarity_threshold = similarity_threshold
        self.window_size = max(20, window_size)
        self.overlap_ratio = min(0.89, max(0.0, overlap_ratio))
        self.unit_fallback = FixedSizeStrategy(self.max_chunk_size, 0)

    def chunk_sections(self, sections: list[ParsedSection]) -> list[PreparedChunk]:
        prepared: list[PreparedChunk] = []
        counter = 1
        for section in sections:
            text = normalize_whitespace(section.content)
            if not text:
                continue
            units = self._split_units(text)
            if not units:
                continue
            boundaries = self._semantic_boundaries(units)
            for start, end, content in self._assemble_chunks(units, boundaries):
                prepared.append(
                    PreparedChunk(
                        fragment_id=f"semantic-{counter:04d}",
                        section_title=section.title,
                        heading_path=section.heading_path,
                        page_number=section.page_number,
                        start_offset=start,
                        end_offset=end,
                        token_count=estimate_token_count(content),
                        content=content,
                        chunk_type="fixed",
                        parent_id=None,
                    )
                )
                counter += 1
        return prepared

    def _split_units(self, text: str) -> list[SemanticUnit]:
        pattern = re.compile(r".+?(?:[。！？；.!?;]+|$)")
        units: list[SemanticUnit] = []
        for match in pattern.finditer(text):
            content = match.group(0).strip()
            if not content:
                continue
            units.append(SemanticUnit(content=content, start_offset=match.start(), end_offset=match.end()))
        return units

    def _semantic_boundaries(self, units: list[SemanticUnit]) -> set[int]:
        windows = self._build_windows(units)
        if len(windows) < 2:
            return set()
        embeddings = self.embedding_provider.embed_many([window.text for window in windows])
        if len(embeddings) != len(windows):
            raise ValueError("Embedding provider returned a different number of vectors than semantic windows.")
        boundaries: set[int] = set()
        for index in range(len(windows) - 1):
            similarity = cosine_similarity(embeddings[index], embeddings[index + 1])
            if similarity < self.similarity_threshold:
                boundary = windows[index + 1].first_unit_index
                if 0 < boundary < len(units):
                    boundaries.add(boundary)
        return boundaries

    def _build_windows(self, units: list[SemanticUnit]) -> list[SemanticWindow]:
        windows: list[SemanticWindow] = []
        start = 0
        step_size = max(1, int(self.window_size * (1.0 - self.overlap_ratio)))
        while start < len(units):
            end = start
            length = 0
            while end < len(units) and (length < self.window_size or end == start):
                length += len(units[end].content)
                end += 1
            text = normalize_whitespace(" ".join(unit.content for unit in units[start:end]))
            if text:
                windows.append(SemanticWindow(text=text, first_unit_index=start, last_unit_index=end - 1))
            if end >= len(units):
                break
            next_start = start
            consumed = 0
            while next_start < len(units) and consumed < step_size:
                consumed += len(units[next_start].content)
                next_start += 1
            start = max(next_start, start + 1)
        return windows

    def _assemble_chunks(self, units: list[SemanticUnit], boundaries: set[int]) -> list[tuple[int, int, str]]:
        chunks: list[tuple[int, int, str]] = []
        current: list[SemanticUnit] = []
        current_length = 0

        def flush() -> None:
            if not current:
                return
            content = normalize_whitespace(" ".join(unit.content for unit in current))
            if content:
                chunks.append((current[0].start_offset, current[-1].end_offset, content))
            current.clear()

        for index, unit in enumerate(units):
            if current and index in boundaries:
                flush()
                current_length = 0

            if len(unit.content) > self.max_chunk_size:
                if current:
                    flush()
                    current_length = 0
                chunks.extend(self.unit_fallback._split_text(unit.content))
                continue

            would_exceed = current and current_length + len(unit.content) > self.max_chunk_size
            if would_exceed:
                flush()
                current_length = 0

            current.append(unit)
            current_length += len(unit.content)

        flush()
        return chunks
```

- [ ] **Step 2: Fix oversized-unit offset bug in the initial implementation**

In `_assemble_chunks`, replace:

```python
chunks.extend(self.unit_fallback._split_text(unit.content))
```

with:

```python
for start, end, snippet in self.unit_fallback._split_text(unit.content):
    chunks.append((unit.start_offset + start, unit.start_offset + end, snippet))
```

- [ ] **Step 3: Export SemanticStrategy**

Update `backend/app/services/chunking_strategies/__init__.py`:

```python
from app.services.chunking_strategies.base import ChunkingStrategy, PreparedChunk
from app.services.chunking_strategies.fixed_size import FixedSizeStrategy
from app.services.chunking_strategies.parent_child import ParentChildStrategy
from app.services.chunking_strategies.semantic import SemanticStrategy

__all__ = ["ChunkingStrategy", "FixedSizeStrategy", "ParentChildStrategy", "PreparedChunk", "SemanticStrategy"]
```

- [ ] **Step 4: Run semantic unit tests**

Run:

```bash
SEARCH_BACKEND=memory EMBEDDING_BACKEND=hash backend/.venv/bin/python -m pytest backend/tests/test_chunking_strategies.py -v
```

Expected: semantic implementation tests pass except factory tests that have not been added yet.

- [ ] **Step 5: Commit implementation**

```bash
git add backend/app/services/chunking_strategies/semantic.py backend/app/services/chunking_strategies/__init__.py
git commit -m "feat: add semantic chunking strategy"
```

## Task 3: Wire SemanticStrategy Into Factory and Container

**Files:**
- Modify: `backend/app/services/chunking_factory.py`
- Modify: `backend/app/services/container.py`
- Modify: `backend/tests/test_chunking_strategies.py`

- [ ] **Step 1: Add factory tests**

Add these tests to `backend/tests/test_chunking_strategies.py`:

```python
def test_chunking_factory_creates_semantic_strategy_with_embedding_provider() -> None:
    strategy = ChunkingStrategyFactory.create(
        Settings(chunking_strategy="semantic"),
        embedding_provider=FakeSemanticEmbeddingProvider(),
    )

    assert isinstance(strategy, SemanticStrategy)


def test_chunking_factory_falls_back_for_semantic_without_embedding_provider() -> None:
    strategy = ChunkingStrategyFactory.create(Settings(chunking_strategy="semantic"))

    assert isinstance(strategy, FixedSizeStrategy)
```

- [ ] **Step 2: Run factory tests and verify they fail**

Run:

```bash
SEARCH_BACKEND=memory EMBEDDING_BACKEND=hash backend/.venv/bin/python -m pytest backend/tests/test_chunking_strategies.py::test_chunking_factory_creates_semantic_strategy_with_embedding_provider backend/tests/test_chunking_strategies.py::test_chunking_factory_falls_back_for_semantic_without_embedding_provider -v
```

Expected: fail because `ChunkingStrategyFactory.create()` does not yet accept `embedding_provider`.

- [ ] **Step 3: Update chunking_factory.py**

Replace `backend/app/services/chunking_factory.py` with:

```python
from __future__ import annotations

import logging

from app.core.config import Settings
from app.services.chunking_strategies import ChunkingStrategy, FixedSizeStrategy, ParentChildStrategy, SemanticStrategy

logger = logging.getLogger(__name__)


class ChunkingStrategyFactory:
    @staticmethod
    def create(settings: Settings, embedding_provider: object | None = None) -> ChunkingStrategy:
        try:
            if settings.chunking_strategy == "fixed-size":
                return FixedSizeStrategy(settings.chunk_size, settings.chunk_overlap)
            if settings.chunking_strategy == "parent-child":
                return ParentChildStrategy(
                    parent_chunk_size=settings.parent_chunk_size,
                    parent_chunk_overlap=settings.parent_chunk_overlap,
                    child_chunk_size=settings.child_chunk_size,
                    child_chunk_overlap=settings.child_chunk_overlap,
                )
            if settings.chunking_strategy == "semantic":
                if embedding_provider is None:
                    raise ValueError("Semantic chunking requires an embedding provider.")
                return SemanticStrategy(
                    embedding_provider=embedding_provider,
                    max_chunk_size=settings.semantic_chunk_max_size,
                    similarity_threshold=settings.semantic_similarity_threshold,
                    window_size=settings.sliding_window_size,
                    overlap_ratio=settings.sliding_overlap_ratio,
                )
            raise ValueError(f"Unknown chunking strategy: {settings.chunking_strategy}")
        except Exception:
            logger.exception("Failed to create chunking strategy; falling back to fixed-size.")
            return FixedSizeStrategy(settings.chunk_size, settings.chunk_overlap)
```

- [ ] **Step 4: Update container.py**

In `backend/app/services/container.py`, replace:

```python
self.chunker = ChunkingStrategyFactory.create(settings)
```

with:

```python
self.chunker = ChunkingStrategyFactory.create(settings, self.embedding_provider)
```

- [ ] **Step 5: Run chunking strategy tests**

Run:

```bash
SEARCH_BACKEND=memory EMBEDDING_BACKEND=hash backend/.venv/bin/python -m pytest backend/tests/test_chunking_strategies.py -v
```

Expected: all tests in this file pass.

- [ ] **Step 6: Commit factory integration**

```bash
git add backend/app/services/chunking_factory.py backend/app/services/container.py backend/tests/test_chunking_strategies.py
git commit -m "feat: wire semantic chunking strategy"
```

## Task 4: Add Semantic Ingestion Integration Test

**Files:**
- Create: `backend/tests/test_semantic_chunking_integration.py`

- [ ] **Step 1: Add integration test file**

Create `backend/tests/test_semantic_chunking_integration.py`:

```python
from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.entities import Chunk


def encoded_text_payload(content: str) -> str:
    return base64.b64encode(content.encode("utf-8")).decode("ascii")


def make_semantic_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        object_storage_local_root=str(tmp_path / "object-storage"),
        object_storage_backend="local",
        workflow_backend="immediate",
        search_backend="memory",
        embedding_backend="hash",
        chunking_strategy="semantic",
        semantic_chunk_max_size=120,
        semantic_similarity_threshold=0.2,
        sliding_window_size=80,
        sliding_overlap_ratio=0.0,
    )
    return TestClient(create_app(settings))


def test_semantic_import_indexes_chunks_and_answers_with_citations(tmp_path: Path) -> None:
    with make_semantic_client(tmp_path) as client:
        knowledge_space_id = client.get("/api/knowledge-spaces").json()[0]["id"]
        content = (
            "# 管控制度\n\n"
            "## 财务管理\n"
            "财务预算需要月度复核。发票归档需要双人检查。费用报销需要审批记录。\n\n"
            "## 发布管理\n"
            "核心系统发布必须完成测试准入。回滚预案需要提前演练。发布窗口需要审批确认。"
        )
        imported = client.post(
            "/api/sources/import",
            json={
                "title": "管控制度.md",
                "knowledge_space_id": knowledge_space_id,
                "uploaded_file_name": "管控制度.md",
                "uploaded_file_base64": encoded_text_payload(content),
            },
        )
        assert imported.status_code == 202
        document_id = imported.json()["document"]["id"]
        chunks = imported.json()["document"]["chunks"]

        assert chunks
        assert all(chunk["fragment_id"].startswith("semantic-") for chunk in chunks)
        assert all(chunk["chunk_type"] == "fixed" for chunk in chunks)
        assert all(chunk["parent_id"] is None for chunk in chunks)

        with client.app.state.session_factory() as db:
            stored_chunks = db.query(Chunk).filter(Chunk.document_id == document_id).all()
            assert stored_chunks
            assert all(chunk.embedding for chunk in stored_chunks)

        response = client.post(
            "/api/queries/answer",
            json={
                "knowledge_space_id": knowledge_space_id,
                "question": "核心系统发布需要哪些前置条件？",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["citations"]
        assert body["source_documents"]
        assert body["confidence"] > 0
```

- [ ] **Step 2: Run integration test**

Run:

```bash
SEARCH_BACKEND=memory EMBEDDING_BACKEND=hash backend/.venv/bin/python -m pytest backend/tests/test_semantic_chunking_integration.py -v
```

Expected: pass.

- [ ] **Step 3: Commit integration test**

```bash
git add backend/tests/test_semantic_chunking_integration.py
git commit -m "test: cover semantic chunking ingestion flow"
```

## Task 5: Update Documentation and Configuration Examples

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Update .env.example**

In `.env.example`, update the chunking strategy comment:

```bash
# 可切换：fixed-size 使用固定窗口；parent-child 使用小块检索、大块生成；semantic 使用滑动窗口 embedding 相似度切分
CHUNKING_STRATEGY=fixed-size
```

Keep the existing semantic and sliding config entries:

```bash
SEMANTIC_CHUNK_MAX_SIZE=500
SEMANTIC_SIMILARITY_THRESHOLD=0.75
SEMANTIC_EMBEDDING_MODEL=text-embedding-3-small
SLIDING_WINDOW_SIZE=300
SLIDING_OVERLAP_RATIO=0.3
SLIDING_MERGE_THRESHOLD=0.8
```

- [ ] **Step 2: Update README.md**

In the document chunking bullet under "设计说明", replace the existing strategy text with:

```markdown
- 文档切割支持 `CHUNKING_STRATEGY=fixed-size`、`CHUNKING_STRATEGY=parent-child` 与 `CHUNKING_STRATEGY=semantic`：
  - `fixed-size` 保持原有固定窗口行为，使用 `CHUNK_SIZE` 和 `CHUNK_OVERLAP`。
  - `parent-child` 会同时生成 `parent` 和 `child` chunks；系统只对 `child` 生成 embedding 并写入搜索索引，回答时再批量加载对应 `parent` 内容作为生成上下文和引用来源。
  - `semantic` 使用滑动窗口 embedding 相似度寻找语义边界，输出普通可检索 chunks；它会在导入/重建索引阶段额外调用 embedding provider，`EMBEDDING_BACKEND=openai` 时会增加模型调用成本。
  - 切换策略后，建议对历史文档执行重建索引。
```

- [ ] **Step 3: Commit documentation**

```bash
git add .env.example README.md
git commit -m "docs: document semantic chunking configuration"
```

## Task 6: Full Verification

**Files:**
- Verify all changed files.

- [ ] **Step 1: Run full backend test suite**

Run:

```bash
SEARCH_BACKEND=memory EMBEDDING_BACKEND=hash backend/.venv/bin/python -m pytest backend/tests -v
```

Expected: all tests pass.

- [ ] **Step 2: Inspect git status**

Run:

```bash
git status --short --branch
```

Expected: clean working tree on the implementation branch.

- [ ] **Step 3: Review recent commits**

Run:

```bash
git log --oneline --max-count=8
```

Expected: commits for semantic tests, implementation, wiring, integration test, and docs are present.

- [ ] **Step 4: Stop and use finishing workflow**

Invoke `superpowers:finishing-a-development-branch` and follow its options. Do not merge, push, or delete branches before that workflow asks for the user's choice.

## Self-Review

- Spec coverage: Tasks cover `SemanticStrategy`, sliding-window embedding boundaries, factory/container integration, docs, failure behavior, unit tests, integration tests, and full regression verification.
- Placeholder scan: no deferred implementation sections are intentionally left blank.
- Type consistency: plan consistently uses `SemanticStrategy`, `EmbeddingProviderLike`, `SemanticUnit`, `SemanticWindow`, and `ChunkingStrategyFactory.create(settings, embedding_provider=None)`.
