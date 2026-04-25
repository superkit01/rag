from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import AnswerTrace, Chunk, Document, EvalRun
from app.schemas.common import DashboardSummary, RecentQueryRead
from app.services.container import ServiceContainer, get_container

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    knowledge_space_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> DashboardSummary:
    document_query = db.query(func.count(Document.id))
    chunk_query = db.query(func.count(Chunk.id))
    trace_query = db.query(func.count(AnswerTrace.id))
    eval_query = db.query(func.count(EvalRun.id))
    recent_query = db.query(AnswerTrace).order_by(AnswerTrace.created_at.desc())

    if knowledge_space_id:
        document_query = document_query.filter(Document.knowledge_space_id == knowledge_space_id)
        chunk_query = chunk_query.filter(Chunk.knowledge_space_id == knowledge_space_id)
        trace_query = trace_query.filter(AnswerTrace.knowledge_space_id == knowledge_space_id)
        eval_query = eval_query.filter(EvalRun.knowledge_space_id == knowledge_space_id)
        recent_query = recent_query.filter(AnswerTrace.knowledge_space_id == knowledge_space_id)

    recent = recent_query.limit(5).all()
    return DashboardSummary(
        document_count=document_query.scalar() or 0,
        chunk_count=chunk_query.scalar() or 0,
        trace_count=trace_query.scalar() or 0,
        eval_run_count=eval_query.scalar() or 0,
        recent_queries=[
            RecentQueryRead(
                id=item.id,
                question=item.question,
                confidence=item.confidence,
                created_at=item.created_at,
            )
            for item in recent
        ],
    )

