from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.entities import EvalCase, EvalRun
from app.schemas.evals import EvalCaseResult, EvalRunRequest, EvalRunResponse
from app.schemas.queries import AnswerRequest
from app.services.answering import AnswerService
from app.services.ingestion import IngestionService


class EvaluationService:
    def __init__(self, ingestion_service: IngestionService, answer_service: AnswerService) -> None:
        self.ingestion_service = ingestion_service
        self.answer_service = answer_service

    def create_run(self, db: Session, request: EvalRunRequest) -> EvalRun:
        knowledge_space = self.ingestion_service.ensure_knowledge_space(
            db,
            knowledge_space_id=request.knowledge_space_id,
            knowledge_space_name=request.knowledge_space_name,
        )
        eval_run = EvalRun(
            knowledge_space_id=knowledge_space.id,
            workflow_id=self._workflow_id(None),
            status="pending",
            total_cases=len(request.cases),
            completed_cases=0,
            request_payload=request.model_dump(mode="json"),
            attempt_count=1,
            summary={},
            error_message=None,
        )
        db.add(eval_run)
        db.flush()
        eval_run.workflow_id = self._workflow_id(eval_run.id, eval_run.attempt_count)
        db.commit()
        db.refresh(eval_run)
        return eval_run

    def retry_run(self, db: Session, run_id: str) -> tuple[EvalRun, str, EvalRunRequest]:
        eval_run = self._require_run(db, run_id)
        if eval_run.status not in {"failed", "cancelled"}:
            raise ValueError("Only failed or cancelled eval runs can be retried.")
        eval_run.attempt_count += 1
        eval_run.workflow_id = self._workflow_id(eval_run.id, eval_run.attempt_count)
        eval_run.status = "pending"
        eval_run.completed_cases = 0
        eval_run.completed_at = None
        eval_run.summary = {}
        eval_run.error_message = None
        db.commit()
        db.refresh(eval_run)
        return eval_run, eval_run.workflow_id or "", EvalRunRequest.model_validate(eval_run.request_payload)

    def mark_run_cancelling(self, db: Session, run_id: str) -> EvalRun:
        eval_run = self._require_run(db, run_id)
        if eval_run.status not in {"pending", "running"}:
            raise ValueError("Only pending or running eval runs can be cancelled.")
        eval_run.status = "cancelling"
        db.commit()
        db.refresh(eval_run)
        return eval_run

    def mark_run_cancelled(self, db: Session, run_id: str, error_message: str | None = None) -> EvalRun:
        eval_run = self._require_run(db, run_id)
        eval_run.status = "cancelled"
        eval_run.completed_at = datetime.now(UTC)
        eval_run.error_message = error_message
        db.commit()
        db.refresh(eval_run)
        return eval_run

    def execute_run(self, db: Session, run_id: str, request: EvalRunRequest) -> EvalRun:
        eval_run = self._require_run(db, run_id)
        if eval_run.status in {"cancelling", "cancelled"}:
            return self.mark_run_cancelled(db, run_id, "Eval run was cancelled before execution started.")

        knowledge_space = self.ingestion_service.ensure_knowledge_space(
            db,
            knowledge_space_id=request.knowledge_space_id or eval_run.knowledge_space_id,
            knowledge_space_name=request.knowledge_space_name,
        )
        eval_run.knowledge_space_id = knowledge_space.id
        eval_run.status = "running"
        eval_run.summary = {}
        eval_run.error_message = None
        db.commit()

        try:
            results: list[EvalCaseResult] = []
            hits = 0
            citation_hits = 0
            total_citations = 0
            confidence_total = 0.0

            for case in request.cases:
                db.add(
                    EvalCase(
                        knowledge_space_id=knowledge_space.id,
                        name=case.name,
                        question=case.question,
                        expected_document_ids=case.expected_document_ids,
                        expected_snippets=case.expected_snippets,
                    )
                )
                answer = self.answer_service.answer(
                    db,
                    AnswerRequest(
                        question=case.question,
                        knowledge_space_id=knowledge_space.id,
                        document_ids=[],
                    ),
                )
                returned_document_ids = [item.document_id for item in answer.source_documents]
                expected_ids = set(case.expected_document_ids)
                hit = not expected_ids or bool(expected_ids & set(returned_document_ids))
                hits += int(hit)
                total_citations += len(answer.citations)
                citation_hits += sum(1 for citation in answer.citations if not expected_ids or citation.document_id in expected_ids)
                confidence_total += answer.confidence
                results.append(
                    EvalCaseResult(
                        name=case.name,
                        question=case.question,
                        returned_document_ids=returned_document_ids,
                        hit=hit,
                        confidence=answer.confidence,
                    )
                )

            db.refresh(eval_run)
            if eval_run.status == "cancelling":
                return self.mark_run_cancelled(db, run_id, "Eval run was cancelled during execution.")

            eval_run.status = "completed"
            eval_run.completed_cases = len(results)
            eval_run.completed_at = datetime.now(UTC)
            eval_run.summary = {
                "document_recall": round(hits / max(1, len(results)), 4),
                "citation_precision": round(citation_hits / max(1, total_citations), 4),
                "avg_confidence": round(confidence_total / max(1, len(results)), 4),
                "case_results": [item.model_dump() for item in results],
            }
            db.commit()
            db.refresh(eval_run)
            return eval_run
        except Exception as exc:
            self.mark_run_failed(db, run_id, str(exc))
            raise

    def mark_run_failed(self, db: Session, run_id: str, error_message: str) -> EvalRun:
        eval_run = self._require_run(db, run_id)
        eval_run.status = "failed"
        eval_run.completed_at = datetime.now(UTC)
        eval_run.error_message = error_message
        summary = dict(eval_run.summary or {})
        summary["error_message"] = error_message
        eval_run.summary = summary
        db.commit()
        db.refresh(eval_run)
        return eval_run

    def get_run(self, db: Session, run_id: str) -> EvalRun | None:
        return db.get(EvalRun, run_id)

    def list_runs(self, db: Session, knowledge_space_id: str | None = None, limit: int = 20) -> list[EvalRun]:
        query = db.query(EvalRun).order_by(EvalRun.created_at.desc())
        if knowledge_space_id:
            query = query.filter(EvalRun.knowledge_space_id == knowledge_space_id)
        return query.limit(limit).all()

    def to_response(self, run: EvalRun, include_results: bool = True) -> EvalRunResponse:
        summary = dict(run.summary or {})
        raw_results = summary.pop("case_results", [])
        results = [EvalCaseResult.model_validate(item) for item in raw_results] if include_results else []
        return EvalRunResponse(
            id=run.id,
            knowledge_space_id=run.knowledge_space_id,
            workflow_id=run.workflow_id,
            status=run.status,
            attempt_count=run.attempt_count,
            error_message=run.error_message,
            total_cases=run.total_cases,
            completed_cases=run.completed_cases,
            summary=summary,
            created_at=run.created_at,
            completed_at=run.completed_at,
            results=results,
        )

    def _require_run(self, db: Session, run_id: str) -> EvalRun:
        eval_run = self.get_run(db, run_id)
        if eval_run is None:
            raise ValueError(f"Eval run not found: {run_id}")
        return eval_run

    def _workflow_id(self, run_id: str | None, attempt_count: int = 1) -> str:
        suffix = run_id or "pending"
        return f"eval-{suffix}-attempt-{attempt_count}"
