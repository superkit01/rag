from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.entities import Chunk


def encoded_text_payload(content: str) -> str:
    return base64.b64encode(content.encode("utf-8")).decode("ascii")


def make_parent_child_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        object_storage_local_root=str(tmp_path / "object-storage"),
        object_storage_backend="local",
        workflow_backend="immediate",
        search_backend="memory",
        embedding_backend="hash",
        chunking_strategy="parent-child",
        parent_chunk_size=120,
        parent_chunk_overlap=20,
        child_chunk_size=50,
        child_chunk_overlap=10,
    )
    return TestClient(create_app(settings))


def test_parent_child_import_indexes_only_children_and_uses_parent_context(tmp_path: Path) -> None:
    with make_parent_child_client(tmp_path) as client:
        knowledge_space_id = client.get("/api/knowledge-spaces").json()[0]["id"]
        content = "# 研发管理办法\n\n## 变更控制\n" + "核心数据上线必须完成测试准入、发布窗口审批和回滚预案确认。" * 8
        imported = client.post(
            "/api/sources/import",
            json={
                "title": "研发管理办法.md",
                "knowledge_space_id": knowledge_space_id,
                "uploaded_file_name": "研发管理办法.md",
                "uploaded_file_base64": encoded_text_payload(content),
            },
        )
        assert imported.status_code == 202
        document_id = imported.json()["document"]["id"]

        chunks = imported.json()["document"]["chunks"]
        parents = [chunk for chunk in chunks if chunk["chunk_type"] == "parent"]
        children = [chunk for chunk in chunks if chunk["chunk_type"] == "child"]
        assert parents
        assert children
        assert all(child["parent_id"] for child in children)

        backend_chunks = client.app.state.container.orchestrator.executor.container.search_backend._chunks
        assert backend_chunks
        assert {chunk.chunk_type for chunk in backend_chunks.values()} == {"child"}

        with client.app.state.session_factory() as db:
            stored_parents = db.query(Chunk).filter(Chunk.document_id == document_id, Chunk.chunk_type == "parent").all()
            stored_children = db.query(Chunk).filter(Chunk.document_id == document_id, Chunk.chunk_type == "child").all()
            assert stored_parents
            assert stored_children
            assert all(parent.embedding == [] for parent in stored_parents)
            assert all(child.embedding for child in stored_children)

        response = client.post(
            "/api/queries/answer",
            json={
                "knowledge_space_id": knowledge_space_id,
                "question": "核心数据上线需要哪些前置条件？",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["citations"]
        assert body["citations"][0]["fragment_id"].startswith("parent-")
        assert len(body["citations"][0]["quote"]) >= len(children[0]["content"])
