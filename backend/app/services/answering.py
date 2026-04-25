from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.entities import AnswerTrace
from app.schemas.queries import AnswerRequest, AnswerResponse, CitationRead, SourceDocumentRead
from app.services.indexing import SearchBackend, SearchResult
from app.services.ingestion import IngestionService
from app.services.llm import AnswerGenerationProvider
from app.services.text_utils import shorten_text


class AnswerService:
    def __init__(
        self,
        settings: Settings,
        ingestion_service: IngestionService,
        search_backend: SearchBackend,
        answer_provider: AnswerGenerationProvider,
    ) -> None:
        self.settings = settings
        self.ingestion_service = ingestion_service
        self.search_backend = search_backend
        self.answer_provider = answer_provider

    def answer(self, db: Session, request: AnswerRequest) -> AnswerResponse:
        context = self._prepare_answer_context(db, request)
        if context["insufficient_evidence"]:
            answer = self._build_conservative_answer()
        else:
            answer = self.answer_provider.generate(request.question, context["reranked"])
        return self._persist_response(db, context, request, answer)

    def stream_answer(self, db: Session, request: AnswerRequest) -> Iterator[dict]:
        context = self._prepare_answer_context(db, request)
        yield {
            "event": "meta",
            "data": {
                "confidence": context["confidence"],
                "citations": [item.model_dump(mode="json") for item in context["citations"]],
                "source_documents": [item.model_dump(mode="json") for item in context["source_documents"]],
            },
        }

        answer_parts: list[str] = []
        if context["insufficient_evidence"]:
            for chunk in self._stream_text(self._build_conservative_answer()):
                answer_parts.append(chunk)
                yield {"event": "delta", "data": chunk}
        else:
            for chunk in self.answer_provider.stream_generate(request.question, context["reranked"]):
                if not chunk:
                    continue
                answer_parts.append(chunk)
                yield {"event": "delta", "data": chunk}

        answer = "".join(answer_parts).strip()
        if not answer:
            answer = self._build_conservative_answer() if context["insufficient_evidence"] else self.answer_provider.generate(
                request.question, context["reranked"]
            )
        response = self._persist_response(db, context, request, answer)
        yield {"event": "done", "data": response.model_dump(mode="json")}

    def list_traces(self, db: Session, knowledge_space_id: str | None = None, limit: int = 20) -> list[AnswerTrace]:
        query = db.query(AnswerTrace).order_by(AnswerTrace.created_at.desc())
        if knowledge_space_id:
            query = query.filter(AnswerTrace.knowledge_space_id == knowledge_space_id)
        return query.limit(limit).all()

    def _rerank(self, question: str, results: list[SearchResult]) -> list[SearchResult]:
        question_terms = set(question.lower().split())
        reranked = []
        for result in results:
            extra = 0.02 * len(question_terms & set(" ".join(result.heading_path).lower().split()))
            result.score = round(result.score + extra, 4)
            reranked.append(result)
        reranked.sort(key=lambda item: item.score, reverse=True)
        return reranked

    def _build_citations(self, results: list[SearchResult]) -> list[CitationRead]:
        citations: list[CitationRead] = []
        for index, item in enumerate(results, start=1):
            citations.append(
                CitationRead(
                    citation_id=f"cite-{index}",
                    document_id=item.document_id,
                    document_title=item.document_title,
                    fragment_id=item.fragment_id,
                    section_title=item.section_title,
                    heading_path=item.heading_path,
                    page_number=item.page_number,
                    quote=shorten_text(item.content, 240),
                    score=round(item.score, 4),
                )
            )
        return citations

    def _build_source_documents(self, results: list[SearchResult]) -> list[SourceDocumentRead]:
        ordered: "OrderedDict[str, SourceDocumentRead]" = OrderedDict()
        for item in results:
            existing = ordered.get(item.document_id)
            if existing is None or item.score > existing.score:
                ordered[item.document_id] = SourceDocumentRead(
                    document_id=item.document_id,
                    title=item.document_title,
                    score=round(item.score, 4),
                )
        return list(ordered.values())

    def _estimate_confidence(self, results: list[SearchResult]) -> float:
        if not results:
            return 0.0
        sample = results[:3]
        return round(min(0.99, sum(item.score for item in sample) / len(sample)), 4)

    def _build_followups(self, question: str, results: list[SearchResult]) -> list[str]:
        top_titles = [item.document_title for item in results[:2]]
        followups = [
            f"请结合 {top_titles[0]} 继续展开 {question} 的关键约束条件。",
            f"请定位与“{question}”最相关的原始章节并比较差异。",
        ]
        if len(top_titles) > 1:
            followups.append(f"请比较 {top_titles[0]} 与 {top_titles[1]} 在该问题上的结论差异。")
        return followups

    def _prepare_answer_context(self, db: Session, request: AnswerRequest) -> dict:
        knowledge_space = self.ingestion_service.ensure_knowledge_space(
            db,
            knowledge_space_id=request.knowledge_space_id,
            knowledge_space_name=request.knowledge_space_name,
        )
        results = self.search_backend.search(
            query=request.question,
            knowledge_space_id=knowledge_space.id,
            document_ids=request.document_ids,
            top_k=self.settings.retrieval_top_k,
        )
        reranked = self._rerank(request.question, results)[: self.settings.rerank_top_k]
        citations = self._build_citations(reranked[: request.max_citations])
        source_documents = self._build_source_documents(reranked)
        confidence = self._estimate_confidence(reranked)
        insufficient_evidence = not reranked or confidence < 0.1
        return {
            "knowledge_space_id": knowledge_space.id,
            "reranked": reranked,
            "citations": citations,
            "source_documents": source_documents,
            "confidence": confidence,
            "followup_queries": self._build_conservative_followups(request.question)
            if insufficient_evidence
            else self._build_followups(request.question, reranked),
            "insufficient_evidence": insufficient_evidence,
        }

    def _persist_response(self, db: Session, context: dict, request: AnswerRequest, answer: str) -> AnswerResponse:
        trace = AnswerTrace(
            knowledge_space_id=context["knowledge_space_id"],
            question=request.question,
            answer=answer,
            confidence=context["confidence"],
            citations=[item.model_dump() for item in context["citations"]],
            source_documents=[item.model_dump() for item in context["source_documents"]],
            followup_queries=context["followup_queries"],
            evidence_snapshot=[self._serialize_result(item) for item in context["reranked"]],
        )
        db.add(trace)
        db.commit()
        db.refresh(trace)

        return AnswerResponse(
            answer_trace_id=trace.id,
            answer=trace.answer,
            citations=context["citations"],
            confidence=trace.confidence,
            source_documents=context["source_documents"],
            followup_queries=context["followup_queries"],
        )

    def _build_conservative_answer(self) -> str:
        return "当前可用证据不足以支持可靠回答。建议补充更相关的文档，或把问题缩小到具体制度、流程、日期或章节。"

    def _build_conservative_followups(self, question: str) -> list[str]:
        return [
            f"{question} 的适用范围是什么？",
            f"{question} 在现有文档中对应哪个章节？",
        ]

    def _stream_text(self, text: str) -> Iterator[str]:
        chunk_size = 48
        for start in range(0, len(text), chunk_size):
            yield text[start : start + chunk_size]

    def _serialize_result(self, result: SearchResult) -> dict:
        return {
            "chunk_id": result.chunk_id,
            "document_id": result.document_id,
            "document_title": result.document_title,
            "fragment_id": result.fragment_id,
            "section_title": result.section_title,
            "heading_path": result.heading_path,
            "page_number": result.page_number,
            "content": result.content,
            "score": result.score,
        }
