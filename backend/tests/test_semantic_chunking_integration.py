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


def test_semantic_import_persists_embeddings_and_answers_with_citations(tmp_path: Path) -> None:
    with make_semantic_client(tmp_path) as client:
        knowledge_space_id = client.get("/api/knowledge-spaces").json()[0]["id"]
        content = (
            "# 企业运营手册\n\n"
            "## 财务管理\n"
            "预算复核需要财务负责人确认，月度报销必须保留发票、合同和付款记录。"
            "资金计划按季度滚动更新，并在经营会议中同步风险敞口。\n\n"
            "## 核心系统发布\n"
            "核心系统发布前必须完成测试准入、发布窗口审批和回滚预案确认。"
            "发布负责人还需要确认监控告警、值班安排和业务方验收记录。"
            "缺少任一前置条件时，发布任务必须延期并重新评审。"
        )

        imported = client.post(
            "/api/sources/import",
            json={
                "title": "企业运营手册.md",
                "knowledge_space_id": knowledge_space_id,
                "uploaded_file_name": "企业运营手册.md",
                "uploaded_file_base64": encoded_text_payload(content),
            },
        )

        assert imported.status_code == 202
        document = imported.json()["document"]
        document_id = document["id"]
        chunks = document["chunks"]
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
