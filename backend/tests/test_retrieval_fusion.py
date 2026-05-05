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
