from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.entities import AnswerTrace, Session as ChatSession
from app.schemas.queries import AnswerRequest, AnswerResponse, CitationRead, SourceDocumentRead
from app.services.indexing import SearchBackend, SearchResult
from app.services.ingestion import IngestionService
from app.services.llm import AnswerGenerationProvider, ConversationTurn
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
            answer = self.answer_provider.generate(request.question, context["reranked"], context["history"])
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
            for chunk in self.answer_provider.stream_generate(request.question, context["reranked"], context["history"]):
                if not chunk:
                    continue
                answer_parts.append(chunk)
                yield {"event": "delta", "data": chunk}

        answer = "".join(answer_parts).strip()
        if not answer:
            answer = self._build_conservative_answer() if context["insufficient_evidence"] else self.answer_provider.generate(
                request.question, context["reranked"], context["history"]
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
        chat_session = self._get_session(db, request.session_id, knowledge_space.id)
        history = self._load_history(db, chat_session.id if chat_session else None)
        retrieval_query = self.answer_provider.rewrite_query(request.question, history) if history else request.question
        results = self.search_backend.search(
            query=retrieval_query,
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
            "chat_session": chat_session,
            "history": history,
            "retrieval_query": retrieval_query,
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
            session_id=request.session_id,
            question=request.question,
            answer=answer,
            confidence=context["confidence"],
            citations=[item.model_dump() for item in context["citations"]],
            source_documents=[item.model_dump() for item in context["source_documents"]],
            followup_queries=context["followup_queries"],
            evidence_snapshot=[self._serialize_result(item) for item in context["reranked"]],
        )
        db.add(trace)
        db.flush()
        if context["chat_session"] is not None:
            context["chat_session"].updated_at = datetime.now(UTC)
            self._maybe_update_session_title(db, context["chat_session"], trace)
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

    def _get_session(self, db: Session, session_id: str | None, knowledge_space_id: str) -> ChatSession | None:
        if not session_id:
            return None
        chat_session = db.get(ChatSession, session_id)
        if chat_session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if chat_session.knowledge_space_id != knowledge_space_id:
            raise HTTPException(status_code=400, detail="Session does not belong to the selected knowledge space.")
        return chat_session

    def _load_history(self, db: Session, session_id: str | None) -> list[ConversationTurn]:
        if not session_id:
            return []
        limit = max(0, self.settings.chat_context_turn_limit)
        if limit == 0:
            return []
        traces = (
            db.query(AnswerTrace)
            .filter(AnswerTrace.session_id == session_id)
            .order_by(AnswerTrace.created_at.desc())
            .limit(limit)
            .all()
        )
        traces.reverse()
        return [ConversationTurn(question=item.question, answer=shorten_text(item.answer, 700)) for item in traces]

    def _temporary_session_name(self, question: str) -> str:
        stripped = " ".join(question.split())
        if not stripped:
            return "新对话"
        return stripped[:20] + "..." if len(stripped) > 20 else stripped

    def _can_update_session_title(self, chat_session: ChatSession, first_question: str) -> bool:
        current = chat_session.name.strip()
        return current in {"", "新对话", "新会话", self._temporary_session_name(first_question)}

    def _maybe_update_session_title(self, db: Session, chat_session: ChatSession, trace: AnswerTrace) -> None:
        trace_count = db.query(AnswerTrace).filter(AnswerTrace.session_id == chat_session.id).count()
        if trace_count != 1:
            return
        if not self._can_update_session_title(chat_session, trace.question):
            return
        generated = self.answer_provider.generate_session_title(trace.question, trace.answer)
        chat_session.name = generated.strip() if generated and generated.strip() else self._temporary_session_name(trace.question)

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
