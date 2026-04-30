# Admin History Sessions Design

## Goal

Replace the admin console's current single-answer history page with a session-oriented history page. The page should match the chat page's conversation model: one session contains multiple question-answer turns, and each turn can cite multiple source documents.

## Scope

This change covers the frontend admin history page and navigation labels. It does not change backend APIs, session creation, chat behavior, answer generation, or retrieval.

## Current State

`/history` currently renders `data.traces`, which is a flat list of answer traces from `/answer-traces`. Each item is shown as an independent historical question. The admin sidebar labels this route as "历史问答".

The chat page already uses session APIs:

- `fetchSessions(knowledgeSpaceId)` for the session list.
- `fetchSessionTraces(sessionId)` for the turns inside one session.

## Target Experience

### Navigation And Page Header

The admin navigation label changes from "历史问答" to "历史会话".

The `/history` page title changes to "历史会话". Its description should explain that the page groups historical questions by conversation session and shows cited documents inside each session.

### Split Layout

Use a two-column admin page layout:

- Left column: scrollable session list.
- Right column: selected session detail.

This matches the approved visual direction and supports scanning many sessions while inspecting one session without leaving the page.

### Session List

The left column loads sessions for the currently selected knowledge space using `fetchSessions(data.selectedSpaceId || undefined)`.

Each session row shows:

- Session name.
- Relative updated time.
- Active state when selected.

When the selected knowledge space changes, reload the session list and select the newest session by default if one exists.

Empty state: show "暂无历史会话".

### Session Detail

Selecting a session loads its turns with `fetchSessionTraces(session.id)`.

The detail header shows:

- Session name.
- Number of turns loaded.
- Number of unique cited documents across all turns.
- Last updated time.

The detail body renders the turns in returned order. Each turn shows:

- Question.
- Answer.
- Confidence percentage.
- Unique cited document chips for that turn.

Document chips are derived from `source_documents` first. If a trace has no `source_documents`, derive document chips from `citations` by `document_id`.

Empty states:

- No selected session: "请选择一个会话".
- Selected session has no turns: "该会话暂无问答记录".

Loading and error states should appear inside the relevant column without breaking the page layout.

## Data Flow

1. `HistoryPage` mounts or selected knowledge space changes.
2. Page calls `fetchSessions`.
3. Page stores sessions and selects the newest session by default.
4. Selecting a session calls `fetchSessionTraces`.
5. Page stores traces for the selected session.
6. The detail panel computes session stats and document chips from the loaded traces.

## Components

The initial implementation can stay inside `web/components/pages/history-page.tsx`:

- `HistoryPage`: owns loading state, selected session, and selected traces.
- `SessionList`: renders sessions and active row state.
- `SessionDetail`: renders header stats and trace list.

If the file becomes too large later, these can be extracted into focused UI components.

## Error Handling

- Session list fetch failure: show the API error in the left column and keep the detail empty.
- Session trace fetch failure: show the API error in the right detail panel.
- Knowledge space with no sessions: show the empty session-list state.

## Styling

Use existing admin card/list styling as the base. Add only focused classes needed for:

- Two-column history layout.
- Scrollable session list.
- Scrollable session detail panel.
- Active session row.
- Document chips inside a trace.

The page should keep the console's dense, operational feel. It should not use marketing-style hero content.

## Testing

Run the frontend build:

```bash
cd web
pnpm build
```

Manual browser verification:

- Admin navigation says "历史会话".
- `/history` loads sessions for the selected knowledge space.
- Selecting a session loads multiple turns in the right panel.
- Unique document chips appear per turn.
- Switching knowledge space reloads sessions.
- Empty, loading, and error states are readable.
