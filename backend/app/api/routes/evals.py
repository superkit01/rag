from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.evals import EvalRunRequest, EvalRunResponse
from app.services.container import ServiceContainer, get_container

router = APIRouter(prefix="/eval", tags=["evals"])


@router.post("/runs", response_model=EvalRunResponse, status_code=202)
async def run_eval(
    payload: EvalRunRequest,
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> EvalRunResponse:
    eval_run = container.evaluation_service.create_run(db, payload)
    try:
        await container.orchestrator.start_eval_run(eval_run.id, eval_run.workflow_id or "", payload.model_dump(mode="json"))
        db.expire_all()
        refreshed = container.evaluation_service.get_run(db, eval_run.id)
        assert refreshed is not None
        return container.evaluation_service.to_response(refreshed, include_results=False)
    except Exception as exc:
        container.evaluation_service.mark_run_failed(db, eval_run.id, f"Workflow submission failed: {exc}")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/runs", response_model=list[EvalRunResponse])
def list_eval_runs(
    knowledge_space_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> list[EvalRunResponse]:
    runs = container.evaluation_service.list_runs(db, knowledge_space_id=knowledge_space_id, limit=limit)
    return [container.evaluation_service.to_response(run, include_results=False) for run in runs]


@router.get("/runs/{run_id}", response_model=EvalRunResponse)
def get_eval_run(
    run_id: str,
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> EvalRunResponse:
    run = container.evaluation_service.get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Eval run not found")
    return container.evaluation_service.to_response(run, include_results=True)


@router.post("/runs/{run_id}/retry", response_model=EvalRunResponse, status_code=202)
async def retry_eval_run(
    run_id: str,
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> EvalRunResponse:
    try:
        run, workflow_id, request = container.evaluation_service.retry_run(db, run_id)
        await container.orchestrator.start_eval_run(run.id, workflow_id, request.model_dump(mode="json"))
        db.expire_all()
        refreshed = container.evaluation_service.get_run(db, run.id)
        assert refreshed is not None
        return container.evaluation_service.to_response(refreshed, include_results=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        container.evaluation_service.mark_run_failed(db, run_id, f"Workflow retry submission failed: {exc}")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/runs/{run_id}/cancel", response_model=EvalRunResponse, status_code=202)
async def cancel_eval_run(
    run_id: str,
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> EvalRunResponse:
    try:
        run = container.evaluation_service.mark_run_cancelling(db, run_id)
        if run.workflow_id:
            await container.orchestrator.cancel_workflow(run.workflow_id)
        db.expire_all()
        refreshed = container.evaluation_service.get_run(db, run.id)
        assert refreshed is not None
        return container.evaluation_service.to_response(refreshed, include_results=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
