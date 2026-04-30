from __future__ import annotations

import time

from app.services.chunking_strategies import FixedSizeStrategy, ParentChildStrategy
from app.services.parser import ParsedSection


def test_parent_child_chunking_50000_chars_under_two_seconds() -> None:
    content = "核心数据上线必须完成测试准入、发布窗口审批和回滚预案确认。" * 1000
    sections = [ParsedSection(title="变更控制", heading_path=["研发管理办法", "变更控制"], content=content)]
    strategy = ParentChildStrategy()

    start = time.perf_counter()
    chunks = strategy.chunk_sections(sections)
    elapsed = time.perf_counter() - start

    assert chunks
    assert elapsed < 2.0


def test_parent_child_storage_overhead_is_tracked_against_fixed_size() -> None:
    content = "核心数据上线必须完成测试准入、发布窗口审批和回滚预案确认。" * 300
    sections = [ParsedSection(title="变更控制", heading_path=["研发管理办法", "变更控制"], content=content)]

    fixed_chunks = FixedSizeStrategy().chunk_sections(sections)
    parent_child_chunks = ParentChildStrategy().chunk_sections(sections)

    assert fixed_chunks
    assert parent_child_chunks
    assert len(parent_child_chunks) / len(fixed_chunks) < 6.0
