from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.documents import SourceImportRequest, SourceImportResponse
from app.services.container import ServiceContainer, get_container

router = APIRouter(prefix="/sources", tags=["sources"])


def _build_job_response(db: Session, container: ServiceContainer, job_id: str) -> SourceImportResponse:
    db.expire_all()
    job = container.ingestion_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    document = None
    if job.imported_document_id:
        document = container.ingestion_service.get_document(db, job.imported_document_id)
    return SourceImportResponse(ingestion_job=job, document=document)


@router.post("/import", response_model=SourceImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_source(
    payload: SourceImportRequest,
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> SourceImportResponse:
    job = None
    try:
        job = container.ingestion_service.create_import_job(db, payload)
        await container.orchestrator.start_ingestion_job(job.id, job.workflow_id or "", payload.model_dump(mode="json"))
        return _build_job_response(db, container, job.id)
    except Exception as exc:
        if job is not None:
            container.ingestion_service.mark_job_failed(db, job.id, f"Workflow submission failed: {exc}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/jobs", response_model=list[SourceImportResponse])
def list_jobs(
    knowledge_space_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> list[SourceImportResponse]:
    jobs = container.ingestion_service.list_jobs(db, knowledge_space_id=knowledge_space_id, limit=limit)
    return [_build_job_response(db, container, job.id) for job in jobs]


@router.get("/jobs/{job_id}", response_model=SourceImportResponse)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> SourceImportResponse:
    return _build_job_response(db, container, job_id)


@router.post("/jobs/{job_id}/retry", response_model=SourceImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_job(
    job_id: str,
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> SourceImportResponse:
    try:
        job, workflow_id, request = container.ingestion_service.retry_job(db, job_id)
        if job.job_kind == "import":
            assert request is not None
            await container.orchestrator.start_ingestion_job(job.id, workflow_id, request.model_dump(mode="json"))
        else:
            document_id = job.request_payload.get("document_id")
            if not document_id:
                raise ValueError("Retry payload is missing document_id.")
            await container.orchestrator.start_reindex_job(job.id, workflow_id, document_id)
        return _build_job_response(db, container, job.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        container.ingestion_service.mark_job_failed(db, job_id, f"Workflow retry submission failed: {exc}")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/cancel", response_model=SourceImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def cancel_job(
    job_id: str,
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> SourceImportResponse:
    try:
        job = container.ingestion_service.mark_job_cancelling(db, job_id)
        workflow_id = job.workflow_id
        if workflow_id:
            await container.orchestrator.cancel_workflow(workflow_id)
        return _build_job_response(db, container, job.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
