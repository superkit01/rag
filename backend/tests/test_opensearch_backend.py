from __future__ import annotations

import httpx

from app.services.indexing import IndexedChunk, OpenSearchSearchBackend
from app.services.llm import HashEmbeddingProvider


def test_opensearch_backend_indexes_and_reranks() -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "HEAD" and request.url.path == "/rag_chunks":
            return httpx.Response(404)
        if request.method == "PUT" and request.url.path == "/rag_chunks":
            return httpx.Response(200, json={"acknowledged": True})
        if request.method == "POST" and request.url.path == "/_bulk":
            return httpx.Response(200, json={"errors": False, "items": []})
        if request.method == "POST" and request.url.path == "/rag_chunks/_search":
            return httpx.Response(
                200,
                json={
                    "hits": {
                        "hits": [
                            {
                                "_score": 6.0,
                                "_source": {
                                    "chunk_id": "chunk-1",
                                    "knowledge_space_id": "space-1",
                                    "document_id": "doc-1",
                                    "document_title": "发布管理规范.md",
                                    "fragment_id": "frag-1",
                                    "section_title": "发布前检查",
                                    "heading_path": ["发布管理规范", "发布前检查"],
                                    "heading_path_terms": "发 布 发布 前 检 检查",
                                    "page_number": None,
                                    "content": "核心数据变更必须完成测试准入和回滚预案确认。",
                                    "embedding": [0.2, 0.1, 0.3, 0.4],
                                },
                            },
                            {
                                "_score": 3.0,
                                "_source": {
                                    "chunk_id": "chunk-2",
                                    "knowledge_space_id": "space-1",
                                    "document_id": "doc-2",
                                    "document_title": "架构评审制度.md",
                                    "fragment_id": "frag-2",
                                    "section_title": "风险治理",
                                    "heading_path": ["架构评审制度", "风险治理"],
                                    "heading_path_terms": "架 构 构评 评审 审制 制度 风 险 风险 治 理 治理",
                                    "page_number": None,
                                    "content": "高风险模块必须保留架构评审记录。",
                                    "embedding": [0.01, 0.02, 0.03, 0.04],
                                },
                            },
                        ]
                    }
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    backend = OpenSearchSearchBackend(
        HashEmbeddingProvider(dimensions=4),
        base_url="http://opensearch:9200",
        index_name="rag_chunks",
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://opensearch:9200"),
    )

    backend.upsert_chunks(
        [
            IndexedChunk(
                chunk_id="chunk-1",
                knowledge_space_id="space-1",
                document_id="doc-1",
                document_title="发布管理规范.md",
                fragment_id="frag-1",
                section_title="发布前检查",
                heading_path=["发布管理规范", "发布前检查"],
                page_number=None,
                content="核心数据变更必须完成测试准入和回滚预案确认。",
                embedding=[0.2, 0.1, 0.3, 0.4],
            )
        ]
    )
    results = backend.search("核心数据变更需要哪些前置条件？", "space-1", None, 5)

    assert calls[:3] == [("HEAD", "/rag_chunks"), ("PUT", "/rag_chunks"), ("POST", "/_bulk")]
    assert results
    assert results[0].document_id == "doc-1"
    assert results[0].score >= results[0].semantic_score
