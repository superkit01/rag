import base64
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


class RecordingAnswerProvider:
    def __init__(self) -> None:
        self.generate_calls = []
        self.stream_calls = []
        self.rewrite_calls = []
        self.title_calls = []

    def generate(self, question, evidence, history=None):
        self.generate_calls.append((question, evidence, history or []))
        return f"回答: {question}"

    def stream_generate(self, question, evidence, history=None):
        self.stream_calls.append((question, evidence, history or []))
        yield f"流式回答: {question}"

    def rewrite_query(self, question, history):
        self.rewrite_calls.append((question, history))
        if history:
            return " ".join([turn.question for turn in history] + [question])
        return question

    def generate_session_title(self, question, answer):
        self.title_calls.append((question, answer))
        return "核心数据上线要求"


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


def install_recording_answer_provider(client: TestClient) -> RecordingAnswerProvider:
    provider = RecordingAnswerProvider()
    client.app.state.container.answer_provider = provider
    client.app.state.container.answer_service.answer_provider = provider
    return provider


def encoded_text_payload(content: str) -> str:
    return base64.b64encode(content.encode("utf-8")).decode("ascii")


def seed_document(client: TestClient, tmp_path: Path) -> tuple[str, str]:
    del tmp_path
    content = "# 研发管理办法\n\n## 变更控制\n涉及核心数据的上线必须具备回滚预案、发布窗口审批和测试准入。"
    spaces = client.get("/api/knowledge-spaces")
    knowledge_space_id = spaces.json()[0]["id"]
    imported = client.post(
        "/api/sources/import",
        json={
            "title": "研发管理办法.md",
            "knowledge_space_id": knowledge_space_id,
            "uploaded_file_name": "研发管理办法.md",
            "uploaded_file_base64": encoded_text_payload(content),
        },
    )
    body = imported.json()
    return knowledge_space_id, body["document"]["id"]


def import_uploaded_markdown(client: TestClient, knowledge_space_id: str, title: str, content: str):
    return client.post(
        "/api/sources/import",
        json={
            "title": title,
            "knowledge_space_id": knowledge_space_id,
            "uploaded_file_name": title,
            "uploaded_file_base64": encoded_text_payload(content),
        },
    )


def test_import_and_fragment_lookup(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        knowledge_space_id, document_id = seed_document(client, tmp_path)
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
        _, document_id = seed_document(client, tmp_path)
        deleted = client.delete(f"/api/documents/{document_id}")
        assert deleted.status_code == 200
        assert deleted.json()["id"] == document_id

        missing = client.get(f"/api/documents/{document_id}")
        assert missing.status_code == 404


def test_source_path_import_is_rejected(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        spaces = client.get("/api/knowledge-spaces")
        knowledge_space_id = spaces.json()[0]["id"]
        response = client.post(
            "/api/sources/import",
            json={
                "title": "流程规范.md",
                "knowledge_space_id": knowledge_space_id,
                "source_path": str(tmp_path / "docs" / "流程规范.md"),
            },
        )
        assert response.status_code == 422
        assert "uploaded_file_base64" in response.text


def test_inline_content_import_is_rejected(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        spaces = client.get("/api/knowledge-spaces")
        knowledge_space_id = spaces.json()[0]["id"]
        response = client.post(
            "/api/sources/import",
            json={
                "title": "内联制度.md",
                "knowledge_space_id": knowledge_space_id,
                "inline_content": "# 内联制度\n\n## 门禁\n未完成审批不得发布。",
                "source_type": "markdown",
            },
        )

        assert response.status_code == 422
        assert "uploaded_file_base64" in response.text


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
        assert document.json()["source_uri"] == "上传制度.md"
        assert document.json()["storage_uri"].startswith("s3://rag-documents/uploads/")
        assert "测试准入" in document.json()["chunks"][0]["content"]
        stored_path = tmp_path / "object-storage" / document.json()["storage_uri"].replace("s3://", "", 1)
        assert stored_path.exists()


def test_storage_uri_import_is_rejected(tmp_path: Path) -> None:
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
        assert response.status_code == 422
        assert "uploaded_file_base64" in response.text


def test_failed_import_retry_reuses_uploaded_payload(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        spaces = client.get("/api/knowledge-spaces")
        knowledge_space_id = spaces.json()[0]["id"]
        first = client.post(
            "/api/sources/import",
            json={
                "title": "补录制度.md",
                "knowledge_space_id": knowledge_space_id,
                "uploaded_file_name": "补录制度.md",
                "uploaded_file_base64": "not-valid-base64",
            },
        )
        assert first.status_code == 202
        failed = first.json()
        assert failed["ingestion_job"]["status"] == "failed"
        assert failed["ingestion_job"]["attempt_count"] == 1

        retried = client.post(f"/api/sources/jobs/{failed['ingestion_job']['id']}/retry")
        assert retried.status_code == 202
        payload = retried.json()
        assert payload["ingestion_job"]["status"] == "failed"
        assert payload["ingestion_job"]["attempt_count"] == 2


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
                "uploaded_file_name": "待取消制度.md",
                "uploaded_file_base64": encoded_text_payload("# 待取消制度\n\n## 门禁\n未完成审批不得发布。"),
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
        knowledge_space_id, document_id = seed_document(client, tmp_path)

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
        knowledge_space_id, _ = seed_document(client, tmp_path)
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
        knowledge_space_id, _ = seed_document(client, tmp_path)
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


def test_session_title_is_refined_after_first_answer(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        knowledge_space_id, _ = seed_document(client, tmp_path)
        provider = install_recording_answer_provider(client)
        session = client.post(
            "/api/sessions",
            json={"knowledge_space_id": knowledge_space_id, "name": "新对话"},
        ).json()

        response = client.post(
            "/api/queries/answer",
            json={
                "knowledge_space_id": knowledge_space_id,
                "session_id": session["id"],
                "question": "核心数据上线需要哪些前置条件？",
            },
        )

        assert response.status_code == 200
        refreshed = client.get(f"/api/sessions/{session['id']}")
        assert refreshed.status_code == 200
        assert refreshed.json()["name"] == "核心数据上线要求"
        assert provider.title_calls == [("核心数据上线需要哪些前置条件？", "回答: 核心数据上线需要哪些前置条件？")]


def test_session_history_is_used_for_followup_answer(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        knowledge_space_id, _ = seed_document(client, tmp_path)
        provider = install_recording_answer_provider(client)
        session = client.post(
            "/api/sessions",
            json={"knowledge_space_id": knowledge_space_id, "name": "新对话"},
        ).json()

        first = client.post(
            "/api/queries/answer",
            json={
                "knowledge_space_id": knowledge_space_id,
                "session_id": session["id"],
                "question": "核心数据上线需要哪些前置条件？",
            },
        )
        assert first.status_code == 200

        second = client.post(
            "/api/queries/answer",
            json={
                "knowledge_space_id": knowledge_space_id,
                "session_id": session["id"],
                "question": "继续说一下风险",
            },
        )
        assert second.status_code == 200

        _, _, second_history = provider.generate_calls[-1]
        assert [turn.question for turn in second_history] == ["核心数据上线需要哪些前置条件？"]
        assert [turn.answer for turn in second_history] == ["回答: 核心数据上线需要哪些前置条件？"]
        rewrite_question, rewrite_history = provider.rewrite_calls[-1]
        assert rewrite_question == "继续说一下风险"
        assert [turn.question for turn in rewrite_history] == ["核心数据上线需要哪些前置条件？"]


def test_custom_session_title_is_not_overwritten(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        knowledge_space_id, _ = seed_document(client, tmp_path)
        provider = install_recording_answer_provider(client)
        session = client.post(
            "/api/sessions",
            json={"knowledge_space_id": knowledge_space_id, "name": "我的专题研究"},
        ).json()

        response = client.post(
            "/api/queries/answer",
            json={
                "knowledge_space_id": knowledge_space_id,
                "session_id": session["id"],
                "question": "核心数据上线需要哪些前置条件？",
            },
        )

        assert response.status_code == 200
        refreshed = client.get(f"/api/sessions/{session['id']}")
        assert refreshed.json()["name"] == "我的专题研究"
        assert provider.title_calls == []


def test_answer_rejects_unknown_session(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        knowledge_space_id, _ = seed_document(client, tmp_path)
        response = client.post(
            "/api/queries/answer",
            json={
                "knowledge_space_id": knowledge_space_id,
                "session_id": "00000000-0000-0000-0000-000000000000",
                "question": "核心数据上线需要哪些前置条件？",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Session not found"


def test_answer_rejects_cross_space_session(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        knowledge_space_id, _ = seed_document(client, tmp_path)
        other_space = client.post(
            "/api/knowledge-spaces",
            json={"name": "另一个空间", "description": "用于跨空间校验"},
        ).json()
        session = client.post(
            "/api/sessions",
            json={"knowledge_space_id": other_space["id"], "name": "新对话"},
        ).json()

        response = client.post(
            "/api/queries/answer",
            json={
                "knowledge_space_id": knowledge_space_id,
                "session_id": session["id"],
                "question": "核心数据上线需要哪些前置条件？",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Session does not belong to the selected knowledge space."


def test_streaming_answer_refines_session_title(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        knowledge_space_id, _ = seed_document(client, tmp_path)
        provider = install_recording_answer_provider(client)
        session = client.post(
            "/api/sessions",
            json={"knowledge_space_id": knowledge_space_id, "name": "新对话"},
        ).json()

        with client.stream(
            "POST",
            "/api/queries/answer/stream",
            json={
                "knowledge_space_id": knowledge_space_id,
                "session_id": session["id"],
                "question": "核心数据上线需要哪些前置条件？",
            },
        ) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())

        refreshed = client.get(f"/api/sessions/{session['id']}")
        assert "event: done" in body
        assert "answer_trace_id" in body
        assert refreshed.json()["name"] == "核心数据上线要求"
        assert provider.title_calls == [("核心数据上线需要哪些前置条件？", "流式回答: 核心数据上线需要哪些前置条件？")]


def test_eval_run_reports_metrics(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        knowledge_space_id, document_id = seed_document(client, tmp_path)
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
