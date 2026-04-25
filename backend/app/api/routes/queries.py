import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.queries import AnswerRequest, AnswerResponse, AnswerTraceRead
from app.services.container import ServiceContainer, get_container

router = APIRouter(prefix="/queries", tags=["queries"])
trace_router = APIRouter(prefix="/answer-traces", tags=["answer-traces"])


@router.post("/answer", response_model=AnswerResponse)
def answer_query(
    payload: AnswerRequest,
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> AnswerResponse:
    if container.search_backend.backend_name == "memory-hybrid":
        container.bootstrap_index(db)
    return container.answer_service.answer(db, payload)


@router.post("/answer/stream")
def answer_query_stream(
    payload: AnswerRequest,
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> StreamingResponse:
    if container.search_backend.backend_name == "memory-hybrid":
        container.bootstrap_index(db)

    def event_stream():
        try:
            for item in container.answer_service.stream_answer(db, payload):
                yield _render_sse(item["event"], item["data"])
        except Exception as exc:
            yield _render_sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@trace_router.get("", response_model=list[AnswerTraceRead])
def list_answer_traces(
    knowledge_space_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    container: ServiceContainer = Depends(get_container),
) -> list[AnswerTraceRead]:
    return container.answer_service.list_traces(db, knowledge_space_id=knowledge_space_id, limit=limit)


def _render_sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
