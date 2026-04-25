from __future__ import annotations

from collections.abc import Iterable
import hashlib

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.entities import Chunk, Document, IngestionJob, KnowledgeSpace
from app.schemas.common import KnowledgeSpaceCreate
from app.schemas.documents import SourceImportRequest
from app.services.chunking import HierarchicalChunker
from app.services.indexing import EmbeddingProvider, IndexedChunk, SearchBackend
from app.services.object_storage import ObjectStorage
from app.services.parser import CompositeDocumentParser


class IngestionService:
    def __init__(
        self,
        parser: CompositeDocumentParser,
        chunker: HierarchicalChunker,
        search_backend: SearchBackend,
        embedding_provider: EmbeddingProvider,
        object_storage: ObjectStorage,
    ) -> None:
        self.parser = parser
        self.chunker = chunker
        self.search_backend = search_backend
        self.embedding_provider = embedding_provider
        self.object_storage = object_storage

    def ensure_knowledge_space(
        self,
        db: Session,
        knowledge_space_id: str | None = None,
        knowledge_space_name: str | None = None,
    ) -> KnowledgeSpace:
        if knowledge_space_id:
            knowledge_space = db.get(KnowledgeSpace, knowledge_space_id)
            if knowledge_space:
                return knowledge_space
        if knowledge_space_name:
            knowledge_space = db.query(KnowledgeSpace).filter(KnowledgeSpace.name == knowledge_space_name).one_or_none()
            if knowledge_space:
                return knowledge_space
            knowledge_space = KnowledgeSpace(name=knowledge_space_name, description="Auto-created knowledge space")
            db.add(knowledge_space)
            db.commit()
            db.refresh(knowledge_space)
            return knowledge_space
        default = db.query(KnowledgeSpace).filter(KnowledgeSpace.name == "默认研究空间").one_or_none()
        if default:
            return default
        default = KnowledgeSpace(name="默认研究空间", description="默认创建的内部研究知识空间")
        db.add(default)
        db.commit()
        db.refresh(default)
        return default

    def list_knowledge_spaces(self, db: Session) -> list[KnowledgeSpace]:
        return db.query(KnowledgeSpace).order_by(KnowledgeSpace.created_at.desc()).all()

    def create_knowledge_space(self, db: Session, payload: KnowledgeSpaceCreate) -> KnowledgeSpace:
        existing = db.query(KnowledgeSpace).filter(KnowledgeSpace.name == payload.name).one_or_none()
        if existing:
            return existing
        knowledge_space = KnowledgeSpace(name=payload.name, description=payload.description, language=payload.language)
        db.add(knowledge_space)
        db.commit()
        db.refresh(knowledge_space)
        return knowledge_space

    def list_documents(self, db: Session, knowledge_space_id: str | None = None) -> list[tuple[Document, int]]:
        chunk_counts = (
            db.query(Chunk.document_id.label("document_id"), func.count(Chunk.id).label("chunk_count"))
            .group_by(Chunk.document_id)
            .subquery()
        )
        query = (
            db.query(Document, func.coalesce(chunk_counts.c.chunk_count, 0))
            .outerjoin(chunk_counts, chunk_counts.c.document_id == Document.id)
            .order_by(Document.created_at.desc())
        )
        if knowledge_space_id:
            query = query.filter(Document.knowledge_space_id == knowledge_space_id)
        return query.all()

    def get_document(self, db: Session, document_id: str) -> Document | None:
        return (
            db.query(Document)
            .options(selectinload(Document.chunks))
            .filter(Document.id == document_id)
            .one_or_none()
        )

    def get_fragment(self, db: Session, document_id: str, fragment_id: str) -> Chunk | None:
        return (
            db.query(Chunk)
            .filter(Chunk.document_id == document_id, Chunk.fragment_id == fragment_id)
            .one_or_none()
        )

    def list_jobs(self, db: Session, knowledge_space_id: str | None = None, limit: int = 20) -> list[IngestionJob]:
        query = db.query(IngestionJob).order_by(IngestionJob.created_at.desc())
        if knowledge_space_id:
            query = query.filter(IngestionJob.knowledge_space_id == knowledge_space_id)
        return query.limit(limit).all()

    def get_job(self, db: Session, job_id: str) -> IngestionJob | None:
        return db.get(IngestionJob, job_id)

    def create_import_job(self, db: Session, request: SourceImportRequest) -> IngestionJob:
        knowledge_space = self.ensure_knowledge_space(db, request.knowledge_space_id, request.knowledge_space_name)
        source_uri = request.source_path or request.storage_uri or (
            f"upload://{request.uploaded_file_name}" if request.uploaded_file_name else f"inline://{request.title}"
        )
        job = IngestionJob(
            knowledge_space_id=knowledge_space.id,
            job_kind="import",
            source_uri=source_uri,
            workflow_id=self._workflow_id("ingestion", None),
            status="pending",
            request_payload=request.model_dump(mode="json"),
            attempt_count=1,
        )
        db.add(job)
        db.flush()
        job.workflow_id = self._workflow_id("ingestion", job.id, attempt_count=job.attempt_count)
        db.commit()
        db.refresh(job)
        return job

    def create_reindex_job(self, db: Session, document_id: str) -> IngestionJob:
        document = self.get_document(db, document_id)
        if document is None:
            raise ValueError(f"Document not found: {document_id}")

        document.status = "reindexing"
        job = IngestionJob(
            knowledge_space_id=document.knowledge_space_id,
            job_kind="reindex",
            source_uri=document.source_uri,
            workflow_id=self._workflow_id("reindex", None),
            status="pending",
            request_payload={"document_id": document_id},
            attempt_count=1,
            imported_document_id=document.id,
        )
        db.add(job)
        db.flush()
        job.workflow_id = self._workflow_id("reindex", job.id, attempt_count=job.attempt_count)
        db.commit()
        db.refresh(job)
        return job

    def retry_job(self, db: Session, job_id: str) -> tuple[IngestionJob, str, SourceImportRequest | None]:
        job = self._require_job(db, job_id)
        if job.status not in {"failed", "cancelled"}:
            raise ValueError("Only failed or cancelled jobs can be retried.")
        workflow_prefix = "ingestion" if job.job_kind == "import" else "reindex"
        job.attempt_count += 1
        job.workflow_id = self._workflow_id(workflow_prefix, job.id, attempt_count=job.attempt_count)
        job.status = "pending"
        job.error_message = None
        if job.job_kind == "reindex" and job.imported_document_id:
            document = self.get_document(db, job.imported_document_id)
            if document is not None:
                document.status = "reindexing"
        db.commit()
        db.refresh(job)
        if job.job_kind == "import":
            return job, job.workflow_id or "", SourceImportRequest.model_validate(job.request_payload)
        return job, job.workflow_id or "", None

    def mark_job_cancelling(self, db: Session, job_id: str) -> IngestionJob:
        job = self._require_job(db, job_id)
        if job.status not in {"pending", "running"}:
            raise ValueError("Only pending or running jobs can be cancelled.")
        job.status = "cancelling"
        db.commit()
        db.refresh(job)
        return job

    def mark_job_cancelled(self, db: Session, job_id: str, error_message: str | None = None) -> IngestionJob:
        job = self._require_job(db, job_id)
        job.status = "cancelled"
        job.error_message = error_message
        if job.imported_document_id:
            document = self.get_document(db, job.imported_document_id)
            if document is not None and document.status in {"indexing", "reindexing"}:
                document.status = "error"
        db.commit()
        db.refresh(job)
        return job

    def execute_import_job(self, db: Session, job_id: str, request: SourceImportRequest) -> IngestionJob:
        job = self._require_job(db, job_id)
        document: Document | None = None
        if job.status in {"cancelling", "cancelled"}:
            return self.mark_job_cancelled(db, job_id, "Job was cancelled before execution started.")
        job.status = "running"
        job.error_message = None
        db.commit()

        try:
            knowledge_space = self.ensure_knowledge_space(db, request.knowledge_space_id, request.knowledge_space_name)
            persisted_storage_uri = self._persist_uploaded_file(request, knowledge_space.id)
            parsed = self.parser.parse(request)
            chunks = self.chunker.chunk_sections(parsed.sections)
            merged_metadata = dict(request.source_metadata)
            merged_metadata["raw_content"] = parsed.raw_content

            document = Document(
                knowledge_space_id=knowledge_space.id,
                title=request.title,
                source_type=parsed.source_type,
                source_uri=parsed.source_uri,
                storage_uri=persisted_storage_uri or request.storage_uri,
                visibility_scope=request.visibility_scope,
                source_acl_refs=request.source_acl_refs,
                connector_id=request.connector_id,
                ingestion_job_id=job.id,
                status="indexing",
                checksum=hashlib.sha256(parsed.raw_content.encode("utf-8")).hexdigest(),
                source_metadata=merged_metadata,
            )
            db.add(document)
            db.flush()

            indexed_chunks = self._materialize_chunks(document, chunks)
            db.add_all(indexed_chunks)
            db.flush()
            db.refresh(job)
            if job.status == "cancelling":
                db.rollback()
                return self.mark_job_cancelled(db, job_id, "Job was cancelled during execution.")

            job.imported_document_id = document.id
            db.commit()
            db.refresh(job)
            db.refresh(document)

            self.search_backend.upsert_chunks(
                [
                    IndexedChunk(
                        chunk_id=chunk.id,
                        knowledge_space_id=chunk.knowledge_space_id,
                        document_id=chunk.document_id,
                        document_title=document.title,
                        fragment_id=chunk.fragment_id,
                        section_title=chunk.section_title,
                        heading_path=chunk.heading_path,
                        page_number=chunk.page_number,
                        content=chunk.content,
                        embedding=chunk.embedding,
                    )
                    for chunk in indexed_chunks
                ]
            )
            db.refresh(job)
            if job.status == "cancelling":
                self.search_backend.remove_document(document.id)
                document.status = "error"
                db.commit()
                return self.mark_job_cancelled(db, job_id, "Job was cancelled during execution.")

            document.status = "ready"
            job.status = "completed"
            db.commit()
            db.refresh(job)
            return job
        except Exception as exc:
            if document is not None:
                document.status = "error"
            job.status = "failed"
            job.error_message = str(exc)
            db.commit()
            raise

    def execute_reindex_job(self, db: Session, job_id: str, document_id: str) -> IngestionJob:
        document = self.get_document(db, document_id)
        if document is None:
            raise ValueError(f"Document not found: {document_id}")

        job = self._require_job(db, job_id)
        if job.status in {"cancelling", "cancelled"}:
            return self.mark_job_cancelled(db, job_id, "Job was cancelled before execution started.")
        job.status = "running"
        job.error_message = None
        db.commit()

        try:
            raw_content = document.source_metadata.get("raw_content")
            if not raw_content:
                raise ValueError("Document cannot be reindexed because raw content is unavailable.")
            parsed = self.parser.parse_existing(document.title, document.source_uri, document.source_type, raw_content)
            prepared_chunks = self.chunker.chunk_sections(parsed.sections)
            self.search_backend.remove_document(document.id)
            for chunk in list(document.chunks):
                db.delete(chunk)
            db.flush()

            new_chunks = self._materialize_chunks(document, prepared_chunks)
            db.add_all(new_chunks)
            db.flush()
            db.refresh(job)
            if job.status == "cancelling":
                db.rollback()
                return self.mark_job_cancelled(db, job_id, "Job was cancelled during execution.")

            document.ingestion_job_id = job.id
            job.imported_document_id = document.id
            db.commit()
            db.refresh(job)
            db.refresh(document)

            self.search_backend.upsert_chunks(
                [
                    IndexedChunk(
                        chunk_id=chunk.id,
                        knowledge_space_id=chunk.knowledge_space_id,
                        document_id=chunk.document_id,
                        document_title=document.title,
                        fragment_id=chunk.fragment_id,
                        section_title=chunk.section_title,
                        heading_path=chunk.heading_path,
                        page_number=chunk.page_number,
                        content=chunk.content,
                        embedding=chunk.embedding,
                    )
                    for chunk in new_chunks
                ]
            )
            db.refresh(job)
            if job.status == "cancelling":
                self.search_backend.remove_document(document.id)
                document.status = "error"
                db.commit()
                return self.mark_job_cancelled(db, job_id, "Job was cancelled during execution.")

            document.status = "ready"
            job.status = "completed"
            db.commit()
            db.refresh(job)
            return job
        except Exception as exc:
            document.status = "error"
            job.status = "failed"
            job.error_message = str(exc)
            db.commit()
            raise

    def mark_job_failed(self, db: Session, job_id: str, error_message: str) -> IngestionJob:
        job = self._require_job(db, job_id)
        job.status = "failed"
        job.error_message = error_message
        if job.imported_document_id:
            document = self.get_document(db, job.imported_document_id)
            if document is not None and document.status in {"indexing", "reindexing"}:
                document.status = "error"
        db.commit()
        db.refresh(job)
        return job

    def _require_job(self, db: Session, job_id: str) -> IngestionJob:
        job = self.get_job(db, job_id)
        if job is None:
            raise ValueError(f"Ingestion job not found: {job_id}")
        return job

    def _workflow_id(self, prefix: str, entity_id: str | None, attempt_count: int = 1) -> str:
        suffix = entity_id or "pending"
        return f"{prefix}-{suffix}-attempt-{attempt_count}"

    def _persist_uploaded_file(self, request: SourceImportRequest, knowledge_space_id: str) -> str | None:
        if not request.uploaded_file_base64 or not request.uploaded_file_name:
            return None
        payload = self.parser._decode_uploaded_bytes(request.uploaded_file_base64)
        return self.object_storage.store_uploaded_file(
            filename=request.uploaded_file_name,
            payload=payload,
            knowledge_space_id=knowledge_space_id,
        )

    def _materialize_chunks(self, document: Document, chunks: Iterable) -> list[Chunk]:
        prepared_chunks = list(chunks)
        embeddings = self.embedding_provider.embed_many([prepared.content for prepared in prepared_chunks])
        if len(embeddings) != len(prepared_chunks):
            raise ValueError("Embedding provider returned a different number of vectors than chunks.")
        entities: list[Chunk] = []
        for prepared, embedding in zip(prepared_chunks, embeddings):
            entities.append(
                Chunk(
                    document_id=document.id,
                    knowledge_space_id=document.knowledge_space_id,
                    fragment_id=prepared.fragment_id,
                    section_title=prepared.section_title,
                    heading_path=prepared.heading_path,
                    page_number=prepared.page_number,
                    start_offset=prepared.start_offset,
                    end_offset=prepared.end_offset,
                    token_count=prepared.token_count,
                    content=prepared.content,
                    embedding=embedding,
                )
            )
        return entities
