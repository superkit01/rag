from __future__ import annotations

from app.core.config import Settings
from app.services.chunking import HierarchicalChunker, PreparedChunk
from app.services.chunking_factory import ChunkingStrategyFactory
from app.services.chunking_strategies import ChunkingStrategy, FixedSizeStrategy, ParentChildStrategy, SemanticStrategy
from app.services.parser import ParsedSection


class MockChunkingStrategy(ChunkingStrategy):
    def chunk_sections(self, sections: list[ParsedSection]) -> list[PreparedChunk]:
        return [
            PreparedChunk(
                fragment_id="test-frag-001",
                section_title="Test Section",
                heading_path=["Test"],
                page_number=1,
                start_offset=0,
                end_offset=10,
                token_count=5,
                content="Test content",
            )
        ]


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


def test_chunking_strategy_interface() -> None:
    strategy = MockChunkingStrategy()

    result = strategy.chunk_sections([])

    assert len(result) == 1
    assert result[0].fragment_id == "test-frag-001"
    assert result[0].chunk_type == "fixed"


def test_prepared_chunk_defaults() -> None:
    chunk = PreparedChunk(
        fragment_id="frag-001",
        section_title="Section",
        heading_path=["A", "B"],
        page_number=5,
        start_offset=0,
        end_offset=100,
        token_count=50,
        content="Content here",
    )

    assert chunk.chunk_type == "fixed"
    assert chunk.parent_id is None


def test_hierarchical_chunker_aliases_fixed_size_strategy() -> None:
    assert HierarchicalChunker is FixedSizeStrategy


def test_fixed_size_short_text_not_split() -> None:
    strategy = FixedSizeStrategy(chunk_size=700, chunk_overlap=100)
    sections = [ParsedSection(title="Test", heading_path=["Test"], page_number=1, content="短文本不需要切割")]

    chunks = strategy.chunk_sections(sections)

    assert len(chunks) == 1
    assert chunks[0].chunk_type == "fixed"
    assert chunks[0].parent_id is None


def test_fixed_size_long_text_is_split() -> None:
    strategy = FixedSizeStrategy(chunk_size=100, chunk_overlap=20)
    sections = [ParsedSection(title="Test", heading_path=["Test"], page_number=1, content="这是一段很长的文本。" * 20)]

    chunks = strategy.chunk_sections(sections)

    assert len(chunks) > 1
    assert {chunk.chunk_type for chunk in chunks} == {"fixed"}
    assert all(chunk.parent_id is None for chunk in chunks)


def test_parent_child_strategy_creates_parent_and_child_relationships() -> None:
    strategy = ParentChildStrategy(
        parent_chunk_size=120,
        parent_chunk_overlap=20,
        child_chunk_size=50,
        child_chunk_overlap=10,
    )
    content = "核心数据上线必须完成测试准入、发布窗口审批和回滚预案确认。" * 8
    sections = [ParsedSection(title="变更控制", heading_path=["研发管理办法", "变更控制"], page_number=3, content=content)]

    chunks = strategy.chunk_sections(sections)

    parents = [chunk for chunk in chunks if chunk.chunk_type == "parent"]
    children = [chunk for chunk in chunks if chunk.chunk_type == "child"]
    parent_ids = {parent.fragment_id for parent in parents}
    assert parents
    assert children
    assert all(child.parent_id in parent_ids for child in children)
    assert all(child.content in {parent.content for parent in parents if parent.fragment_id == child.parent_id}.pop() for child in children)
    assert all(child.page_number == 3 for child in children)


def test_semantic_strategy_splits_at_low_similarity_window_boundary() -> None:
    strategy = SemanticStrategy(
        FakeSemanticEmbeddingProvider(),
        max_chunk_size=500,
        similarity_threshold=0.5,
        window_size=35,
        overlap_ratio=0.0,
    )
    content = "财务预算需要按季度复核。发票归档必须完整。系统发布前要完成测试。回滚方案需要提前确认。"
    sections = [ParsedSection(title="制度", heading_path=["制度"], page_number=2, content=content)]

    chunks = strategy.chunk_sections(sections)

    assert len(chunks) >= 2
    assert chunks[0].fragment_id == "semantic-0001"
    assert chunks[1].fragment_id == "semantic-0002"
    assert "财务" in chunks[0].content
    assert "回滚" in chunks[-1].content
    assert all(chunk.chunk_type == "fixed" for chunk in chunks)
    assert all(chunk.parent_id is None for chunk in chunks)
    assert all(chunk.page_number == 2 for chunk in chunks)


def test_semantic_strategy_splits_high_similarity_text_by_max_size() -> None:
    strategy = SemanticStrategy(
        FakeSemanticEmbeddingProvider(),
        max_chunk_size=45,
        similarity_threshold=0.1,
        window_size=80,
        overlap_ratio=0.0,
    )
    content = "发布制度要求发布前完成测试准入和回滚确认。" * 8
    sections = [ParsedSection(title="发布制度", heading_path=["制度", "发布"], page_number=2, content=content)]

    chunks = strategy.chunk_sections(sections)

    assert len(chunks) > 1
    assert all(len(chunk.content) <= 70 for chunk in chunks)
    assert all(chunk.fragment_id.startswith("semantic-") for chunk in chunks)


def test_semantic_strategy_keeps_short_text_as_single_chunk() -> None:
    strategy = SemanticStrategy(
        FakeSemanticEmbeddingProvider(),
        max_chunk_size=500,
        similarity_threshold=0.5,
        window_size=300,
        overlap_ratio=0.3,
    )
    content = "发布前需要测试准入。"
    sections = [ParsedSection(title="发布制度", heading_path=["制度", "发布"], page_number=2, content=content)]

    chunks = strategy.chunk_sections(sections)

    assert len(chunks) == 1
    assert chunks[0].fragment_id == "semantic-0001"
    assert chunks[0].content == content
    assert chunks[0].chunk_type == "fixed"
    assert chunks[0].parent_id is None


def test_chunking_factory_creates_configured_strategy() -> None:
    fixed = ChunkingStrategyFactory.create(Settings(chunking_strategy="fixed-size", chunk_size=123, chunk_overlap=12))
    parent_child = ChunkingStrategyFactory.create(
        Settings(
            chunking_strategy="parent-child",
            parent_chunk_size=456,
            parent_chunk_overlap=45,
            child_chunk_size=78,
            child_chunk_overlap=7,
        )
    )

    assert isinstance(fixed, FixedSizeStrategy)
    assert isinstance(parent_child, ParentChildStrategy)


def test_chunking_factory_falls_back_to_fixed_size_for_unknown_strategy() -> None:
    strategy = ChunkingStrategyFactory.create(Settings(chunking_strategy="unknown"))

    assert isinstance(strategy, FixedSizeStrategy)
