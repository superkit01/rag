from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Protocol

from temporalio.client import Client

from app.core.config import Settings
from app.workflows.executor import WorkflowJobExecutor


class WorkflowOrchestrator(Protocol):
    mode: str

    async def connect(self) -> None:
        ...

    async def shutdown(self) -> None:
        ...

    async def start_ingestion_job(self, job_id: str, workflow_id: str, request_payload: dict) -> None:
        ...

    async def start_reindex_job(self, job_id: str, workflow_id: str, document_id: str) -> None:
        ...

    async def start_eval_run(self, run_id: str, workflow_id: str, request_payload: dict) -> None:
        ...

    async def cancel_workflow(self, workflow_id: str) -> None:
        ...


@dataclass(slots=True)
class ImmediateWorkflowOrchestrator:
    settings: Settings
    session_factory: object
    mode: str = "immediate"
    executor: WorkflowJobExecutor = field(init=False)

    def __post_init__(self) -> None:
        self.executor = WorkflowJobExecutor(self.settings, self.session_factory)

    async def connect(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None

    async def start_ingestion_job(self, job_id: str, workflow_id: str, request_payload: dict) -> None:
        try:
            await asyncio.to_thread(self.executor.execute_ingestion_job, job_id, request_payload)
        except Exception:
            return None

    async def start_reindex_job(self, job_id: str, workflow_id: str, document_id: str) -> None:
        try:
            await asyncio.to_thread(self.executor.execute_reindex_job, job_id, document_id)
        except Exception:
            return None

    async def start_eval_run(self, run_id: str, workflow_id: str, request_payload: dict) -> None:
        try:
            await asyncio.to_thread(self.executor.execute_eval_run, run_id, request_payload)
        except Exception:
            return None

    async def cancel_workflow(self, workflow_id: str) -> None:
        return None


@dataclass(slots=True)
class TemporalWorkflowOrchestrator:
    settings: Settings
    mode: str = "temporal"
    client: Client | None = field(default=None, init=False)

    async def connect(self) -> None:
        if self.client is not None:
            return
        self.client = await connect_temporal_client(self.settings)

    async def shutdown(self) -> None:
        self.client = None

    async def start_ingestion_job(self, job_id: str, workflow_id: str, request_payload: dict) -> None:
        from app.workflows.definitions import ImportWorkflow

        client = self._require_client()
        await client.start_workflow(
            ImportWorkflow.run,
            {"job_id": job_id, "request": request_payload},
            id=workflow_id,
            task_queue=self.settings.temporal_task_queue,
        )

    async def start_reindex_job(self, job_id: str, workflow_id: str, document_id: str) -> None:
        from app.workflows.definitions import ReindexWorkflow

        client = self._require_client()
        await client.start_workflow(
            ReindexWorkflow.run,
            {"job_id": job_id, "document_id": document_id},
            id=workflow_id,
            task_queue=self.settings.temporal_task_queue,
        )

    async def start_eval_run(self, run_id: str, workflow_id: str, request_payload: dict) -> None:
        from app.workflows.definitions import EvalWorkflow

        client = self._require_client()
        await client.start_workflow(
            EvalWorkflow.run,
            {"run_id": run_id, "request": request_payload},
            id=workflow_id,
            task_queue=self.settings.temporal_task_queue,
        )

    async def cancel_workflow(self, workflow_id: str) -> None:
        client = self._require_client()
        handle = client.get_workflow_handle(workflow_id)
        await handle.cancel()

    def _require_client(self) -> Client:
        if self.client is None:
            raise RuntimeError("Temporal client is not connected.")
        return self.client


def build_workflow_orchestrator(settings: Settings, session_factory: object) -> WorkflowOrchestrator:
    if settings.workflow_backend == "immediate":
        return ImmediateWorkflowOrchestrator(settings=settings, session_factory=session_factory)
    return TemporalWorkflowOrchestrator(settings=settings)


async def connect_temporal_client(settings: Settings) -> Client:
    last_error: Exception | None = None
    for attempt in range(1, settings.temporal_connect_retries + 1):
        try:
            return await Client.connect(
                settings.temporal_host,
                namespace=settings.temporal_namespace,
            )
        except Exception as exc:  # pragma: no cover - depends on live Temporal timing
            last_error = exc
            if attempt >= settings.temporal_connect_retries:
                break
            await asyncio.sleep(settings.temporal_connect_delay_seconds)
    assert last_error is not None
    raise last_error
