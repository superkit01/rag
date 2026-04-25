from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


class DeferredWorkflowOrchestrator:
    def __init__(self) -> None:
        self.mode = "deferred-test"
        self.cancelled_workflows: list[str] = []

    async def connect(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None

    async def start_ingestion_job(self, job_id: str, workflow_id: str, request_payload: dict) -> None:
        return None

    async def start_reindex_job(self, job_id: str, workflow_id: str, document_id: str) -> None:
        return None

    async def start_eval_run(self, run_id: str, workflow_id: str, request_payload: dict) -> None:
        return None

    async def cancel_workflow(self, workflow_id: str) -> None:
        self.cancelled_workflows.append(workflow_id)


def make_client(tmp_path: Path, orchestrator: object | None = None) -> TestClient:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        object_storage_local_root=str(tmp_path / "object-storage"),
        object_storage_backend="local",
        workflow_backend="immediate",
    )
    app = create_app(settings)
    if orchestrator is not None:
        app.state.container.orchestrator = orchestrator
    return TestClient(app)


def seed_document(client: TestClient) -> tuple[str, str]:
    spaces = client.get("/api/knowledge-spaces")
    knowledge_space_id = spaces.json()[0]["id"]
    imported = client.post(
        "/api/sources/import",
        json={
            "title": "研发管理办法.md",
            "knowledge_space_id": knowledge_space_id,
            "inline_content": "# 研发管理办法\n\n## 变更控制\n涉及核心数据的上线必须具备回滚预案、发布窗口审批和测试准入。",
            "source_type": "markdown",
        },
    )
    body = imported.json()
    return knowledge_space_id, body["document"]["id"]


def test_import_and_fragment_lookup(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        knowledge_space_id, document_id = seed_document(client)
        response = client.get(f"/api/documents/{document_id}")
        assert response.status_code == 200
        document = response.json()
        assert document["knowledge_space_id"] == knowledge_space_id
        assert len(document["chunks"]) >= 1

        fragment_id = document["chunks"][0]["fragment_id"]
        fragment = client.get(f"/api/documents/{document_id}/fragments/{fragment_id}")
        assert fragment.status_code == 200
        assert "回滚预案" in fragment.json()["content"]


def test_document_can_be_deleted(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        _, document_id = seed_document(client)
        deleted = client.delete(f"/api/documents/{document_id}")
        assert deleted.status_code == 200
        assert deleted.json()["id"] == document_id

        missing = client.get(f"/api/documents/{document_id}")
        assert missing.status_code == 404


def test_import_from_local_source_path(tmp_path: Path) -> None:
    source_path = tmp_path / "docs" / "流程规范.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        "# 流程规范\n\n## 发布门禁\n发布前需要完成测试准入和窗口审批。",
        encoding="utf-8",
    )

    with make_client(tmp_path) as client:
        spaces = client.get("/api/knowledge-spaces")
        knowledge_space_id = spaces.json()[0]["id"]
        response = client.post(
            "/api/sources/import",
            json={
                "title": "流程规范.md",
                "knowledge_space_id": knowledge_space_id,
                "source_path": str(source_path),
            },
        )
        assert response.status_code == 202
        payload = response.json()
        assert payload["document"]["title"] == "流程规范.md"

        document = client.get(f"/api/documents/{payload['document']['id']}")
        assert document.status_code == 200
        assert document.json()["source_uri"] == str(source_path)
        assert "测试准入" in document.json()["chunks"][0]["content"]


def test_import_from_uploaded_local_file_payload(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        spaces = client.get("/api/knowledge-spaces")
        knowledge_space_id = spaces.json()[0]["id"]
        response = client.post(
            "/api/sources/import",
            json={
                "title": "上传制度.md",
                "knowledge_space_id": knowledge_space_id,
                "uploaded_file_name": "上传制度.md",
                "uploaded_file_base64": "IyDkuIrkvKDliLbluqYKCiMjIOmXqOemgQrlj5HluIPliY3pnIDopoHlrIzmiJDmtYvor5Xlh4blhaXjgIHnqpfnj6PlrqHmibnlh4blgIfnpLrjgII=",
            },
        )
        assert response.status_code == 202
        payload = response.json()

        document = client.get(f"/api/documents/{payload['document']['id']}")
        assert document.status_code == 200
        assert document.json()["source_uri"] == "upload://上传制度.md"
        assert document.json()["storage_uri"].startswith("s3://rag-documents/uploads/")
        assert "测试准入" in document.json()["chunks"][0]["content"]
        stored_path = tmp_path / "object-storage" / document.json()["storage_uri"].replace("s3://", "", 1)
        assert stored_path.exists()


def test_import_from_storage_uri_mapping(tmp_path: Path) -> None:
    storage_path = tmp_path / "object-storage" / "rag-documents" / "policies" / "架构评审制度.md"
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_text(
        "# 架构评审制度\n\n## 风险治理\n高风险模块必须保留架构评审记录。",
        encoding="utf-8",
    )

    with make_client(tmp_path) as client:
        spaces = client.get("/api/knowledge-spaces")
        knowledge_space_id = spaces.json()[0]["id"]
        response = client.post(
            "/api/sources/import",
            json={
                "title": "架构评审制度.md",
                "knowledge_space_id": knowledge_space_id,
                "storage_uri": "s3://rag-documents/policies/架构评审制度.md",
            },
        )
        assert response.status_code == 202
        payload = response.json()

        document = client.get(f"/api/documents/{payload['document']['id']}")
        assert document.status_code == 200
        assert document.json()["storage_uri"] == "s3://rag-documents/policies/架构评审制度.md"
        assert "架构评审记录" in document.json()["chunks"][0]["content"]


def test_failed_import_can_retry_after_source_becomes_available(tmp_path: Path) -> None:
    source_path = tmp_path / "late" / "补录制度.md"

    with make_client(tmp_path) as client:
        spaces = client.get("/api/knowledge-spaces")
        knowledge_space_id = spaces.json()[0]["id"]
        first = client.post(
            "/api/sources/import",
            json={
                "title": "补录制度.md",
                "knowledge_space_id": knowledge_space_id,
                "source_path": str(source_path),
            },
        )
        assert first.status_code == 202
        failed = first.json()
        assert failed["ingestion_job"]["status"] == "failed"
        assert failed["ingestion_job"]["attempt_count"] == 1

        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("# 补录制度\n\n## 要求\n补录后需要重新索引。", encoding="utf-8")

        retried = client.post(f"/api/sources/jobs/{failed['ingestion_job']['id']}/retry")
        assert retried.status_code == 202
        payload = retried.json()
        assert payload["ingestion_job"]["status"] == "completed"
        assert payload["ingestion_job"]["attempt_count"] == 2
        assert payload["document"]["title"] == "补录制度.md"


def test_pending_import_job_can_be_cancelled(tmp_path: Path) -> None:
    orchestrator = DeferredWorkflowOrchestrator()

    with make_client(tmp_path, orchestrator=orchestrator) as client:
        spaces = client.get("/api/knowledge-spaces")
        knowledge_space_id = spaces.json()[0]["id"]
        response = client.post(
            "/api/sources/import",
            json={
                "title": "待取消制度.md",
                "knowledge_space_id": knowledge_space_id,
                "inline_content": "# 待取消制度\n\n## 门禁\n未完成审批不得发布。",
                "source_type": "markdown",
            },
        )
        assert response.status_code == 202
        payload = response.json()
        assert payload["ingestion_job"]["status"] == "pending"
        assert payload["ingestion_job"]["job_kind"] == "import"
        assert payload["ingestion_job"]["attempt_count"] == 1
        assert payload["ingestion_job"]["workflow_id"]

        cancelled = client.post(f"/api/sources/jobs/{payload['ingestion_job']['id']}/cancel")
        assert cancelled.status_code == 202
        cancelled_payload = cancelled.json()
        assert cancelled_payload["ingestion_job"]["status"] == "cancelling"
        assert orchestrator.cancelled_workflows == [payload["ingestion_job"]["workflow_id"]]


def test_pending_eval_run_can_be_cancelled(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        knowledge_space_id, document_id = seed_document(client)

    orchestrator = DeferredWorkflowOrchestrator()

    with make_client(tmp_path, orchestrator=orchestrator) as client:
        response = client.post(
            "/api/eval/runs",
            json={
                "knowledge_space_id": knowledge_space_id,
                "cases": [
                    {
                        "name": "待取消评测",
                        "question": "核心数据上线需要满足什么要求？",
                        "expected_document_ids": [document_id],
                        "expected_snippets": ["回滚预案"],
                    }
                ],
            },
        )
        assert response.status_code == 202
        payload = response.json()
        assert payload["status"] == "pending"
        assert payload["attempt_count"] == 1
        assert payload["workflow_id"]

        cancelled = client.post(f"/api/eval/runs/{payload['id']}/cancel")
        assert cancelled.status_code == 202
        cancelled_payload = cancelled.json()
        assert cancelled_payload["status"] == "cancelling"
        assert orchestrator.cancelled_workflows == [payload["workflow_id"]]


def test_grounded_answer_flow(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        knowledge_space_id, _ = seed_document(client)
        response = client.post(
            "/api/queries/answer",
            json={
                "knowledge_space_id": knowledge_space_id,
                "question": "核心数据上线需要哪些前置条件？",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["answer_trace_id"]
        assert payload["citations"]
        assert payload["source_documents"]
        assert payload["confidence"] > 0

        feedback = client.post(
            "/api/feedback",
            json={
                "answer_trace_id": payload["answer_trace_id"],
                "rating": 5,
                "issue_type": "grounded",
                "comments": "引用完整，适合作为研究底稿。",
            },
        )
        assert feedback.status_code == 201
        feedback_payload = feedback.json()
        assert feedback_payload["rating"] == 5
        assert feedback_payload["answer_trace_id"] == payload["answer_trace_id"]


def test_grounded_answer_stream(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        knowledge_space_id, _ = seed_document(client)
        with client.stream(
            "POST",
            "/api/queries/answer/stream",
            json={
                "knowledge_space_id": knowledge_space_id,
                "question": "核心数据上线需要哪些前置条件？",
            },
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())

        assert "event: meta" in body
        assert "event: delta" in body
        assert "event: done" in body
        assert "answer_trace_id" in body


def test_eval_run_reports_metrics(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        knowledge_space_id, document_id = seed_document(client)
        response = client.post(
            "/api/eval/runs",
            json={
                "knowledge_space_id": knowledge_space_id,
                "cases": [
                    {
                        "name": "变更控制命中",
                        "question": "核心数据上线需要满足什么要求？",
                        "expected_document_ids": [document_id],
                        "expected_snippets": ["回滚预案"],
                    }
                ],
            },
        )
        assert response.status_code == 202
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["summary"]["document_recall"] == 1.0
        assert payload["completed_cases"] == 1

        listed = client.get(f"/api/eval/runs?knowledge_space_id={knowledge_space_id}")
        assert listed.status_code == 200
        listed_payload = listed.json()
        assert len(listed_payload) == 1
        assert listed_payload[0]["id"] == payload["id"]

        detail = client.get(f"/api/eval/runs/{payload['id']}")
        assert detail.status_code == 200
        assert detail.json()["results"][0]["hit"] is True
