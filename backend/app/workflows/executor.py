from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.documents import SourceImportRequest
from app.schemas.evals import EvalRunRequest
from app.services.container import UnconfiguredWorkflowOrchestrator, build_container


@dataclass(slots=True)
class WorkflowJobExecutor:
    settings: Settings
    session_factory: object
    container: object = field(init=False)

    def __post_init__(self) -> None:
        self.container = build_container(
            self.settings,
            orchestrator=UnconfiguredWorkflowOrchestrator(mode="workflow-runtime"),
        )

    def execute_ingestion_job(self, job_id: str, request_payload: dict) -> None:
        request = SourceImportRequest.model_validate(request_payload)
        with self.session_factory() as db:
            self.container.ingestion_service.execute_import_job(db, job_id, request)

    def execute_reindex_job(self, job_id: str, document_id: str) -> None:
        with self.session_factory() as db:
            self.container.ingestion_service.execute_reindex_job(db, job_id, document_id)

    def fail_ingestion_job(self, job_id: str, error_message: str) -> None:
        with self.session_factory() as db:
            self.container.ingestion_service.mark_job_failed(db, job_id, error_message)

    def cancel_ingestion_job(self, job_id: str, error_message: str) -> None:
        with self.session_factory() as db:
            self.container.ingestion_service.mark_job_cancelled(db, job_id, error_message)

    def execute_eval_run(self, run_id: str, request_payload: dict) -> None:
        request = EvalRunRequest.model_validate(request_payload)
        with self.session_factory() as db:
            self._sync_memory_index(db)
            self.container.evaluation_service.execute_run(db, run_id, request)

    def fail_eval_run(self, run_id: str, error_message: str) -> None:
        with self.session_factory() as db:
            self.container.evaluation_service.mark_run_failed(db, run_id, error_message)

    def cancel_eval_run(self, run_id: str, error_message: str) -> None:
        with self.session_factory() as db:
            self.container.evaluation_service.mark_run_cancelled(db, run_id, error_message)

    def _sync_memory_index(self, db: Session) -> None:
        if self.container.search_backend.backend_name == "memory-hybrid":
            self.container.bootstrap_index(db)
