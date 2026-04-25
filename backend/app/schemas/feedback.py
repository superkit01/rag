from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    answer_trace_id: str
    rating: int = Field(ge=1, le=5)
    issue_type: str | None = None
    comments: str | None = None


class FeedbackResponse(BaseModel):
    id: str
    answer_trace_id: str
    rating: int
    issue_type: str | None
    comments: str | None
    created_at: datetime

