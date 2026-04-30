# Admin History Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the admin `/history` page from a flat answer list into a session-oriented history view.

**Architecture:** Reuse the existing session API helpers from `web/lib/api.ts`. `HistoryPage` owns session list state, selected session state, and selected session traces, while small local render helpers keep the page readable.

**Tech Stack:** Next.js 15, React 19, TypeScript, existing admin CSS, existing `ConsoleShell`.

---

### Task 1: Update Admin Navigation Label

**Files:**
- Modify: `web/components/console-shell.tsx`

- [ ] **Step 1: Rename navigation item**

Change the `/history` nav label from `历史问答` to `历史会话`.

- [ ] **Step 2: Build verify**

Run: `cd web && pnpm build`

Expected: PASS.

### Task 2: Implement Session-Oriented History Page

**Files:**
- Modify: `web/components/pages/history-page.tsx`

- [ ] **Step 1: Replace flat trace rendering**

Replace `data.traces.map(...)` rendering with local state:

- `sessions`
- `selectedSessionId`
- `selectedTraces`
- `sessionStatus`
- `traceStatus`

Use `fetchSessions(data.selectedSpaceId || undefined)` when the page mounts or selected knowledge space changes. Select the newest session by default.

- [ ] **Step 2: Add session trace loading**

When a session is selected, call `fetchSessionTraces(session.id)`. Store the returned turns in `selectedTraces`.

- [ ] **Step 3: Add document chip helpers**

Inside `history-page.tsx`, add helper functions to derive unique document chips from `source_documents`, falling back to `citations` by `document_id`.

- [ ] **Step 4: Add split layout markup**

Render:

- Left card: session list with active state, relative updated time, empty/loading/error states.
- Right card: selected session header stats, turn list, document chips, empty/loading/error states.

- [ ] **Step 5: Build verify**

Run: `cd web && pnpm build`

Expected: PASS.

### Task 3: Add Admin History Styling

**Files:**
- Modify: `web/app/globals.css`

- [ ] **Step 1: Add focused CSS classes**

Add classes for:

- `.history-session-layout`
- `.history-session-list-card`
- `.history-session-detail-card`
- `.history-session-list`
- `.history-session-item`
- `.history-session-item.active`
- `.history-session-detail-header`
- `.history-trace-list`
- `.history-trace-card`
- `.history-trace-answer`
- `.history-stat-row`

- [ ] **Step 2: Keep responsive behavior**

At the existing `@media (max-width: 1080px)` breakpoint, collapse `.history-session-layout` to one column and remove fixed scroll heights.

- [ ] **Step 3: Build verify**

Run: `cd web && pnpm build`

Expected: PASS.

### Task 4: Browser Verification

**Files:**
- No source changes expected.

- [ ] **Step 1: Start dev server**

Run: `cd web && NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api pnpm dev`

Expected: local Next.js dev URL starts.

- [ ] **Step 2: Verify `/history`**

Open `/history` and verify:

- Sidebar nav says "历史会话".
- Page loads session list for selected knowledge space.
- First session is selected by default when sessions exist.
- Selecting another session updates the right detail panel.
- Each turn shows question, answer, confidence, and unique document chips.
- Empty, loading, and error states are readable.

- [ ] **Step 3: Final build**

Run: `cd web && pnpm build`

Expected: PASS.
