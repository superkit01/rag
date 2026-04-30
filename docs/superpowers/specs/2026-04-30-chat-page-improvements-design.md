# Chat Page Improvements Design

## Goal

Improve the chat page so expert users can keep conversation context visible, apply document filters without crowding the left rail, and inspect citation source content without leaving the chat flow.

## Scope

This change covers only the existing Next.js chat page and related frontend UI components. It does not change backend APIs, retrieval behavior, answer generation, or citation payloads.

## Interaction Design

### Left Sidebar History

The left sidebar keeps the existing knowledge-space selector and new-session action. The history section becomes the main scrollable area in the sidebar:

- Show all sessions for the selected knowledge space.
- Keep the active session highlighted.
- Remove the current three-item truncation behavior.
- Let the history list scroll independently so long session lists do not push the document-filter entry out of reach.

### Document Filter Dialog

The left sidebar no longer renders the document list directly. It shows a compact document-filter button with the current selected count:

- No selected documents: "文档过滤".
- Selected documents: "已限定 N 份文档".

Clicking the button opens a centered modal dialog. The dialog includes:

- Search input for document title filtering.
- Scrollable multi-select document list.
- Clear button to remove all selected documents.
- Confirm button to close the dialog and keep the selection.

The existing `selectedDocumentIds` state remains the source of truth. Asking a question continues to send `document_ids` to `/queries/answer/stream`.

### Citation Source Chips

Each answer's citation area becomes a compact source list. Instead of expandable quote cards, it shows one chip per cited document:

- File-type visual label derived from the document title extension or source type.
- Document title.
- Optional cited-fragment count when a document appears in multiple citations.

The chips are grouped by `document_id` from the answer turn's citations. Duplicate citations from the same document do not create duplicate chips.

### Document Drawer

Clicking a citation source chip opens a right-side drawer. The drawer fetches document details using the existing `/documents/{documentId}` endpoint and displays:

- Document title.
- Source type and status.
- Citation snippets from the current answer, highlighted as "本次命中片段".
- Full document chunks when document details load successfully.
- Loading and error states.

The drawer can be closed without changing the chat state. It is read-only and does not navigate away from the chat page.

## Components And Data Flow

The initial implementation can stay inside `web/components/pages/chat-page.tsx` with small local helper components:

- `DocumentFilterDialog`: renders modal document search and multi-select controls.
- `CitationSourceList`: groups citations by document and renders source chips.
- `DocumentDrawer`: fetches and displays document details for the selected source.

If the page becomes too large during implementation, these helpers can be moved into `web/components/ui/` without changing behavior.

Data flow:

1. User selects documents in the filter dialog.
2. `selectedDocumentIds` updates in `ChatPage`.
3. `handleAsk` sends `document_ids`.
4. The answer turn stores `citations` and `sourceDocuments`.
5. `CitationSourceList` groups turn citations by document.
6. Clicking a source sets drawer state.
7. `DocumentDrawer` fetches `/documents/{documentId}` and renders cited snippets plus chunks.

## Error Handling

- Empty history: keep the existing "暂无历史会话" state.
- Empty document search: show "没有匹配的文档。".
- Drawer loading: show a lightweight loading message.
- Drawer fetch failure: show the API error inside the drawer and allow closing it.
- No citations: keep the current warning that the answer lacks document sources.

## Responsive Behavior

Desktop uses a right-side drawer. On narrower screens, the drawer should cover the main content as an overlay while preserving the same close behavior. The document filter remains a modal dialog on all viewport sizes.

## Testing

Run the frontend production build:

```bash
cd web
pnpm build
```

If a dev server is available, manually verify:

- Long session history scrolls in the sidebar.
- Document filtering opens in a modal, searches, selects, clears, and preserves selected count.
- Asking with selected documents still sends the filter.
- Citation chips are unique by document.
- Clicking a citation chip opens the drawer and loads document content.
- Drawer loading, error, and close states work.
