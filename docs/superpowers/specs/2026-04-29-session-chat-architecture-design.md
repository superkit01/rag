# Session-Based Chat Architecture Design

**Date**: 2026-04-29
**Status**: Approved
**Approach**: Minimal Changes (Approach A)

## Overview

Add a session layer to the chat system where each session contains multiple Q&A pairs. Users can create new sessions, switch between sessions, and view session history.

## Goals

1. **Session Management** - Group related conversations into sessions
2. **Session History** - Browse and load previous sessions
3. **Minimal Disruption** - Preserve existing chat UX patterns

## Current State

**Existing Structure**
- Single `turns` array with all Q&A pairs
- "最近对话" shows individual AnswerTrace records
- No session concept - conversations run continuously

**Pain Points**
1. No way to group related conversations
2. History list becomes cluttered
3. Can't return to a previous conversation context

## Design

### 1. Data Model

```typescript
type Session = {
  id: string;
  name: string;              // Auto-generated from first question
  knowledge_space_id: string;
  created_at: string;
  updated_at: string;
}

type ChatTurn = {
  id: string;
  session_id: string;        // NEW: Link to parent session
  question: string;
  answer: string;
  citations: Citation[];
  sourceDocuments: SourceDocument[];
  confidence?: number;
  answerTraceId?: string;
  isStreaming?: boolean;
  hasError?: boolean;
}
```

### 2. Component Structure

**Sidebar Changes**
- Section title: "最近对话" → "历史会话"
- Session items display:
  - Session name (truncated question)
  - Trace count (e.g., "3 条对话")
  - Last updated time (relative: "2小时前")
- "新建对话" button at top of sidebar
- Click session → load its turns

**Main Chat Area**
- Session name shown in header when active
- Turns display unchanged (existing UX preserved)

**State Additions**
```typescript
const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
const [sessions, setSessions] = useState<Session[]>([]);
```

### 3. User Flows

**New Chat Flow**
```
1. User clicks "新建对话" button
2. API: POST /sessions with knowledge_space_id
3. Set currentSessionId = new session.id
4. Clear turns array
5. Focus textarea
6. First question → auto-generate session name
```

**Session Switching Flow**
```
1. User clicks session in sidebar
2. API: GET /sessions/{id}/traces
3. Set currentSessionId = session.id
4. Replace turns with fetched data
5. Scroll to bottom
```

**Continuing Session Flow**
```
1. User has active session
2. Submits new question
3. Stream answer as normal
4. API: PATCH /sessions/{id} (update updated_at)
5. Refresh sessions list for updated timestamp
```

**Auto-Generated Session Names**
```
- Source: First question in session
- Format: Truncate to ~20 characters, add "..."
- Example: "如何使用数据管理..." from "如何使用数据管理办法进行变更审批？"
- Fallback: "新对话" if question unavailable
```

### 4. API Endpoints

```typescript
// Create new session
POST /sessions
Body: { knowledge_space_id: string, name?: string }
Response: Session

// List sessions for knowledge space
GET /sessions?knowledge_space_id={id}
Response: Session[]

// Get turns for a session
GET /sessions/{id}/traces
Response: AnswerTrace[]

// Update session (name/timestamp)
PATCH /sessions/{id}
Body: { name?: string }
Response: Session
```

### 5. Error Handling

| Scenario | Behavior |
|----------|----------|
| Session creation fails | Toast: "创建会话失败，请重试" |
| Session load fails | Toast: "加载会话失败", retry button |
| Name generation fails | Default: "新对话 <timestamp>" |
| Empty session | Show existing empty state |

### 6. Implementation Scope

| Component | Changes |
|-----------|---------|
| Frontend State | Add sessions, currentSessionId |
| Sidebar UI | Rename section, add new chat button, update item format |
| Chat Page | Pass session_id to API calls |
| Backend | Add sessions table and API endpoints |
| Migration | Assign existing traces to sessions by date |

### 7. Visual Design

**Sidebar Session List Item**
```
┌─────────────────────────────┐
│ 如何使用数据管理...         │
│ 3 条对话 · 2小时前          │
└─────────────────────────────┘
```

**New Chat Button**
- Placed at top of "历史会话" section
- Icon + "新建对话" label
- Blue accent color

**Active Session Indicator**
- Highlighted background for selected session
- Left border accent (4px solid blue)

## Non-Goals

- Session sharing between users
- Session folders or nesting
- Session search/filtering (can add later)
- Mobile-specific session management
