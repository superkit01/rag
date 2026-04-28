from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from temporalio.worker import Worker

from app.core.config import get_settings
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
from app.workflows.definitions import EvalWorkflow, ImportWorkflow, ReindexWorkflow
from app.workflows.orchestrator import connect_temporal_client


async def main() -> None:
    settings = get_settings()
    client = await connect_temporal_client(settings)
    activity_executor = ThreadPoolExecutor(max_workers=8)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[ImportWorkflow, ReindexWorkflow, EvalWorkflow],
        activities=[
            run_import_activity,
            mark_import_failed_activity,
            mark_import_cancelled_activity,
            run_reindex_activity,
            mark_reindex_failed_activity,
            mark_reindex_cancelled_activity,
            run_eval_activity,
            mark_eval_failed_activity,
            mark_eval_cancelled_activity,
        ],
        activity_executor=activity_executor,
    )
    print(
        "Temporal worker started "
        f"(host={settings.temporal_host}, namespace={settings.temporal_namespace}, "
        f"task_queue={settings.temporal_task_queue})",
        flush=True,
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
