from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import KnowledgeSpaceCreate, KnowledgeSpaceRead
from app.services.container import ServiceContainer, get_container

router = APIRouter(prefix="/knowledge-spaces", tags=["knowledge-spaces"])


@router.get("", response_model=list[KnowledgeSpaceRead])
def list_knowledge_spaces(
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> list[KnowledgeSpaceRead]:
    return container.ingestion_service.list_knowledge_spaces(db)


@router.post("", response_model=KnowledgeSpaceRead)
def create_knowledge_space(
    payload: KnowledgeSpaceCreate,
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> KnowledgeSpaceRead:
    return container.ingestion_service.create_knowledge_space(db, payload)


@router.delete("/{knowledge_space_id}", response_model=KnowledgeSpaceRead)
def delete_knowledge_space(
    knowledge_space_id: str,
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> KnowledgeSpaceRead:
    try:
        return container.ingestion_service.delete_knowledge_space(db, knowledge_space_id)
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message == "Knowledge space not found." else 400
        raise HTTPException(status_code=status_code, detail=message) from exc
