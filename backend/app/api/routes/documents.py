from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.documents import (
    DocumentDeleteResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentRead,
    FragmentRead,
    ReindexResponse,
)
from app.services.container import ServiceContainer, get_container

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
def list_documents(
    knowledge_space_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> DocumentListResponse:
    rows = container.ingestion_service.list_documents(db, knowledge_space_id)
    return DocumentListResponse(
        items=[
            DocumentListItem(
                id=document.id,
                title=document.title,
                source_type=document.source_type,
                status=document.status,
                chunk_count=chunk_count,
                created_at=document.created_at,
            )
            for document, chunk_count in rows
        ]
    )


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> DocumentRead:
    document = container.ingestion_service.get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/{document_id}/fragments/{fragment_id}", response_model=FragmentRead)
def get_fragment(
    document_id: str,
    fragment_id: str,
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> FragmentRead:
    chunk = container.ingestion_service.get_fragment(db, document_id, fragment_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return FragmentRead(
        document_id=document_id,
        fragment_id=chunk.fragment_id,
        chunk_type=chunk.chunk_type,
        parent_id=chunk.parent_id,
        section_title=chunk.section_title,
        heading_path=chunk.heading_path,
        page_number=chunk.page_number,
        content=chunk.content,
    )


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> DocumentDeleteResponse:
    try:
        deleted = container.ingestion_service.delete_document(db, document_id)
        return DocumentDeleteResponse(id=deleted.id, title=deleted.title)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{document_id}/reindex", response_model=ReindexResponse, status_code=202)
async def reindex_document(
    document_id: str,
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> ReindexResponse:
    job = None
    try:
        job = container.ingestion_service.create_reindex_job(db, document_id)
        await container.orchestrator.start_reindex_job(job.id, job.workflow_id or "", document_id)
        db.expire_all()
        refreshed_job = container.ingestion_service.get_job(db, job.id)
        document = container.ingestion_service.get_document(db, document_id)
        assert refreshed_job is not None
        return ReindexResponse(ingestion_job=refreshed_job, document=document)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        if job is not None:
            container.ingestion_service.mark_job_failed(db, job.id, f"Workflow submission failed: {exc}")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
