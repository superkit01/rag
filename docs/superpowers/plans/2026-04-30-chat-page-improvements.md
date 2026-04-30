# Chat Page Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved chat page improvements: scrollable history, modal document filtering, compact citation source chips, and a right-side document drawer.

**Architecture:** Keep the feature inside the existing Next.js chat page while extracting pure citation/file helpers into `web/lib/chat-ui.ts`. The page owns dialog, drawer, and selection state; existing backend APIs remain unchanged.

**Tech Stack:** Next.js 15, React 19, TypeScript, existing global CSS, existing `fetchJson` API helper.

---

### Task 1: Pure Chat UI Helpers

**Files:**
- Create: `web/lib/chat-ui.ts`

- [ ] **Step 1: Add helper functions**

Create `web/lib/chat-ui.ts` with:

```ts
import type { Citation } from "./types";

export type CitationDocumentGroup = {
  documentId: string;
  title: string;
  fileType: string;
  citations: Citation[];
};

export function getFileTypeLabel(title: string, sourceType?: string): string {
  const normalizedSource = sourceType?.trim();
  const extension = title.split(".").pop()?.toLowerCase();
  const value = extension && extension !== title.toLowerCase() ? extension : normalizedSource;
  if (!value) return "FILE";
  if (value.includes("pdf")) return "PDF";
  if (value.includes("doc")) return "DOC";
  if (value.includes("xls") || value.includes("sheet")) return "XLS";
  if (value.includes("ppt")) return "PPT";
  if (value.includes("md")) return "MD";
  if (value.includes("txt") || value.includes("text")) return "TXT";
  return value.slice(0, 4).toUpperCase();
}

export function groupCitationsByDocument(citations: Citation[]): CitationDocumentGroup[] {
  const groups = new Map<string, CitationDocumentGroup>();
  for (const citation of citations) {
    const current = groups.get(citation.document_id);
    if (current) {
      current.citations.push(citation);
      continue;
    }
    groups.set(citation.document_id, {
      documentId: citation.document_id,
      title: citation.document_title || "未知文档",
      fileType: getFileTypeLabel(citation.document_title || ""),
      citations: [citation]
    });
  }
  return Array.from(groups.values());
}
```

- [ ] **Step 2: Verify helper types**

Run: `cd web && pnpm build`

Expected: build reaches TypeScript compilation. If it fails because the helper is unused, continue; the next task wires it into the page.

### Task 2: Document Filter Modal And Sidebar History

**Files:**
- Modify: `web/components/pages/chat-page.tsx`
- Modify: `web/app/globals.css`

- [ ] **Step 1: Update chat page state and sidebar**

In `ChatPage`, add `isDocumentFilterOpen` state. Remove `showAllHistory` usage. Replace the inline document list in the sidebar with a compact button that opens the dialog.

- [ ] **Step 2: Add `DocumentFilterDialog` local component**

Add a local component in `chat-page.tsx` that receives documents, selected ids, search query, and callbacks. It renders only when open, supports search, select, clear, cancel/confirm, and closes on overlay click.

- [ ] **Step 3: Add CSS for scrollable sidebar and modal**

Update `globals.css` so `.chat-sidebar` has fixed vertical sections, `.chat-history` flexes and scrolls, and new modal classes render centered with a scrollable document list.

- [ ] **Step 4: Build verify**

Run: `cd web && pnpm build`

Expected: PASS.

### Task 3: Citation Chips And Document Drawer

**Files:**
- Modify: `web/components/pages/chat-page.tsx`
- Modify: `web/app/globals.css`

- [ ] **Step 1: Add drawer state and document fetch**

Add state for selected citation document group, loaded document detail, loading status, and error. Fetch `/documents/{documentId}` through `fetchJson<DocumentRead>` when a chip is selected.

- [ ] **Step 2: Replace `CitationCard` list with `CitationSourceList`**

Use `groupCitationsByDocument` to render one chip per cited document. Each chip shows file type and title, plus citation count when greater than one.

- [ ] **Step 3: Add `DocumentDrawer` local component**

Render a right-side overlay drawer with title, source metadata, current answer snippets, full chunks, loading/error states, and close button.

- [ ] **Step 4: Add drawer and chip CSS**

Add stable dimensions and responsive overlay behavior for source chips and drawer.

- [ ] **Step 5: Build verify**

Run: `cd web && pnpm build`

Expected: PASS.

### Task 4: Browser Verification

**Files:**
- No source changes expected.

- [ ] **Step 1: Start dev server**

Run: `cd web && NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api pnpm dev`

Expected: local Next.js dev URL starts.

- [ ] **Step 2: Inspect chat page in browser**

Open `/chat` and verify:

- Left history shows all sessions and scrolls independently.
- Document filter opens as a modal.
- Modal search, select, clear, cancel, and confirm work.
- Composer selected-document count updates.
- Citation chips render one item per document when citations exist.
- Clicking a chip opens the right drawer.
- Drawer closes cleanly and handles loading or API error states.

- [ ] **Step 3: Final status**

Report changed files and verification results.
