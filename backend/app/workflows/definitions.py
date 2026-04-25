from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import CancelledError

with workflow.unsafe.imports_passed_through():
    from app.workflows.activities import (
        mark_eval_failed_activity,
        mark_eval_cancelled_activity,
        mark_import_failed_activity,
        mark_import_cancelled_activity,
        mark_reindex_failed_activity,
        mark_reindex_cancelled_activity,
        run_eval_activity,
        run_import_activity,
        run_reindex_activity,
    )


def _retry_policy() -> RetryPolicy:
    return RetryPolicy(maximum_attempts=3)


@workflow.defn
class ImportWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        try:
            return await workflow.execute_activity(
                run_import_activity,
                payload,
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=_retry_policy(),
            )
        except CancelledError:
            await workflow.execute_activity(
                mark_import_cancelled_activity,
                {"job_id": payload["job_id"], "error_message": "Workflow cancellation requested."},
                start_to_close_timeout=timedelta(minutes=1),
            )
            raise
        except Exception as exc:
            await workflow.execute_activity(
                mark_import_failed_activity,
                {"job_id": payload["job_id"], "error_message": str(exc)},
                start_to_close_timeout=timedelta(minutes=1),
            )
            raise


@workflow.defn
class ReindexWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        try:
            return await workflow.execute_activity(
                run_reindex_activity,
                payload,
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=_retry_policy(),
            )
        except CancelledError:
            await workflow.execute_activity(
                mark_reindex_cancelled_activity,
                {"job_id": payload["job_id"], "error_message": "Workflow cancellation requested."},
                start_to_close_timeout=timedelta(minutes=1),
            )
            raise
        except Exception as exc:
            await workflow.execute_activity(
                mark_reindex_failed_activity,
                {"job_id": payload["job_id"], "error_message": str(exc)},
                start_to_close_timeout=timedelta(minutes=1),
            )
            raise


@workflow.defn
class EvalWorkflow:
    @workflow.run
    async def run(self, payload: dict) -> dict:
        try:
            return await workflow.execute_activity(
                run_eval_activity,
                payload,
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=_retry_policy(),
            )
        except CancelledError:
            await workflow.execute_activity(
                mark_eval_cancelled_activity,
                {"run_id": payload["run_id"], "error_message": "Workflow cancellation requested."},
                start_to_close_timeout=timedelta(minutes=1),
            )
            raise
        except Exception as exc:
            await workflow.execute_activity(
                mark_eval_failed_activity,
                {"run_id": payload["run_id"], "error_message": str(exc)},
                start_to_close_timeout=timedelta(minutes=1),
            )
            raise
