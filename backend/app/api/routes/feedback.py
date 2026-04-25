from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import AnswerTrace, Feedback
from app.schemas.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def create_feedback(payload: FeedbackRequest, db: Session = Depends(get_db)) -> FeedbackResponse:
    trace = db.get(AnswerTrace, payload.answer_trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Answer trace not found")

    feedback = Feedback(
        answer_trace_id=payload.answer_trace_id,
        rating=payload.rating,
        issue_type=payload.issue_type,
        comments=payload.comments,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return FeedbackResponse(
        id=feedback.id,
        answer_trace_id=feedback.answer_trace_id,
        rating=feedback.rating,
        issue_type=feedback.issue_type,
        comments=feedback.comments,
        created_at=feedback.created_at,
    )

