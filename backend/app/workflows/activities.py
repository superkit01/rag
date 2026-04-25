from __future__ import annotations

from temporalio import activity

from app.core.config import get_settings
from app.db.session import build_session_factory
from app.workflows.executor import WorkflowJobExecutor


_activity_executor: WorkflowJobExecutor | None = None


def get_activity_executor() -> WorkflowJobExecutor:
    global _activity_executor
    if _activity_executor is None:
        settings = get_settings()
        session_factory = build_session_factory(settings)
        _activity_executor = WorkflowJobExecutor(settings=settings, session_factory=session_factory)
    return _activity_executor


@activity.defn
def run_import_activity(payload: dict) -> dict:
    executor = get_activity_executor()
    executor.execute_ingestion_job(payload["job_id"], payload["request"])
    return {"job_id": payload["job_id"]}


@activity.defn
def mark_import_failed_activity(payload: dict) -> dict:
    executor = get_activity_executor()
    executor.fail_ingestion_job(payload["job_id"], payload["error_message"])
    return {"job_id": payload["job_id"]}


@activity.defn
def mark_import_cancelled_activity(payload: dict) -> dict:
    executor = get_activity_executor()
    executor.cancel_ingestion_job(payload["job_id"], payload["error_message"])
    return {"job_id": payload["job_id"]}


@activity.defn
def run_reindex_activity(payload: dict) -> dict:
    executor = get_activity_executor()
    executor.execute_reindex_job(payload["job_id"], payload["document_id"])
    return {"job_id": payload["job_id"], "document_id": payload["document_id"]}


@activity.defn
def mark_reindex_failed_activity(payload: dict) -> dict:
    executor = get_activity_executor()
    executor.fail_ingestion_job(payload["job_id"], payload["error_message"])
    return {"job_id": payload["job_id"]}


@activity.defn
def mark_reindex_cancelled_activity(payload: dict) -> dict:
    executor = get_activity_executor()
    executor.cancel_ingestion_job(payload["job_id"], payload["error_message"])
    return {"job_id": payload["job_id"]}


@activity.defn
def run_eval_activity(payload: dict) -> dict:
    executor = get_activity_executor()
    executor.execute_eval_run(payload["run_id"], payload["request"])
    return {"run_id": payload["run_id"]}


@activity.defn
def mark_eval_failed_activity(payload: dict) -> dict:
    executor = get_activity_executor()
    executor.fail_eval_run(payload["run_id"], payload["error_message"])
    return {"run_id": payload["run_id"]}


@activity.defn
def mark_eval_cancelled_activity(payload: dict) -> dict:
    executor = get_activity_executor()
    executor.cancel_eval_run(payload["run_id"], payload["error_message"])
    return {"run_id": payload["run_id"]}
