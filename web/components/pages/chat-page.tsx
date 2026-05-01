"use client";

import Link from "next/link";
import { FormEvent, KeyboardEvent, useRef, useState, useEffect } from "react";
import { motion } from "framer-motion";

import { useConsoleData } from "@/hooks/use-console-data";
import { useToast } from "@/hooks/use-toast";
import { fetchJson, streamAnswer, fetchSessions, createSession, fetchSessionTraces, updateSession, type Session } from "@/lib/api";
import { groupCitationsByDocument, type CitationDocumentGroup } from "@/lib/chat-ui";
import { getErrorMessage } from "@/lib/console";
import { hasIncompleteMarkdown, preprocessCitations } from "@/lib/streaming-parser";
import type { AnswerResponse, Citation, DocumentListItem, DocumentRead, FeedbackResponse, SourceDocument } from "@/lib/types";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";
import { ToastContainer } from "@/components/ui/toast";

type ChatTurn = {
  id: string;
  session_id?: string;
  question: string;
  answer: string;
  citations: Citation[];
  sourceDocuments: SourceDocument[];
  confidence?: number;
  answerTraceId?: string;
  isStreaming?: boolean;
  hasError?: boolean;
};

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

function ConfidenceBar({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const color =
    pct >= 80 ? "#0f9f6e" : pct >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>置信度</span>
        <span style={{ fontSize: 13, color: "var(--muted)" }}>{pct}%</span>
      </div>
      <div style={{ height: 6, borderRadius: 3, background: "#e5e7eb", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", borderRadius: 3, background: color, transition: "width 0.6s ease" }} />
      </div>
    </div>
  );
}

type DocumentFilterDialogProps = {
  documents: DocumentListItem[];
  isOpen: boolean;
  isStreaming: boolean;
  query: string;
  selectedDocumentIds: string[];
  onClose: () => void;
  onQueryChange: (value: string) => void;
  onClear: () => void;
  onToggleDocument: (documentId: string) => void;
};

function DocumentFilterDialog({
  documents,
  isOpen,
  isStreaming,
  query,
  selectedDocumentIds,
  onClose,
  onQueryChange,
  onClear,
  onToggleDocument
}: DocumentFilterDialogProps) {
  if (!isOpen) return null;

  const normalizedQuery = query.trim().toLowerCase();
  const filteredDocuments = documents.filter((doc) => !normalizedQuery || doc.title.toLowerCase().includes(normalizedQuery));

  return (
    <div className="chat-modal-backdrop" onClick={onClose}>
      <section className="chat-document-modal" role="dialog" aria-modal="true" aria-labelledby="chat-document-filter-title" onClick={(event) => event.stopPropagation()}>
        <div className="chat-modal-header">
          <div>
            <h2 id="chat-document-filter-title">文档过滤</h2>
            <p>选择本轮问答限定使用的文档范围。</p>
          </div>
          <button className="chat-icon-button" type="button" onClick={onClose} aria-label="关闭文档过滤">
            ×
          </button>
        </div>

        <input
          className="input"
          type="text"
          placeholder="搜索文档..."
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          autoFocus
        />

        <div className="chat-document-filter-summary">
          <span>{selectedDocumentIds.length ? `已选择 ${selectedDocumentIds.length} 份文档` : "未选择文档，将使用整个命名空间"}</span>
          <button className="mini-button" type="button" onClick={onClear} disabled={isStreaming || selectedDocumentIds.length === 0}>
            清空
          </button>
        </div>

        <div className="chat-doc-list modal-list">
          {filteredDocuments.map((document) => (
            <button
              key={document.id}
              className={`chat-doc-button ${selectedDocumentIds.includes(document.id) ? "active" : ""}`}
              type="button"
              onClick={() => onToggleDocument(document.id)}
              disabled={isStreaming}
            >
              <strong>{document.title}</strong>
              <div className="tiny">
                {document.source_type} · {document.status}
              </div>
            </button>
          ))}
          {normalizedQuery && !filteredDocuments.length ? <div className="tiny">没有匹配的文档。</div> : null}
          {!documents.length ? <div className="tiny">当前知识空间暂无可过滤文档。</div> : null}
        </div>

        <div className="chat-modal-actions">
          <button className="button ghost" type="button" onClick={onClose}>
            取消
          </button>
          <button className="button" type="button" onClick={onClose}>
            确认
          </button>
        </div>
      </section>
    </div>
  );
}

function CitationSourceList({ citations, onOpenDocument }: { citations: Citation[]; onOpenDocument: (group: CitationDocumentGroup) => void }) {
  const groups = groupCitationsByDocument(citations);

  return (
    <div className="chat-source-list">
      {groups.map((group) => (
        <button key={group.documentId} className="chat-source-chip" type="button" onClick={() => onOpenDocument(group)}>
          <span className="chat-source-filetype">{group.fileType}</span>
          <span className="chat-source-title">{group.title}</span>
          {group.citations.length > 1 ? <span className="chat-source-count">{group.citations.length}</span> : null}
        </button>
      ))}
    </div>
  );
}

function DocumentDrawer({ source, onClose }: { source: CitationDocumentGroup | null; onClose: () => void }) {
  const [documentDetail, setDocumentDetail] = useState<DocumentRead | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "loaded" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!source) {
      setDocumentDetail(null);
      setStatus("idle");
      setErrorMessage("");
      return;
    }

    let isCurrent = true;
    setStatus("loading");
    setErrorMessage("");
    setDocumentDetail(null);

    fetchJson<DocumentRead>(`/documents/${source.documentId}`)
      .then((result) => {
        if (!isCurrent) return;
        setDocumentDetail(result);
        setStatus("loaded");
      })
      .catch((error) => {
        if (!isCurrent) return;
        setErrorMessage(getErrorMessage(error));
        setStatus("error");
      });

    return () => {
      isCurrent = false;
    };
  }, [source]);

  if (!source) return null;

  return (
    <div className="chat-drawer-layer">
      <button className="chat-drawer-scrim" type="button" aria-label="关闭文档抽屉" onClick={onClose} />
      <aside className="chat-document-drawer" aria-label="引用文档内容">
        <div className="chat-drawer-header">
          <div>
            <div className="chat-source-filetype">{source.fileType}</div>
            <h2>{documentDetail?.title || source.title}</h2>
            <p>
              {documentDetail ? `${documentDetail.source_type} · ${documentDetail.status}` : `${source.citations.length} 个引用片段`}
            </p>
          </div>
          <button className="chat-icon-button" type="button" onClick={onClose} aria-label="关闭文档内容">
            ×
          </button>
        </div>

        <div className="chat-drawer-body">
          <section className="chat-drawer-section">
            <h3>本次命中片段</h3>
            <div className="chat-hit-list">
              {source.citations.map((citation, index) => (
                <article className="chat-hit-card" key={citation.citation_id}>
                  <div className="tiny">
                    #{index + 1} · {citation.section_title || "未命名章节"}
                    {citation.page_number != null ? ` · 第 ${citation.page_number} 页` : ""}
                  </div>
                  <p>{citation.quote || "暂无引用文本"}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="chat-drawer-section">
            <h3>文档内容</h3>
            {status === "loading" ? <div className="tiny">正在加载文档内容...</div> : null}
            {status === "error" ? <div className="chat-drawer-error">{errorMessage}</div> : null}
            {status === "loaded" && documentDetail ? (
              <div className="chat-chunk-list">
                {documentDetail.chunks.map((chunk) => (
                  <article className="chat-chunk-card" key={chunk.id}>
                    <div className="tiny">
                      {chunk.section_title || chunk.fragment_id}
                      {chunk.page_number != null ? ` · 第 ${chunk.page_number} 页` : ""}
                    </div>
                    <p>{chunk.content}</p>
                  </article>
                ))}
                {!documentDetail.chunks.length ? <div className="tiny">该文档暂无切片内容。</div> : null}
              </div>
            ) : null}
          </section>
        </div>
      </aside>
    </div>
  );
}

export function ChatPage() {
  const data = useConsoleData();
  const { showToast } = useToast();
  const [status, setStatus] = useState("");
  const [question, setQuestion] = useState("");
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [streamingProgress, setStreamingProgress] = useState(0);
  const [streamingPhase, setStreamingPhase] = useState<"thinking" | "writing" | "done">("thinking");
  const [isStreaming, setIsStreaming] = useState(false);
  const [answer, setAnswer] = useState<AnswerResponse | null>(null);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [sourceDocuments, setSourceDocuments] = useState<SourceDocument[]>([]);
  const [feedbackStatus, setFeedbackStatus] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [isDocumentFilterOpen, setIsDocumentFilterOpen] = useState(false);
  const [docSearchQuery, setDocSearchQuery] = useState("");
  const [activeCitationSource, setActiveCitationSource] = useState<CitationDocumentGroup | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isComposingRef = useRef(false);

  // Load sessions on mount
  useEffect(() => {
    async function loadSessions() {
      try {
        const sessionList = await fetchSessions(data.selectedSpaceId || undefined);
        setSessions(sessionList);
      } catch (error) {
        console.error("Failed to load sessions:", error);
      }
    }
    loadSessions();
  }, [data.selectedSpaceId]);

  function adjustTextareaHeight() {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 240)}px`;
  }

  function handleNewSession() {
    setCurrentSessionId(null);
    setTurns([]);
    setQuestion("");
    setAnswer(null);
    setCitations([]);
    setSourceDocuments([]);
    setFeedbackStatus("");
    setStatus("");
    showToast("已准备新对话，发送第一条消息后创建会话", "success");
  }

  function getRelativeTime(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "刚刚";
    if (diffMins < 60) return `${diffMins}分钟前`;
    if (diffHours < 24) return `${diffHours}小时前`;
    return `${diffDays}天前`;
  }

  function generateSessionName(question: string): string {
    const truncated = question.length > 20 ? question.slice(0, 20) + "..." : question;
    return truncated;
  }

  function handleAbort() {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setIsStreaming(false);
    showToast("已中断回答", "info");
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    const isComposing = isComposingRef.current || event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229;
    if (event.key === "Enter" && !event.shiftKey && !isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  async function handleAsk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const currentQuestion = question.trim();
    if (!currentQuestion) {
      setStatus("请输入问题后再开始问答。");
      return;
    }

    // Create session if none active
    let activeSessionId = currentSessionId;
    if (!activeSessionId) {
      try {
        const newSession = await createSession({
          knowledge_space_id: data.selectedSpaceId || data.spaces[0]?.id || "",
          name: generateSessionName(currentQuestion)
        });
        activeSessionId = newSession.id;
        setCurrentSessionId(newSession.id);
        setSessions((current) => [newSession, ...current]);
      } catch (error) {
        showToast(`创建会话失败: ${getErrorMessage(error)}`, "error");
        return;
      }
    }

    const turnId = `${Date.now()}`;
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      setIsStreaming(true);
      setStreamingText("");
      setStreamingProgress(0);
      setStreamingPhase("thinking");
      setAnswer(null);
      setCitations([]);
      setSourceDocuments([]);
      setFeedbackStatus("");
      setTurns((current) => [
        ...current,
        {
          id: turnId,
          session_id: activeSessionId,
          question: currentQuestion,
          answer: "",
          citations: [],
          sourceDocuments: [],
          isStreaming: true
        }
      ]);

      // Clear input immediately after sending
      setQuestion("");

      await streamAnswer<AnswerResponse>(
        {
          question: currentQuestion,
          session_id: activeSessionId,
          knowledge_space_id: data.selectedSpaceId || undefined,
          knowledge_space_name: data.selectedSpaceId ? undefined : data.spaceName,
          document_ids: selectedDocumentIds,
          max_citations: 4
        },
        {
          onMeta(meta) {
            setCitations(meta.citations);
            setSourceDocuments(meta.source_documents);
            setTurns((current) =>
              current.map((turn) =>
                turn.id === turnId
                  ? {
                      ...turn,
                      answerTraceId: meta.answer_trace_id,
                      citations: meta.citations,
                      sourceDocuments: meta.source_documents
                    }
                  : turn
              )
            );
          },
          onDelta(delta) {
            setStreamingText((currentText) => {
              const nextText = currentText + delta;

              // Update progress based on content length
              setStreamingProgress(Math.min((nextText.length / 500) * 100, 95));
              if (nextText.length > 50) {
                setStreamingPhase("writing");
              }

              const preprocessed = preprocessCitations(nextText);

              setTurns((current) =>
                current.map((turn) =>
                  turn.id === turnId ? { ...turn, answer: preprocessed } : turn
                )
              );
              return nextText;
            });
          },
          onDone(result) {
            // Update session timestamp
            if (activeSessionId) {
              updateSession(activeSessionId, {}).catch(() => {
                // Silent fail - timestamp update not critical
              });
              // Refresh sessions list
              fetchSessions(data.selectedSpaceId || undefined).then(setSessions).catch(() => {});
            }

            setStreamingProgress(100);
            setStreamingPhase("done");
            setAnswer(result);
            const finalContent = preprocessCitations(result.answer);
            setStreamingText(finalContent);
            setCitations(result.citations);
            setSourceDocuments(result.source_documents);
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
        },
        abortController.signal
      );
      await data.refreshCollections(data.selectedSpaceId || data.spaces[0]?.id || "");
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      if (error instanceof Error && error.name === 'AbortError') {
        showToast("已中断回答", "info");
        setTurns((current) =>
          current.map((turn) =>
            turn.id === turnId
              ? { ...turn, isStreaming: false }
              : turn
          )
        );
      } else {
        showToast(`问答失败: ${errorMessage}，请重试。`, "error");
        setStatus(errorMessage);
        setTurns((current) =>
          current.map((turn) =>
            turn.id === turnId
              ? { ...turn, answer: errorMessage, isStreaming: false, hasError: true }
              : turn
          )
        );
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }

  async function handleFeedback(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!answer) {
      setFeedbackStatus("当前还没有可反馈的答案。");
      return;
    }
    try {
      const result = await fetchJson<FeedbackResponse>("/feedback", {
        method: "POST",
        body: JSON.stringify({
          answer_trace_id: answer.answer_trace_id,
          rating: 5,
          issue_type: "grounded",
          comments: "流式问答结果可读，引用清晰。"
        })
      });
      setFeedbackStatus(`反馈已记录，评分 ${result.rating}/5。`);
    } catch (error) {
      setFeedbackStatus(getErrorMessage(error));
    }
  }

  function toggleDocumentSelection(documentId: string) {
    setSelectedDocumentIds((current) =>
      current.includes(documentId) ? current.filter((id) => id !== documentId) : [...current, documentId]
    );
  }

  function handleRetry(questionToRetry: string) {
    setQuestion(questionToRetry);
    setTimeout(() => {
      const form = document.querySelector<HTMLFormElement>(".chat-composer");
      form?.requestSubmit();
    }, 0);
  }

  return (
    <main className="chat-layout">
      <aside className="chat-sidebar">
        <div className="chat-sidebar-top">
          <div className="chat-logo">
            <span className="chat-logo-mark">AI</span>
            <div>
              <strong>知识库对话</strong>
              <div className="tiny">独立对话页</div>
            </div>
          </div>
          <Link href="/dashboard" className="mini-button link-card">
            控制台
          </Link>
        </div>

        <section className="chat-sidebar-card" style={{ padding: "12px 14px" }}>
          <select
            className="select"
            value={data.selectedSpaceId}
            onChange={(event) => data.setSelectedSpaceId(event.target.value)}
            style={{ marginTop: 0 }}
          >
            <option value="">自动选择默认空间</option>
            {data.spaces.map((space) => (
              <option key={space.id} value={space.id}>
                {space.name}
              </option>
            ))}
          </select>
        </section>

        <section className="chat-sidebar-card chat-history-card">
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ marginBottom: 0 }}>历史会话</h3>
            <button
              className="mini-button"
              type="button"
              onClick={handleNewSession}
              disabled={isStreaming}
            >
              新建对话
            </button>
          </div>
          <div className="chat-history" style={{ marginTop: 12 }}>
            {sessions.length ? (
              sessions
                .slice()
                .map((session) => (
                  <div
                    key={session.id}
                    className={`chat-history-item ${currentSessionId === session.id ? "active" : ""}`}
                    onClick={async () => {
                      try {
                        const traces = await fetchSessionTraces(session.id);
                        setCurrentSessionId(session.id);
                        setTurns(traces.map((trace) => ({
                          id: trace.id,
                          session_id: session.id,
                          question: trace.question,
                          answer: trace.answer,
                          citations: trace.citations,
                          sourceDocuments: trace.source_documents || [],
                          confidence: trace.confidence,
                          answerTraceId: trace.id,
                          isStreaming: false
                        })));
                        showToast(`已加载会话: ${session.name}`, "success");
                      } catch (error) {
                        showToast(`加载会话失败: ${getErrorMessage(error)}`, "error");
                      }
                    }}
                    style={{ cursor: "pointer" }}
                  >
                    <strong>{session.name}</strong>
                    <div className="tiny">
                      点击加载 · {getRelativeTime(session.updated_at)}
                    </div>
                  </div>
                ))
            ) : (
              <div className="tiny">暂无历史会话</div>
            )}
          </div>
        </section>

        <section className="chat-sidebar-card chat-filter-card">
          <button className="chat-filter-button" type="button" onClick={() => setIsDocumentFilterOpen(true)}>
            <span>
              <strong>文档过滤</strong>
              <span className="tiny">{selectedDocumentIds.length ? `已限定 ${selectedDocumentIds.length} 份文档` : "当前使用整个命名空间"}</span>
            </span>
            <span className="chat-filter-arrow">›</span>
          </button>
        </section>
      </aside>

      <section className="chat-main">
        <header className="chat-main-header">
          <div>
            <h1>知识库对话</h1>
          </div>
          <div className="chat-header-actions">
            {status ? <div className="chat-sidebar-card" style={{ padding: "12px 14px" }}>{status}</div> : null}
            {feedbackStatus ? <div className="chat-sidebar-card" style={{ padding: "12px 14px" }}>{feedbackStatus}</div> : null}
          </div>
        </header>

        <section className="chat-content">
          <div className="chat-thread">
            {!turns.length ? (
              <section className="chat-empty">
                <h2>今天想先研究什么？</h2>
                <p>可以直接提问，系统会按当前知识空间与文档过滤条件给出带引用的回答。</p>
              </section>
            ) : null}

            {turns.map((turn) => (
              <div key={turn.id} className="chat-message-group">
                <div className="chat-message user">
                  <div className="chat-bubble">{turn.question}</div>
                </div>

                {turn.isStreaming && (
                  <div className="mb-2">
                    <ProgressBar progress={streamingProgress} />
                    <p className="text-xs text-gray-500 mt-1">
                      {streamingPhase === "thinking" && "正在思考..."}
                      {streamingPhase === "writing" && "正在组织答案..."}
                    </p>
                  </div>
                )}

                {turn.answer || turn.isStreaming ? (
                  <>
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
                          />
                        )}
                      </div>
                    </div>

                    {turn.citations.length > 0 && (
                      <div className="chat-message assistant">
                        <div className="chat-meta-card">
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="text-sm font-semibold">引用来源 ({turn.citations.length})</h4>
                          </div>
                          <CitationSourceList citations={turn.citations} onOpenDocument={setActiveCitationSource} />
                          {turn.confidence != null && <ConfidenceBar confidence={turn.confidence} />}
                        </div>
                      </div>
                    )}

                    {!turn.isStreaming && turn.citations.length === 0 && !turn.hasError && (
                      <div className="chat-message assistant">
                        <div className="chat-meta-card" style={{ borderColor: "rgba(245, 158, 11, 0.3)", background: "rgba(255, 251, 235, 0.95)" }}>
                          <p style={{ margin: 0, color: "#92400e", fontSize: 14 }}>
                            本次回答未引用任何文档来源，结论可能缺乏依据，建议调整问题或更换知识空间后重试。
                          </p>
                        </div>
                      </div>
                    )}
                  </>
                ) : null}

                {turn.hasError && !turn.isStreaming && (
                  <div className="chat-message assistant">
                    <button
                      className="button ghost"
                      type="button"
                      onClick={() => handleRetry(turn.question)}
                      style={{ fontSize: 14 }}
                    >
                      重试此问题
                    </button>
                  </div>
                )}
              </div>
            ))}

            {(streamingText || citations.length || sourceDocuments.length) && answer ? (
              <form onSubmit={handleFeedback}>
                <button className="button secondary" type="submit">
                  记录正向反馈
                </button>
              </form>
            ) : null}
          </div>

          <div className="chat-composer-wrap">
            <form className="chat-composer" onSubmit={handleAsk}>
              <textarea
                ref={textareaRef}
                value={question}
                onChange={(event) => {
                  setQuestion(event.target.value);
                  adjustTextareaHeight();
                }}
                onCompositionStart={() => {
                  isComposingRef.current = true;
                }}
                onCompositionEnd={() => {
                  isComposingRef.current = false;
                }}
                onKeyDown={handleComposerKeyDown}
                placeholder="给知识库发一条消息，或要求它基于引用整理结论..."
              />
              <div className="chat-composer-actions">
                <div className="chat-composer-meta">
                  {selectedDocumentIds.length ? `已限定 ${selectedDocumentIds.length} 份文档` : "当前使用整个命名空间"}
                  <span style={{ marginLeft: 8, fontSize: 12, color: question.length > 2000 ? "#ef4444" : "inherit" }}>
                    {question.length}/2000
                  </span>
                </div>
                {isStreaming ? (
                  <button
                    className="button"
                    type="button"
                    onClick={handleAbort}
                    style={{ backgroundColor: "#ef4444", width: 42, height: 42, padding: 0, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: 8, boxSizing: "border-box" }}
                    aria-label="停止"
                  >
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                      <rect x="5" y="5" width="14" height="14" rx="2" />
                    </svg>
                  </button>
                ) : (
                  <button
                    className="button"
                    type="submit"
                    disabled={!question.trim()}
                    style={{
                      width: 42,
                      height: 42,
                      padding: 0,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      borderRadius: 8,
                      boxSizing: "border-box",
                      ...(question.trim() ? {} : { opacity: 0.5, cursor: "default" })
                    }}
                    aria-label="发送"
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" xmlns="http://www.w3.org/2000/svg">
                      <path d="M22 2L11 13" />
                      <path d="M22 2L15 22L11 13L2 9L22 2Z" />
                    </svg>
                  </button>
                )}
              </div>
            </form>
          </div>
        </section>
      </section>
      <DocumentFilterDialog
        documents={data.documents}
        isOpen={isDocumentFilterOpen}
        isStreaming={isStreaming}
        query={docSearchQuery}
        selectedDocumentIds={selectedDocumentIds}
        onClose={() => setIsDocumentFilterOpen(false)}
        onQueryChange={setDocSearchQuery}
        onClear={() => setSelectedDocumentIds([])}
        onToggleDocument={toggleDocumentSelection}
      />
      <DocumentDrawer source={activeCitationSource} onClose={() => setActiveCitationSource(null)} />
      <ToastContainer />
    </main>
  );
}
