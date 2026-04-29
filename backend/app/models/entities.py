from __future__ import annotations

from datetime import UTC, datetime
import uuid
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class KnowledgeSpace(TimestampMixin, Base):
    __tablename__ = "knowledge_spaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="zh-CN", nullable=False)

    documents: Mapped[list["Document"]] = relationship(back_populates="knowledge_space")


class IngestionJob(TimestampMixin, Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    knowledge_space_id: Mapped[str] = mapped_column(ForeignKey("knowledge_spaces.id"), nullable=False)
    job_kind: Mapped[str] = mapped_column(String(32), default="import", nullable=False)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    imported_document_id: Mapped[Optional[str]] = mapped_column(ForeignKey("documents.id"), nullable=True)


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    knowledge_space_id: Mapped[str] = mapped_column(ForeignKey("knowledge_spaces.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), default="markdown", nullable=False)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    storage_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visibility_scope: Mapped[str] = mapped_column(String(32), default="internal", nullable=False)
    source_acl_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    connector_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    ingestion_job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("ingestion_jobs.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ready", nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    knowledge_space: Mapped["KnowledgeSpace"] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Chunk(TimestampMixin, Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False)
    knowledge_space_id: Mapped[str] = mapped_column(ForeignKey("knowledge_spaces.id"), nullable=False)
    fragment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    section_title: Mapped[str] = mapped_column(String(255), default="Introduction", nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_offset: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JSON, default=list, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="chunks")


class AnswerTrace(Base):
    __tablename__ = "answer_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    knowledge_space_id: Mapped[str] = mapped_column(ForeignKey("knowledge_spaces.id"), nullable=False)
    session_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sessions.id"), nullable=True, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    citations: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    source_documents: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    followup_queries: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence_snapshot: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    session: Mapped[Optional["Session"]] = relationship(back_populates="traces")


class Session(TimestampMixin, Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    knowledge_space_id: Mapped[str] = mapped_column(ForeignKey("knowledge_spaces.id"), nullable=False, index=True)

    traces: Mapped[list["AnswerTrace"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    answer_trace_id: Mapped[str] = mapped_column(ForeignKey("answer_traces.id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    issue_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class EvalCase(Base):
    __tablename__ = "eval_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    knowledge_space_id: Mapped[str] = mapped_column(ForeignKey("knowledge_spaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_document_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    expected_snippets: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    knowledge_space_id: Mapped[str] = mapped_column(ForeignKey("knowledge_spaces.id"), nullable=False)
    workflow_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
