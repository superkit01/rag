from fastapi import APIRouter, Depends
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

