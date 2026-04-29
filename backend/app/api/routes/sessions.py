from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Session
from app.schemas.queries import AnswerTraceRead
from app.schemas.sessions import SessionCreate, SessionRead, SessionUpdate

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionRead)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
) -> SessionRead:
    """Create a new session."""
    name = payload.name or "新对话"
    session = Session(
        name=name,
        knowledge_space_id=payload.knowledge_space_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("", response_model=list[SessionRead])
def list_sessions(
    knowledge_space_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[SessionRead]:
    """List sessions, optionally filtered by knowledge space."""
    query = db.query(Session)
    if knowledge_space_id:
        query = query.filter(Session.knowledge_space_id == knowledge_space_id)
    return query.order_by(Session.updated_at.desc()).all()


@router.get("/{session_id}", response_model=SessionRead)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> SessionRead:
    """Get a single session by ID."""
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/{session_id}/traces", response_model=list[AnswerTraceRead])
def get_session_traces(
    session_id: str,
    db: Session = Depends(get_db),
) -> list[AnswerTraceRead]:
    """Get all answer traces for a session."""
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.traces


@router.patch("/{session_id}", response_model=SessionRead)
def update_session(
    session_id: str,
    payload: SessionUpdate,
    db: Session = Depends(get_db),
) -> SessionRead:
    """Update session name or timestamp."""
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if payload.name is not None:
        session.name = payload.name
    session.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(session)
    return session
