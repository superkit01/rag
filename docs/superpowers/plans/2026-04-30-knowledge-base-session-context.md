# Knowledge Base Session Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make knowledge-base chat sessions generate useful titles and keep bounded multi-turn context during retrieval and answer generation.

**Architecture:** Keep the existing session API and `AnswerService` as the orchestration point. Add a small `ConversationTurn` value object to the LLM layer, extend answer provider methods with optional history, and keep all current response shapes compatible.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, httpx, existing in-memory/OpenSearch retrieval abstractions.

---

## File Structure

- Modify: `backend/app/core/config.py`
  - Add `chat_context_turn_limit`.
- Modify: `backend/app/services/llm.py`
  - Add `ConversationTurn`.
  - Extend answer provider signatures with optional history.
  - Add query rewriting and title generation provider methods.
- Modify: `backend/app/services/answering.py`
  - Validate sessions.
  - Load recent turns.
  - Rewrite retrieval query.
  - Pass history to answer generation.
  - Update session timestamps and titles after persistence.
- Modify: `backend/tests/test_api.py`
  - Add integration tests for session validation, title update, history usage, and streaming persistence.

## Task 1: Add Configuration and Provider Interfaces

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/llm.py`

- [ ] **Step 1: Add failing expectations through tests in Task 2 before implementing behavior**

Task 2 depends on new provider methods. Do not change production behavior until the failing tests exist.

- [ ] **Step 2: Add config**

Add this field to `Settings` in `backend/app/core/config.py`:

```python
chat_context_turn_limit: int = int(os.getenv("CHAT_CONTEXT_TURN_LIMIT", "5"))
```

- [ ] **Step 3: Add conversation turn model and provider methods**

In `backend/app/services/llm.py`, add:

```python
@dataclass(slots=True)
class ConversationTurn:
    question: str
    answer: str
```

Then update `AnswerGenerationProvider` signatures:

```python
def generate(self, question: str, evidence: list[SearchResult], history: list[ConversationTurn] | None = None) -> str:
    ...

def stream_generate(self, question: str, evidence: list[SearchResult], history: list[ConversationTurn] | None = None) -> Iterator[str]:
    ...

def rewrite_query(self, question: str, history: list[ConversationTurn]) -> str:
    return question

def generate_session_title(self, question: str, answer: str) -> str | None:
    return None
```

Update `HeuristicAnswerProvider` to accept `history=None`, use the same answer composition, and implement deterministic `rewrite_query()` by joining recent questions with the current question.

- [ ] **Step 4: Update OpenAI provider**

Update `OpenAICompatibleAnswerProvider.generate()` and `stream_generate()` to include history in the prompt. Add model-backed `rewrite_query()` and `generate_session_title()` with fallback behavior.

- [ ] **Step 5: Run focused tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_api.py -q
```

Expected before Task 2 implementation: existing tests still pass.

## Task 2: Session Context Tests

**Files:**
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Add a recording answer provider test helper**

Add a small provider class near the test helpers:

```python
class RecordingAnswerProvider:
    def __init__(self) -> None:
        self.generate_calls = []
        self.stream_calls = []
        self.rewrite_calls = []
        self.title_calls = []

    def generate(self, question, evidence, history=None):
        self.generate_calls.append((question, evidence, history or []))
        return f"回答: {question}"

    def stream_generate(self, question, evidence, history=None):
        self.stream_calls.append((question, evidence, history or []))
        yield f"流式回答: {question}"

    def rewrite_query(self, question, history):
        self.rewrite_calls.append((question, history))
        if history:
            return " ".join([turn.question for turn in history] + [question])
        return question

    def generate_session_title(self, question, answer):
        self.title_calls.append((question, answer))
        return "核心数据上线要求"
```

- [ ] **Step 2: Add session title test**

Test flow:

1. Seed a document.
2. Create a session named `新对话`.
3. Replace `client.app.state.container.answer_provider` and `answer_service.answer_provider` with `RecordingAnswerProvider`.
4. Ask the first question with `session_id`.
5. Fetch the session.
6. Assert the title is `核心数据上线要求`.

- [ ] **Step 3: Add multi-turn context test**

Test flow:

1. Seed a document.
2. Create a session.
3. Ask first question.
4. Ask second question: `继续说一下风险`.
5. Assert the provider saw one history turn for the second answer.
6. Assert `rewrite_query()` was called with that same history.

- [ ] **Step 4: Add session validation tests**

Test two cases:

- Unknown `session_id` returns HTTP 404.
- A session from another knowledge space returns HTTP 400.

- [ ] **Step 5: Run tests and confirm failure**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_api.py::test_session_title_is_refined_after_first_answer tests/test_api.py::test_session_history_is_used_for_followup_answer tests/test_api.py::test_answer_rejects_unknown_session tests/test_api.py::test_answer_rejects_cross_space_session -q
```

Expected: FAIL before Task 3 because backend does not validate sessions or pass history yet.

## Task 3: Implement Backend Session Context

**Files:**
- Modify: `backend/app/services/answering.py`

- [ ] **Step 1: Import dependencies**

Add imports:

```python
from datetime import UTC, datetime
from fastapi import HTTPException

from app.models.entities import AnswerTrace, Session as ChatSession
from app.services.llm import AnswerGenerationProvider, ConversationTurn
```

- [ ] **Step 2: Load and validate session**

Add helper methods:

```python
def _get_session(self, db: Session, session_id: str | None, knowledge_space_id: str) -> ChatSession | None:
    if not session_id:
        return None
    session = db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.knowledge_space_id != knowledge_space_id:
        raise HTTPException(status_code=400, detail="Session does not belong to the selected knowledge space.")
    return session

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
```

- [ ] **Step 3: Use rewritten retrieval query**

In `_prepare_answer_context()`, after resolving the knowledge space:

```python
chat_session = self._get_session(db, request.session_id, knowledge_space.id)
history = self._load_history(db, chat_session.id if chat_session else None)
retrieval_query = self.answer_provider.rewrite_query(request.question, history) if history else request.question
```

Use `retrieval_query` in `self.search_backend.search(...)`. Include `chat_session` and `history` in the returned context.

- [ ] **Step 4: Pass history to answer provider**

Update non-streaming and streaming generation calls:

```python
answer = self.answer_provider.generate(request.question, context["reranked"], context["history"])
```

```python
for chunk in self.answer_provider.stream_generate(request.question, context["reranked"], context["history"]):
```

- [ ] **Step 5: Update session after persistence**

After adding the trace, update the session:

```python
if context["chat_session"] is not None:
    context["chat_session"].updated_at = datetime.now(UTC)
    self._maybe_update_session_title(db, context["chat_session"], trace)
```

Then commit once.

- [ ] **Step 6: Add title helpers**

Add deterministic title generation and update guard:

```python
def _temporary_session_name(self, question: str) -> str:
    stripped = " ".join(question.split())
    if not stripped:
        return "新对话"
    return stripped[:20] + "..." if len(stripped) > 20 else stripped

def _can_update_session_title(self, session: ChatSession, first_question: str) -> bool:
    current = session.name.strip()
    return current in {"", "新对话", self._temporary_session_name(first_question)}

def _maybe_update_session_title(self, db: Session, session: ChatSession, trace: AnswerTrace) -> None:
    trace_count = db.query(AnswerTrace).filter(AnswerTrace.session_id == session.id).count()
    if trace_count != 1:
        return
    if not self._can_update_session_title(session, trace.question):
        return
    generated = self.answer_provider.generate_session_title(trace.question, trace.answer)
    session.name = generated.strip() if generated and generated.strip() else self._temporary_session_name(trace.question)
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_api.py::test_session_title_is_refined_after_first_answer tests/test_api.py::test_session_history_is_used_for_followup_answer tests/test_api.py::test_answer_rejects_unknown_session tests/test_api.py::test_answer_rejects_cross_space_session -q
```

Expected: PASS.

## Task 4: Verify Streaming and Backward Compatibility

**Files:**
- Modify: `backend/tests/test_api.py`

- [ ] **Step 1: Add streaming session update test**

Create a session named `新对话`, stream a first answer with `session_id`, then fetch the session and assert its title was refined.

- [ ] **Step 2: Run full backend API tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest tests/test_api.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full backend tests**

Run:

```bash
cd backend && .venv/bin/python -m pytest -q
```

Expected: PASS.

## Task 5: Final Review

**Files:**
- Review: `backend/app/services/answering.py`
- Review: `backend/app/services/llm.py`
- Review: `backend/tests/test_api.py`

- [ ] **Step 1: Check formatting and imports**

Run:

```bash
cd backend && .venv/bin/python -m pytest -q
```

Expected: PASS.

- [ ] **Step 2: Inspect diff**

Run:

```bash
git diff -- backend/app/core/config.py backend/app/services/llm.py backend/app/services/answering.py backend/tests/test_api.py
```

Expected: Diff only covers session context, provider interfaces, and tests.

- [ ] **Step 3: Commit implementation**

```bash
git add backend/app/core/config.py backend/app/services/llm.py backend/app/services/answering.py backend/tests/test_api.py docs/superpowers/plans/2026-04-30-knowledge-base-session-context.md
git commit -m "feat: add session context to knowledge chat"
```

