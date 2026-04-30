# Knowledge Base Session Context Design

**Date**: 2026-04-30
**Status**: Draft for user review
**Approach**: Backend-led session title and bounded conversation context

## Overview

Improve knowledge-base chat sessions so they behave like true multi-turn conversations:

- Session names are generated automatically from the conversation.
- A session can contain multiple Q&A turns.
- Follow-up questions keep recent context during retrieval and answer generation.

The existing session foundation remains in place: `sessions` store the conversation container, `answer_traces.session_id` links turns to a session, and the frontend loads turns through `/sessions/{id}/traces`.

## Goals

1. **Automatic Session Names**
   Create a useful title from the first Q&A while still showing an immediate temporary title in the UI.

2. **Multi-Turn Context**
   Use recent Q&A turns when interpreting follow-up questions and when calling the answer model.

3. **Grounded Answers**
   Keep citations tied to the current retrieval evidence. History can clarify intent, but it is not treated as a source of truth.

4. **Backward Compatibility**
   Calls without `session_id`, evaluation flows, and existing answer trace history continue to work.

## Current State

- The frontend creates sessions and passes `session_id` to `/queries/answer/stream`.
- New session names are currently generated on the frontend from the first question.
- The backend persists `session_id` on `AnswerTrace`.
- The answer service calls the answer provider with only the current question and current retrieval evidence.
- The OpenAI-compatible provider sends only a system prompt plus one user prompt containing the current question and evidence.

This means a second question such as “继续说一下它的风险” does not reliably know what “它” refers to.

## Chosen Approach

Use a lightweight backend-led design:

- The frontend may still create an immediate temporary title from the first question.
- The backend owns final title generation and context preparation.
- The answer service reads recent turns for the active session.
- A bounded recent-history window is used for both query rewriting and model messages.

This keeps behavior consistent across streaming, non-streaming, and future clients without introducing a large new service layer yet.

## Session Title Design

### Behavior

When the first successful answer is persisted for a session, the backend attempts to produce a better title.

The backend updates the title when the existing session name is one of:

- Empty or whitespace.
- `新对话`.
- A deterministic temporary title generated from the first question.

If the user later edits a title manually, the backend should not overwrite it.

### Generation Strategy

1. Try model-based generation when an OpenAI-compatible chat model is configured.
2. Prompt the model with the first question and a shortened first answer.
3. Ask for a concise Chinese title, 8-20 characters, with no quotes or punctuation-heavy formatting.
4. If model generation fails or no model is configured, fall back to deterministic title generation from the first question.

### Failure Handling

Title generation failure must not fail the answer request. The system keeps the temporary or fallback title and still persists the answer trace.

For streaming responses, title update occurs after the answer is persisted. The existing simple path is acceptable: the frontend refreshes the session list after `done`.

## Multi-Turn Context Design

### Context Window

For requests with `session_id`, the backend loads recent turns from the same session, ordered by creation time. Use a default limit of 5 turns.

Future configuration:

```bash
CHAT_CONTEXT_TURN_LIMIT=5
```

Each historical answer is truncated before being sent to the model to avoid unbounded prompt growth.

### Session Validation

Before answering with a `session_id`, the backend validates:

- The session exists.
- The session belongs to the resolved knowledge space.

If validation fails, return a clear client error instead of persisting a trace on the wrong session.

### Retrieval Query Rewriting

Before retrieval, build a standalone retrieval query from recent history and the current question.

When a chat model is configured:

- Ask the model to rewrite the current user question into a standalone search query.
- Include recent Q&A turns as context.
- Keep the output concise and factual.

When no chat model is configured:

- Use a deterministic fallback query that combines recent user questions with the current question.
- Prefer recent questions over full historical answers to keep the query focused.

The rewritten query is used only for retrieval. The original user question is preserved in `AnswerTrace.question` and shown in the UI.

### Answer Generation

When generating the final answer, the provider receives:

- System instruction: answer only from current evidence and state uncertainty when evidence is insufficient.
- Recent conversation turns, truncated.
- Current user question.
- Current retrieval evidence.

History helps resolve references and continuity. It does not become citation evidence.

If the historical context conflicts with retrieved evidence, the answer should follow the retrieved evidence and explicitly say the available evidence is insufficient or conflicting.

## API and Data Shape

No new public endpoint is required for the first implementation.

Existing payload:

```json
{
  "question": "继续说一下它的风险",
  "session_id": "session-id",
  "knowledge_space_id": "space-id",
  "document_ids": [],
  "max_citations": 4
}
```

Existing response remains valid. The frontend can refresh `/sessions?knowledge_space_id=...` after `done` to pick up title and timestamp changes.

Optionally later, `AnswerResponse` can include a `session` summary to remove the extra refresh, but that is not required now.

## Component Responsibilities

### Frontend

- Create a session before the first question when needed.
- Use a temporary title for immediate UI feedback.
- Pass `session_id` on each answer request.
- Load historical turns when a session is selected.
- Refresh session list after answer completion.

### Backend Answer Service

- Resolve knowledge space.
- Validate the session.
- Load recent context turns.
- Build the retrieval query.
- Run retrieval and reranking.
- Generate the grounded answer with conversation context.
- Persist the answer trace.
- Update session `updated_at`.
- Generate or refine the session title after the first answer.

### Answer Provider

- Support generation with optional conversation history.
- Support streaming with optional conversation history.
- Support standalone query rewrite when a model is configured.
- Support model-based session title generation when a model is configured.

## Error Handling

| Scenario | Behavior |
| --- | --- |
| Missing `session_id` | Keep existing single-turn behavior |
| Unknown `session_id` | Return client error |
| Session belongs to another space | Return client error |
| Query rewrite fails | Fall back to deterministic combined query |
| Title generation fails | Keep temporary or fallback title |
| Model unavailable | Use existing heuristic answer provider behavior |
| No retrieval evidence | Return conservative answer with no unsupported conclusion |

## Testing Strategy

Backend tests should cover:

- First successful answer updates a default or temporary session title.
- User-edited session titles are not overwritten.
- A second turn in the same session loads previous Q&A context.
- Retrieval uses the standalone rewritten query or deterministic fallback query.
- Answer generation receives recent history when `session_id` is provided.
- Calls without `session_id` keep the previous behavior.
- Invalid or cross-space `session_id` returns a clear error.
- Streaming answer completion persists trace, updates session timestamp, and refreshes title when appropriate.

Frontend tests or manual checks should cover:

- First question shows an immediate title.
- After answer completion, the sidebar reflects the backend-refined title.
- Selecting a session restores multiple turns.
- Follow-up questions stay attached to the active session.

## Non-Goals

- User-facing manual title editing.
- Session deletion or archiving.
- Session search.
- Long-term memory summarization across all turns.
- Treating previous assistant answers as citation sources.
- Fine-grained ACL for sessions.

## Implementation Notes

This design can be implemented incrementally:

1. Add backend context loading and session validation.
2. Extend answer provider interfaces for optional history.
3. Add retrieval query rewriting with deterministic fallback.
4. Add backend title generation/refinement.
5. Update tests and frontend refresh behavior only where needed.

