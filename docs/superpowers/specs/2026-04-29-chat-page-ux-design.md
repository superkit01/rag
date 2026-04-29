# Chat Page UX Optimization Design

**Date**: 2026-04-29
**Status**: Approved
**Approach**: Progressive Enhancement (方案 A)

## Overview

Optimize the chat page user experience through progressive enhancements to interaction feedback and citation readability, while maintaining the existing layout structure.

## Goals

1. **Enhance interaction feedback** - Provide clear status indicators during streaming responses
2. **Improve citation readability** - Inline citation highlights with interactive details
3. **Visual polish** - Refine spacing, shadows, and component hierarchy
4. **Markdown rendering** - Format AI responses with proper markdown and code highlighting

## Current State Analysis

### Strengths
- Clean dual-pane layout (sidebar + main chat area)
- Streaming answer implementation exists
- Basic citation display with metadata
- Empty state with suggestions

### Pain Points
1. **Interaction feedback insufficient** - Only blinking cursor, no progress indication
2. **Citation readability poor** - Citations separated in cards below answer, hard to correlate with content
3. **No markdown rendering** - AI output displays as plain text

## Design

### 1. Interaction Feedback Enhancement

#### Streaming Progress Indicators

**Top Progress Bar**
- Thin progress bar above answer bubble during streaming
- Animates from 0% to 100% during generation
- Smooth ease-out animation

**Status Text**
- Dynamic status before cursor: "正在思考..." → "正在组织答案..." → "完成"
- Transitions based on streaming phase

**Typing Cursor**
- Change from `▋` to `|`
- Add subtle left-right sway animation

#### Toast Notification System

**Implementation**
- Global Toast component for operation results
- Floating notifications for feedback submission, errors, etc.

**Inline Status Tags**
- Gray tag "AI 正在回答..." next to questions being processed
- Disappears when answer completes

#### Confidence Visualization

**Color-coded Confidence Bar**
- Green (>= 0.8): High confidence
- Yellow (0.5-0.8): Medium confidence
- Red (< 0.5): Low confidence

### 2. Inline Citation Highlights

#### Citation Marker Syntax

```
根据《数据管理办法》第三条 {{cite:1}}，核心数据变更需要...
```

**Marker Style**
- Light blue badge, rounded square
- Shows citation number: `[1]`

**Interaction States**
- **Default**: Light blue badge
- **Hover**: Shows popover with:
  - Document title
  - Section title
  - Content preview (max 50 chars)
- **Click**: Expands full citation card

#### Citation Card Enhancement

**Improvements**
1. **Collapsible**: Each card can collapse/expand
2. **Jump Link**: "View Full Document" button linking to document detail page
3. **Relevance Score**: Color/icon indicating relevance (high/medium/low)

**Citation Navigation**
- Citation summary at end of answer
- Click to scroll to corresponding citation
- Click marker to highlight corresponding card

### 3. Markdown Rendering

#### Library Choice

**react-markdown** for core parsing with security configuration

**Features**
- GFM support (tables, strikethrough, task lists)
- XSS protection via allowed tags config
- Custom component mapping for citations

#### Code Highlighting

**prismjs** or **shiki** for syntax highlighting

**Supported Languages**
- Full language support via prism-react-renderer
- Theme: One Dark / GitHub Light

#### Streaming Markdown Challenge

**Problem**: Incomplete markdown causes render flicker during streaming

**Solutions**
1. **Buffered Rendering**: Accumulate small chunks before re-render
2. **Incremental Parsing**: Parse only new content
3. **Fallback**: Show raw text when incomplete code block detected

#### Citation Integration

**Post-processing Approach**
1. Markdown renders to HTML
2. Regex replace `{{cite:N}}` with `<CitationBadge id="N" />`
3. Component handles hover/click interactions

### 4. Visual Polish

#### Chat Bubble Optimization

**Adjustments**
- Enhanced shadow contrast, deeper shadow for user messages
- Unified border-radius: 16px (was 18px/22px)
- Increased spacing: 28px between message groups (was 22px)

#### Sidebar Simplification

**Knowledge Space Card**
- Move into top logo area
- Use inline select instead of separate card

**Recent Conversations**
- Make collapsible panel
- Default: show only 3 most recent

**Document Filtering**
- Keep existing layout
- Add search box to filter document list

#### Input Composer Enhancement

**Auto-height Textarea**
- Expands with content, max 200px

**Shortcut Hint**
- Placeholder: "Enter 发送，Shift+Enter 换行"

**Character Counter**
- Bottom-right character count
- Orange warning when > 500 chars

**Disabled State**
- Gray out + message "请等待当前回答完成..." during generation

### 5. Loading States

#### Skeleton Screens

**Apply to**
- Document list loading
- Space switching
- Conversation history

**Design**
- Pulse animation placeholders mimicking real layout
- 3-4 items for document list

#### Empty State

**Keep existing**, add minor tweaks:
- Fade-in animation
- Chat icon beside title

#### Error States (New)

**Network Error**
- Message: "连接失败，请检查网络后重试"
- Retry button

**Streaming Interrupt**
- Show partial content
- Message: "回答被中断，点击重新生成"
- Regenerate button

**No Citations**
- Message: "未找到相关文档，回答基于通用知识"

## Implementation Scope

| Area | Changes |
|------|---------|
| Interaction Feedback | Progress bar, status text, toast, confidence visualization |
| Markdown Rendering | react-markdown + prism + streaming parser |
| Inline Citations | Hover cards, collapsible cards, navigation |
| Visual Polish | Bubble shadows/spacing, sidebar simplification, input enhancements |
| Loading States | Skeletons, empty/error states |

## Non-Goals

- Major layout restructuring
- Backend API changes
- Mobile-first redesign (responsive improvements only)
