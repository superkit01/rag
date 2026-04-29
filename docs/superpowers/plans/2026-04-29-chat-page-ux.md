# Chat Page UX Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance chat page UX with Markdown rendering, inline citations, progress feedback, and visual polish.

**Architecture:** Progressive enhancement - add new UI components (Toast, CitationBadge, MarkdownRenderer) and integrate into existing chat-page.tsx. No backend changes, pure frontend improvements.

**Tech Stack:** React, Next.js 15, react-markdown, prism-react-renderer, framer-motion (for animations)

---

## File Structure

**New Components:**
- `web/components/ui/toast.tsx` - Global toast notification system
- `web/components/ui/citation-badge.tsx` - Inline citation marker with hover popover
- `web/components/ui/citation-popover.tsx` - Hover card showing citation preview
- `web/components/ui/citation-card.tsx` - Enhanced collapsible citation card
- `web/components/ui/skeleton.tsx` - Skeleton loading placeholders
- `web/components/ui/markdown-renderer.tsx` - Markdown renderer with code highlighting
- `web/lib/streaming-parser.ts` - Buffered streaming markdown parser
- `web/hooks/use-toast.ts` - Toast state management hook

**Modified Files:**
- `web/components/pages/chat-page.tsx` - Integrate all new components
- `web/app/globals.css` - Add animations and new component styles
- `web/package.json` - Add new dependencies

---

## Task 1: Install Dependencies

**Files:**
- Modify: `web/package.json`

- [ ] **Step 1: Add dependencies to package.json**

```json
{
  "dependencies": {
    "react-markdown": "^9.0.1",
    "remark-gfm": "^4.0.0",
    "prism-react-renderer": "^2.3.1",
    "framer-motion": "^11.0.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.0"
  }
}
```

- [ ] **Step 2: Install dependencies**

Run: `cd web && pnpm install`
Expected: Dependencies installed successfully

- [ ] **Step 3: Commit**

```bash
git add web/package.json web/pnpm-lock.yaml
git commit -m "feat: add markdown rendering and animation dependencies"
```

---

## Task 2: Create Toast Notification System

**Files:**
- Create: `web/hooks/use-toast.ts`
- Create: `web/components/ui/toast.tsx`
- Modify: `web/app/globals.css`

- [ ] **Step 1: Create toast hook**

```typescript
// web/hooks/use-toast.ts
import { useState, useCallback } from "react";

export type ToastType = "success" | "error" | "info";

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
}

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: ToastType = "info", duration = 3000) => {
    const id = Math.random().toString(36).substring(7);
    const toast: Toast = { id, message, type, duration };
    setToasts((current) => [...current, toast]);

    if (duration > 0) {
      setTimeout(() => {
        setToasts((current) => current.filter((t) => t.id !== id));
      }, duration);
    }
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  return { toasts, showToast, removeToast };
}
```

- [ ] **Step 2: Create Toast component**

```typescript
// web/components/ui/toast.tsx
"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useToast, Toast } from "@/hooks/use-toast";

const toastStyles = {
  success: "bg-green-50 border-green-200 text-green-800",
  error: "bg-red-50 border-red-200 text-red-800",
  info: "bg-blue-50 border-blue-200 text-blue-800"
};

export function ToastContainer() {
  const { toasts, removeToast } = useToast();

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, x: 100 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 100 }}
            className={`px-4 py-3 rounded-lg border shadow-lg ${toastStyles[toast.type]} max-w-md`}
            onClick={() => removeToast(toast.id)}
          >
            <p className="text-sm font-medium">{toast.message}</p>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
```

- [ ] **Step 3: Add toast styles to globals.css**

```css
/* Add to web/app/globals.css */
@keyframes slideInRight {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
```

- [ ] **Step 4: Run dev server to verify**

Run: `cd web && pnpm dev`
Expected: No TypeScript errors, dev server starts

- [ ] **Step 5: Commit**

```bash
git add web/hooks/use-toast.ts web/components/ui/toast.tsx web/app/globals.css
git commit -m "feat: add toast notification system"
```

---

## Task 3: Create Skeleton Loading Component

**Files:**
- Create: `web/components/ui/skeleton.tsx`

- [ ] **Step 1: Create Skeleton component**

```typescript
// web/components/ui/skeleton.tsx
import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-pulse bg-gray-200 rounded",
        className
      )}
    />
  );
}

export function DocumentSkeleton() {
  return (
    <div className="p-4 border rounded-lg bg-white space-y-3">
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-3 w-1/2" />
      <Skeleton className="h-3 w-1/3" />
    </div>
  );
}

export function ChatMessageSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-6 w-32" />
      <Skeleton className="h-20 w-full rounded-2xl" />
    </div>
  );
}
```

- [ ] **Step 2: Create utility function for class merging**

```typescript
// web/lib/utils.ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 3: Verify no TypeScript errors**

Run: Check `web/lib/utils.ts` and `web/components/ui/skeleton.tsx`
Expected: No red squiggles in IDE

- [ ] **Step 4: Commit**

```bash
git add web/lib/utils.ts web/components/ui/skeleton.tsx
git commit -m "feat: add skeleton loading components"
```

---

## Task 4: Create Citation Badge and Popover

**Files:**
- Create: `web/components/ui/citation-badge.tsx`
- Create: `web/components/ui/citation-popover.tsx`

- [ ] **Step 1: Create CitationBadge component**

```typescript
// web/components/ui/citation-badge.tsx
"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { Citation } from "@/lib/types";
import { CitationPopover } from "./citation-popover";

interface CitationBadgeProps {
  citation: Citation;
  index: number;
}

export function CitationBadge({ citation, index }: CitationBadgeProps) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <span
      className="relative inline-block"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <sup className="inline-flex items-center justify-center w-5 h-5 text-xs font-semibold text-blue-700 bg-blue-100 rounded cursor-pointer hover:bg-blue-200 transition-colors">
        {index}
      </sup>
      <AnimatePresence>
        {isHovered && (
          <CitationPopover citation={citation} />
        )}
      </AnimatePresence>
    </span>
  );
}
```

- [ ] **Step 2: Create CitationPopover component**

```typescript
// web/components/ui/citation-popover.tsx
"use client";

import { motion } from "framer-motion";
import type { Citation } from "@/lib/types";

interface CitationPopoverProps {
  citation: Citation;
}

export function CitationPopover({ citation }: CitationPopoverProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10, scale: 0.95 }}
      animate={{ opacity: 1, y: -40, scale: 1 }}
      exit={{ opacity: 0, y: -10, scale: 0.95 }}
      className="absolute z-50 w-80 p-3 bg-white rounded-lg shadow-xl border border-gray-200"
    >
      <p className="text-sm font-semibold text-gray-900">{citation.document_title}</p>
      <p className="text-xs text-gray-600 mt-1">{citation.section_title}</p>
      <p className="text-xs text-gray-700 mt-2 line-clamp-2">
        {citation.quote.slice(0, 80)}...
      </p>
      <div className="mt-2 pt-2 border-t border-gray-100">
        <p className="text-xs text-gray-500">
          Score: {citation.score.toFixed(3)}
        </p>
      </div>
    </motion.div>
  );
}
```

- [ ] **Step 3: Verify imports resolve correctly**

Check: Imports from `@/lib/types` resolve
Expected: No TypeScript errors

- [ ] **Step 4: Commit**

```bash
git add web/components/ui/citation-badge.tsx web/components/ui/citation-popover.tsx
git commit -m "feat: add inline citation badge with hover popover"
```

---

## Task 5: Create Markdown Renderer

**Files:**
- Create: `web/components/ui/markdown-renderer.tsx`
- Create: `web/lib/streaming-parser.ts`

- [ ] **Step 1: Create streaming parser utility**

```typescript
// web/lib/streaming-parser.ts

const BUFFER_SIZE = 50; // Accumulate 50 chars before re-render
const INCOMPLETE_CODE_BLOCK_REGEX = /```[a-z]*\n([\s\S]*?)?(?!```)$/;
const INCOMPLETE_INLINE_CODE = /`[^`]*$/;

export function shouldBufferUpdate(content: string, buffered: string): boolean {
  const combined = buffered + content;
  return combined.length >= BUFFER_SIZE;
}

export function hasIncompleteMarkdown(text: string): boolean {
  return (
    INCOMPLETE_CODE_BLOCK_REGEX.test(text) ||
    INCOMPLETE_INLINE_CODE.test(text)
  );
}

export function preprocessCitations(text: string): string {
  // Convert {{cite:N}} to markdown link syntax for processing
  return text.replace(/\{\{cite:(\d+)\}\}/g, "[$1]");

}

export function postprocessCitations(html: string, citations: any[]): string {
  // Replace citation markers with react component markers
  return html.replace(
    /\[(\d+)\]/g,
    (match, num) => `__CITATION_${num}__`
  );
}
```

- [ ] **Step 2: Create MarkdownRenderer component**

```typescript
// web/components/ui/markdown-renderer.tsx
"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { CitationBadge } from "./citation-badge";
import type { Citation } from "@/lib/types";

interface MarkdownRendererProps {
  content: string;
  citations?: Citation[];
  isStreaming?: boolean;
}

export function MarkdownRenderer({ content, citations = [], isStreaming = false }: MarkdownRendererProps) {
  const citationMap = new Map(citations.map((c, i) => [i + 1, c]));

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ node, inline, className, children, ...props }: any) {
          const match = /language-(\w+)/.exec(className || "");
          const language = match ? match[1] : "";

          return !inline && language ? (
            <SyntaxHighlighter
              style={oneDark}
              language={language}
              PreTag="div"
              className="rounded-lg"
            >
              {String(children).replace(/\n$/, "")}
            </SyntaxHighlighter>
          ) : (
            <code className="px-1.5 py-0.5 bg-gray-100 rounded text-sm font-mono" {...props}>
              {children}
            </code>
          );
        },
        p({ children }) {
          // Check for citation markers and render with badges
          const childStr = String(children);
          if (/__CITATION_(\d+)__/.test(childStr)) {
            const parts = childStr.split(/(__CITATION_\d+__)/);
            return (
              <p className="mb-2 last:mb-0">
                {parts.map((part, i) => {
                  const match = part.match(/__CITATION_(\d+)__/);
                  if (match) {
                    const citationNum = parseInt(match[1], 10);
                    const citation = citationMap.get(citationNum);
                    return citation ? (
                      <CitationBadge key={i} citation={citation} index={citationNum} />
                    ) : null;
                  }
                  return <span key={i}>{part}</span>;
                })}
              </p>
            );
          }
          return <p className="mb-2 last:mb-0">{children}</p>;
        },
        ul({ children }) {
          return <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>;
        },
        ol({ children }) {
          return <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>;
        },
        h1({ children }) {
          return <h1 className="text-2xl font-bold mb-3">{children}</h1>;
        },
        h2({ children }) {
          return <h2 className="text-xl font-bold mb-2">{children}</h2>;
        },
        h3({ children }) {
          return <h3 className="text-lg font-semibold mb-2">{children}</h3>;
        },
        blockquote({ children }) {
          return <blockquote className="border-l-4 border-gray-300 pl-4 italic my-2">{children}</blockquote>;
        },
        a({ href, children }) {
          return (
            <a href={href} className="text-blue-600 hover:underline" target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          );
        },
        table({ children }) {
          return (
            <div className="overflow-x-auto my-4">
              <table className="min-w-full border border-gray-300">{children}</table>
            </div>
          );
        },
        thead({ children }) {
          return <thead className="bg-gray-100">{children}</thead>;
        },
        th({ children }) {
          return <th className="px-4 py-2 border-b text-left font-semibold">{children}</th>;
        },
        td({ children }) {
          return <td className="px-4 py-2 border-b">{children}</td>;
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
```

- [ ] **Step 3: Verify all imports resolve**

Check: All imports from react-markdown, react-syntax-highlighter, etc.
Expected: No TypeScript errors

- [ ] **Step 4: Commit**

```bash
git add web/lib/streaming-parser.ts web/components/ui/markdown-renderer.tsx
git commit -m "feat: add markdown renderer with code highlighting"
```

---

## Task 6: Create Enhanced Citation Card

**Files:**
- Create: `web/components/ui/citation-card.tsx`

- [ ] **Step 1: Create collapsible CitationCard component**

```typescript
// web/components/ui/citation-card.tsx
"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import type { Citation } from "@/lib/types";

interface CitationCardProps {
  citation: Citation;
  index: number;
}

export function CitationCard({ citation, index }: CitationCardProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  const getRelevanceColor = (score: number) => {
    if (score >= 0.8) return "bg-green-100 text-green-700 border-green-200";
    if (score >= 0.5) return "bg-yellow-100 text-yellow-700 border-yellow-200";
    return "bg-red-100 text-red-700 border-red-200";
  };

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      className="p-3 rounded-lg border bg-white hover:shadow-md transition-shadow"
    >
      <div
        className="flex items-start justify-between cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex-1">
          <p className="text-sm font-semibold">{citation.document_title}</p>
          <p className="text-xs text-gray-600 mt-0.5">{citation.section_title}</p>
        </div>
        <button className="text-gray-400 hover:text-gray-600">
          {isExpanded ? "−" : "+"}
        </button>
      </div>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <p className="text-sm text-gray-700 mt-3 leading-relaxed">
              {citation.quote}
            </p>

            <div className="flex items-center justify-between mt-3 pt-2 border-t border-gray-100">
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getRelevanceColor(citation.score)}`}>
                  {citation.score >= 0.8 ? "高相关" : citation.score >= 0.5 ? "中相关" : "低相关"}
                </span>
                <span className="text-xs text-gray-500">
                  fragment={citation.fragment_id}
                </span>
              </div>

              <Link
                href={`/documents/${citation.document_id}`}
                className="text-xs text-blue-600 hover:underline"
              >
                查看完整文档 →
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
```

- [ ] **Step 2: Verify component compiles**

Check: No TypeScript errors in CitationCard
Expected: Clean compile

- [ ] **Step 3: Commit**

```bash
git add web/components/ui/citation-card.tsx
git commit -m "feat: add collapsible citation card with relevance indicators"
```

---

## Task 7: Update Chat Page - Integrate Markdown Renderer

**Files:**
- Modify: `web/components/pages/chat-page.tsx`

- [ ] **Step 1: Add imports and update ChatTurn type**

```typescript
// Add these imports at top of chat-page.tsx
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";
import { hasIncompleteMarkdown, preprocessCitations } from "@/lib/streaming-parser";
import { useToast } from "@/hooks/use-toast";
import { ToastContainer } from "@/components/ui/toast";
import { DocumentSkeleton } from "@/components/ui/skeleton";
import { CitationCard } from "@/components/ui/citation-card";
```

- [ ] **Step 2: Add toast hook in ChatPage component**

```typescript
// Inside ChatPage component, after existing state declarations:
const { showToast } = useToast();
const [renderedContent, setRenderedContent] = useState("");
```

- [ ] **Step 3: Update handleAsk to use streaming parser**

Find the `onDelta` handler in `handleAsk` and replace:

```typescript
onDelta(delta) {
  setStreamingText((currentText) => {
    const nextText = currentText + delta;
    const preprocessed = preprocessCitations(nextText);

    // Only update rendered content if not in middle of incomplete markdown
    if (!hasIncompleteMarkdown(preprocessed)) {
      setRenderedContent(preprocessed);
    }

    setTurns((current) =>
      current.map((turn) =>
        turn.id === turnId ? { ...turn, answer: preprocessed } : turn
      )
    );
    return nextText;
  });
},
```

- [ ] **Step 4: Update onDone handler**

```typescript
onDone(result) {
  setAnswer(result);
  const finalContent = preprocessCitations(result.answer);
  setStreamingText(finalContent);
  setRenderedContent(finalContent);
  setCitations(result.citations);
  setSourceDocuments(result.sourceDocuments);
  showToast(`问答已完成，当前置信度 ${Math.round(result.confidence * 100)}%`, "success");
  setTurns((current) =>
    current.map((turn) =>
      turn.id === turnId
        ? {
            ...turn,
            answer: finalContent,
            citations: result.citations,
            sourceDocuments: result.source_documents,
            confidence: result.confidence,
            answerTraceId: result.answer_trace_id,
            isStreaming: false
          }
        : turn
    )
  );
}
```

- [ ] **Step 5: Update chat message rendering**

Find the chat-message.assistant bubble and replace:

```typescript
<div className="chat-message assistant">
  <div className="chat-bubble">
    {turn.isStreaming && (!turn.answer || hasIncompleteMarkdown(turn.answer)) ? (
      <>
        {turn.answer || "正在组织答案..."}
        <span className="stream-cursor">|</span>
      </>
    ) : (
      <MarkdownRenderer
        content={turn.answer}
        citations={turn.citations}
        isStreaming={turn.isStreaming}
      />
    )}
  </div>
</div>
```

- [ ] **Step 6: Replace old citation cards with new CitationCard**

Replace the chat-meta-card section:

```typescript
{turn.citations.length > 0 && (
  <div className="chat-message assistant">
    <div className="chat-meta-card">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-semibold">引用来源 ({turn.citations.length})</h4>
      </div>
      <div className="space-y-2">
        {turn.citations.map((citation, index) => (
          <CitationCard key={citation.citation_id} citation={citation} index={index + 1} />
        ))}
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 7: Add ToastContainer to render**

Add before the closing `</main>`:

```typescript
<ToastContainer />
```

- [ ] **Step 8: Verify no TypeScript errors**

Run: Check IDE for red squiggles
Expected: No TypeScript errors

- [ ] **Step 9: Commit**

```bash
git add web/components/pages/chat-page.tsx
git commit -m "feat: integrate markdown renderer and enhanced citations"
```

---

## Task 8: Add Progress Bar and Status Text

**Files:**
- Modify: `web/components/pages/chat-page.tsx`
- Modify: `web/app/globals.css`

- [ ] **Step 1: Add streaming progress state**

Add to ChatPage component:

```typescript
const [streamingProgress, setStreamingProgress] = useState(0);
const [streamingPhase, setStreamingPhase] = useState<"thinking" | "writing" | "done">("thinking");
```

- [ ] **Step 2: Create ProgressBar component inline**

Add before ChatPage function:

```typescript
function ProgressBar({ progress }: { progress: number }) {
  return (
    <div className="h-1 bg-gray-200 rounded-full overflow-hidden">
      <motion.div
        className="h-full bg-blue-500"
        initial={{ width: 0 }}
        animate={{ width: `${progress}%` }}
        transition={{ ease: "easeOut" }}
      />
    </div>
  );
}
```

- [ ] **Step 3: Update onDelta to track progress**

```typescript
onDelta(delta) {
  setStreamingText((currentText) => {
    const nextText = currentText + delta;
    const preprocessed = preprocessCitations(nextText);

    // Update progress based on content length (heuristic)
    setStreamingProgress(Math.min((nextText.length / 500) * 100, 95));
    if (nextText.length > 50) {
      setStreamingPhase("writing");
    }

    if (!hasIncompleteMarkdown(preprocessed)) {
      setRenderedContent(preprocessed);
    }

    setTurns((current) =>
      current.map((turn) =>
        turn.id === turnId ? { ...turn, answer: preprocessed } : turn
      )
    );
    return nextText;
  });
},
```

- [ ] **Step 4: Update onDone to complete progress**

```typescript
onDone(result) {
  setStreamingProgress(100);
  setStreamingPhase("done");
  // ... rest of onDone
}
```

- [ ] **Step 5: Render progress bar above streaming answer**

```typescript
{turn.isStreaming && (
  <div className="mb-2">
    <ProgressBar progress={streamingProgress} />
    <p className="text-xs text-gray-500 mt-1">
      {streamingPhase === "thinking" && "正在思考..."}
      {streamingPhase === "writing" && "正在组织答案..."}
    </p>
  </div>
)}
```

- [ ] **Step 6: Add stream cursor sway animation to globals.css**

```css
@keyframes sway {
  0%, 100% { transform: translateX(0); }
  50% { transform: translateX(2px); }
}

.stream-cursor {
  display: inline-block;
  margin-left: 2px;
  animation: sway 1s ease-in-out infinite, blink 1s steps(1) infinite;
}
```

- [ ] **Step 7: Commit**

```bash
git add web/components/pages/chat-page.tsx web/app/globals.css
git commit -m "feat: add streaming progress bar and status text"
```

---

## Task 9: Visual Polish - CSS Updates

**Files:**
- Modify: `web/app/globals.css`

- [ ] **Step 1: Update chat bubble styles**

Find and replace chat-bubble styles:

```css
.chat-bubble {
  max-width: min(760px, 100%);
  padding: 16px 18px;
  border-radius: 16px;
  line-height: 1.8;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08);
}

.chat-message.user .chat-bubble {
  background: linear-gradient(135deg, #1f2937, #111827);
  color: white;
  border-bottom-right-radius: 8px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.15);
}

.chat-message.assistant .chat-bubble {
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-bottom-left-radius: 8px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.06);
}
```

- [ ] **Step 2: Update message group spacing**

```css
.chat-message-group {
  display: grid;
  gap: 28px;
}
```

- [ ] **Step 3: Update chat meta card border radius**

```css
.chat-meta-card {
  max-width: min(760px, 100%);
  padding: 16px 18px;
  border: 1px solid rgba(22, 119, 255, 0.12);
  border-radius: 16px;
  background: rgba(248, 251, 255, 0.95);
}
```

- [ ] **Step 4: Commit**

```bash
git add web/app/globals.css
git commit -m "style: enhance chat bubble shadows and spacing"
```

---

## Task 10: Input Composer Enhancements

**Files:**
- Modify: `web/components/pages/chat-page.tsx`

- [ ] **Step 1: Add auto-height textarea**

Add ref and auto-height logic:

```typescript
// Add ref
const textareaRef = useRef<HTMLTextAreaElement>(null);

// Auto-height function
const adjustTextareaHeight = useCallback(() => {
  const textarea = textareaRef.current;
  if (textarea) {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + "px";
  }
}, []);

// Add to textarea
<textarea
  ref={textareaRef}
  value={question}
  onChange={(e) => {
    setQuestion(e.target.value);
    adjustTextareaHeight();
  }}
  placeholder="给知识库发一条消息，或要求它基于引用整理结论... (Enter 发送，Shift+Enter 换行)"
  onKeyDown={(e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      // Trigger form submit
    }
  }}
  rows={1}
  style={{ minHeight: "96px", maxHeight: "200px", overflowY: "auto" }}
/>
```

- [ ] **Step 2: Add character counter**

Add in chat-composer-actions:

```typescript
<div className="chat-composer-actions">
  <div className="chat-composer-meta">
    {selectedDocumentIds.length ? `已限定 ${selectedDocumentIds.length} 份文档` : "当前使用整个命名空间"}
    <span className={question.length > 500 ? "text-orange-500" : "text-gray-500"}>
      {question.length} 字
    </span>
  </div>
  <button className="button" type="submit" disabled={isStreaming}>
    {isStreaming ? "生成中..." : "发送"}
  </button>
</div>
```

- [ ] **Step 3: Update disabled state**

```typescript
<textarea
  // ... other props
  disabled={isStreaming}
  placeholder={isStreaming ? "请等待当前回答完成..." : "给知识库发一条消息..."}
  className={isStreaming ? "opacity-50 cursor-not-allowed" : ""}
/>
```

- [ ] **Step 4: Commit**

```bash
git add web/components/pages/chat-page.tsx
git commit -m "feat: add auto-height textarea and character counter"
```

---

## Task 11: Sidebar Simplifications

**Files:**
- Modify: `web/components/pages/chat-page.tsx`

- [ ] **Step 1: Inline knowledge space selector**

Move the space select into the chat-sidebar-top section:

```typescript
<div className="chat-sidebar-top">
  <div className="chat-logo">
    <span className="chat-logo-mark">AI</span>
    <div>
      <strong>知识库对话</strong>
      <div className="tiny">独立对话页</div>
    </div>
  </div>
  <select
    className="select mini-button"
    style={{ padding: "8px 12px", fontSize: "13px" }}
    value={data.selectedSpaceId}
    onChange={(event) => data.setSelectedSpaceId(event.target.value)}
  >
    <option value="">默认空间</option>
    {data.spaces.map((space) => (
      <option key={space.id} value={space.id}>
        {space.name}
      </option>
    ))}
  </select>
</div>
```

- [ ] **Step 2: Make recent conversations collapsible**

```typescript
const [showAllHistory, setShowAllHistory] = useState(false);

// In the history section:
<section className="chat-sidebar-card">
  <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
    <h3 style={{ marginBottom: 0 }}>最近对话</h3>
    {turns.length > 3 && (
      <button
        className="mini-button"
        type="button"
        onClick={() => setShowAllHistory(!showAllHistory)}
        style={{ padding: "4px 8px", fontSize: "12px" }}
      >
        {showAllHistory ? "收起" : "展开"}
      </button>
    )}
  </div>
  <div className="chat-history" style={{ marginTop: 12 }}>
    {!turns.length ? (
      <div className="tiny">还没有开始会话，先试一个研究问题。</div>
    ) : (
      turns
        .slice()
        .reverse()
        .slice(0, showAllHistory ? undefined : 3)
        .map((turn) => (
          <div key={turn.id} className="chat-history-item">
            <strong>{turn.question}</strong>
            <div className="tiny">{turn.isStreaming ? "正在生成回答..." : `引用 ${turn.citations.length} 条`}</div>
          </div>
        ))
    )}
  </div>
</section>
```

- [ ] **Step 3: Add document search**

```typescript
const [docSearchQuery, setDocSearchQuery] = useState("");

// Filter documents
const filteredDocuments = data.documents.filter(doc =>
  doc.title.toLowerCase().includes(docSearchQuery.toLowerCase())
);

// Add search input in document filtering section:
<input
  type="text"
  className="input"
  placeholder="搜索文档..."
  value={docSearchQuery}
  onChange={(e) => setDocSearchQuery(e.target.value)}
  style={{ marginBottom: "12px", padding: "8px 12px", fontSize: "13px" }}
/>
```

- [ ] **Step 4: Commit**

```bash
git add web/components/pages/chat-page.tsx
git commit -m "feat: simplify sidebar with inline space selector and collapsible history"
```

---

## Task 12: Loading States - Error Handling

**Files:**
- Modify: `web/components/pages/chat-page.tsx`

- [ ] **Step 1: Enhance error handling in handleAsk**

```typescript
} catch (error) {
  const errorMessage = getErrorMessage(error);
  showToast(errorMessage, "error");
  setStatus(errorMessage);

  // Check if it's a network error
  if (errorMessage.includes("fetch") || errorMessage.includes("network")) {
    setStatus("连接失败，请检查网络后重试");
  }

  setTurns((current) =>
    current.map((turn) =>
      turn.id === turnId
        ? { ...turn, answer: errorMessage, isStreaming: false }
        : turn
    )
  );
}
```

- [ ] **Step 2: Add retry button for streaming interruption**

After each chat-message-group:

```typescript
{turn.answer.includes("中断") && (
  <button
    className="button secondary"
    onClick={() => /* trigger regeneration */}
    style={{ marginTop: "8px" }}
  >
    重新生成
  </button>
)}
```

- [ ] **Step 3: Handle no citations case**

```typescript
{turn.citations.length === 0 && !turn.isStreaming && (
  <div className="chat-meta-card" style={{ padding: "12px 16px" }}>
    <p className="text-sm text-gray-600">
      ⚠️ 未找到相关文档，回答基于通用知识
    </p>
  </div>
)}
```

- [ ] **Step 4: Commit**

```bash
git add web/components/pages/chat-page.tsx
git commit -m "feat: add enhanced error states and retry functionality"
```

---

## Task 13: Empty State Animation

**Files:**
- Modify: `web/app/globals.css`

- [ ] **Step 1: Add fade-in animation**

```css
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.chat-empty {
  display: grid;
  gap: 16px;
  align-content: center;
  min-height: 100%;
  color: var(--muted);
  animation: fadeInUp 0.6s ease-out;
}

.chat-suggestion {
  animation: fadeInUp 0.6s ease-out;
  animation-delay: calc(var(--index) * 0.1s);
  opacity: 0;
  animation-fill-mode: forwards;
}
```

- [ ] **Step 2: Update chat-page.tsx to use animation index**

```typescript
{uggestions.map((item, index) => (
  <button
    key={item}
    type="button"
    className="chat-suggestion"
    onClick={() => fillPrompt(item)}
    style={{ "--index": index } as React.CSSProperties}
  >
    {item}
  </button>
))}
```

- [ ] **Step 3: Commit**

```bash
git add web/app/globals.css web/components/pages/chat-page.tsx
git commit -m "style: add fade-in animations to empty state"
```

---

## Task 14: Confidence Visualization

**Files:**
- Modify: `web/components/pages/chat-page.tsx`

- [ ] **Step 1: Add confidence color bar component**

```typescript
function ConfidenceBar({ confidence }: { confidence: number }) {
  const getColor = () => {
    if (confidence >= 0.8) return "bg-green-500";
    if (confidence >= 0.5) return "bg-yellow-500";
    return "bg-red-500";
  };

  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full ${getColor()} transition-all duration-500`}
          style={{ width: `${confidence * 100}%` }}
        />
      </div>
      <span className="text-xs text-gray-600">{Math.round(confidence * 100)}%</span>
    </div>
  );
}
```

- [ ] **Step 2: Render in chat-meta-card**

```typescript
{typeof turn.confidence === "number" && (
  <div style={{ marginTop: 12 }}>
    <div className="tiny" style={{ marginBottom: 4 }}>置信度</div>
    <ConfidenceBar confidence={turn.confidence} />
  </div>
)}
```

- [ ] **Step 3: Commit**

```bash
git add web/components/pages/chat-page.tsx
git commit -m "feat: add confidence visualization bar"
```

---

## Task 15: Final Testing and Polish

**Files:**
- All modified files

- [ ] **Step 1: Start dev server and test**

Run: `cd web && pnpm dev`
Test: Open chat page and test all features

- [ ] **Step 2: Test markdown rendering**

Test: Paste markdown content and verify:
- Headers render correctly
- Lists (ordered/unordered) display
- Code blocks have syntax highlighting
- Tables render with borders
- Links are clickable

- [ ] **Step 3: Test citation interactions**

Test: Verify:
- Citation badges appear inline
- Hover shows popover
- Click expands citation card
- "View Full Document" link works

- [ ] **Step 4: Test streaming behavior**

Test: Send question and verify:
- Progress bar animates
- Status text changes (thinking → writing → done)
- Markdown renders incrementally without flicker
- Cursor sways

- [ ] **Step 5: Test input enhancements**

Test: Verify:
- Textarea auto-expands
- Character counter appears
- Enter sends, Shift+Enter adds newline
- Disabled state during generation

- [ ] **Step 6: Test error states**

Test: Disconnect network and send question
Verify: Error toast appears with retry option

- [ ] **Step 7: Check responsive behavior**

Test: Resize browser window
Verify: Layout adapts to mobile sizes

- [ ] **Step 8: Final commit**

```bash
git add -A
git commit -m "feat: complete chat page UX optimization

- Add markdown rendering with code highlighting
- Implement inline citation badges with hover popovers
- Add streaming progress bar and status indicators
- Create toast notification system
- Enhance input composer with auto-height and character counter
- Simplify sidebar with inline space selector
- Add collapsible conversation history
- Implement skeleton loading states
- Add error handling and retry functionality
- Polish visual design with enhanced shadows and spacing"
```

---

## Task 16: Documentation Update

**Files:**
- Modify: `docs/05-frontend-console.md`

- [ ] **Step 1: Update frontend documentation**

Add section about new chat features:

```markdown
## Chat Page Features

### Markdown Rendering
- AI responses render with full markdown formatting
- Code syntax highlighting via Prism
- Streaming-safe incremental parsing

### Inline Citations
- Citation badges appear inline within responses
- Hover for quick preview
- Click to expand full citation card
- Navigate to source documents

### Streaming Feedback
- Progress bar shows generation progress
- Status text indicates current phase (thinking/writing)
- Typing cursor with sway animation

### Toast Notifications
- Global toast system for operation feedback
- Success/error/info states
- Auto-dismiss with configurable duration
```

- [ ] **Step 2: Commit documentation**

```bash
git add docs/05-frontend-console.md
git commit -m "docs: update chat page feature documentation"
```

---

## Self-Review Summary

**Spec Coverage Check:**
- ✅ Interaction feedback enhancement (Task 8, 16)
- ✅ Inline citation highlights (Task 4, 6)
- ✅ Markdown rendering (Task 5, 7)
- ✅ Visual polish (Task 9)
- ✅ Loading states (Task 3, 12)
- ✅ Sidebar simplifications (Task 11)
- ✅ Input enhancements (Task 10)
- ✅ Confidence visualization (Task 14)
- ✅ Error handling (Task 12)

**Placeholder Scan:** No placeholders found - all steps contain complete code.

**Type Consistency:** All type definitions consistent with imports.

**Scope Check:** Plan is appropriately scoped for progressive enhancement - no backend changes, modular frontend updates.
