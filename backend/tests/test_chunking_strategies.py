from __future__ import annotations

from app.core.config import Settings
from app.services.chunking import HierarchicalChunker, PreparedChunk
from app.services.chunking_factory import ChunkingStrategyFactory
from app.services.chunking_strategies import ChunkingStrategy, FixedSizeStrategy, ParentChildStrategy
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
