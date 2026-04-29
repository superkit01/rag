"use client";

import Link from "next/link";
import { FormEvent, useRef, useState } from "react";
import { motion } from "framer-motion";

import { useConsoleData } from "@/hooks/use-console-data";
import { useToast } from "@/hooks/use-toast";
import { fetchJson, streamAnswer } from "@/lib/api";
import { getErrorMessage } from "@/lib/console";
import { hasIncompleteMarkdown, preprocessCitations } from "@/lib/streaming-parser";
import type { AnswerResponse, Citation, FeedbackResponse, SourceDocument } from "@/lib/types";
import { CitationCard } from "@/components/ui/citation-card";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";
import { ToastContainer } from "@/components/ui/toast";

type ChatTurn = {
  id: string;
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

export function ChatPage() {
  const data = useConsoleData();
  const { showToast } = useToast();
  const [status, setStatus] = useState("");
  const [question, setQuestion] = useState("核心数据变更需要满足哪些前置条件？");
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
  const [showAllHistory, setShowAllHistory] = useState(false);
  const [docSearchQuery, setDocSearchQuery] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function adjustTextareaHeight() {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 240)}px`;
  }

  async function handleAsk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const currentQuestion = question.trim();
    if (!currentQuestion) {
      setStatus("请输入问题后再开始问答。");
      return;
    }

    const turnId = `${Date.now()}`;
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
          question: currentQuestion,
          answer: "",
          citations: [],
          sourceDocuments: [],
          isStreaming: true
        }
      ]);

      await streamAnswer<AnswerResponse>(
        {
          question: currentQuestion,
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

              if (!hasIncompleteMarkdown(preprocessed)) {
                setTurns((current) =>
                  current.map((turn) =>
                    turn.id === turnId ? { ...turn, answer: preprocessed } : turn
                  )
                );
              }
              return nextText;
            });
          },
          onDone(result) {
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
        }
      );
      await data.refreshCollections(data.selectedSpaceId || data.spaces[0]?.id || "");
      setQuestion("");
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      showToast(`问答失败: ${errorMessage}，请重试。`, "error");
      setStatus(errorMessage);
      setTurns((current) =>
        current.map((turn) =>
          turn.id === turnId
            ? { ...turn, answer: errorMessage, isStreaming: false, hasError: true }
            : turn
        )
      );
    } finally {
      setIsStreaming(false);
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

  function fillPrompt(nextQuestion: string) {
    setQuestion(nextQuestion);
  }

  function handleRetry(questionToRetry: string) {
    setQuestion(questionToRetry);
    setTimeout(() => {
      const form = document.querySelector<HTMLFormElement>(".chat-composer");
      form?.requestSubmit();
    }, 0);
  }

  const suggestions = [
    "总结当前知识空间里与发布审批相关的硬性前置条件。",
    "按文档出处整理核心数据变更的风险控制要求。",
    "如果证据不足，请明确指出缺失了哪些制度或流程文档。",
    "对比最近导入的文档里，哪些内容最适合做上线前检查清单？"
  ];

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

        <section className="chat-sidebar-card">
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ marginBottom: 0 }}>最近对话</h3>
            {turns.length > 3 && (
              <button className="mini-button" type="button" onClick={() => setShowAllHistory(!showAllHistory)}>
                {showAllHistory ? "收起" : `全部 (${turns.length})`}
              </button>
            )}
          </div>
          <div className="chat-history" style={{ marginTop: 12 }}>
            {turns.length ? (
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
            ) : (
              <div className="tiny">还没有开始会话，先试一个研究问题。</div>
            )}
          </div>
        </section>

        <section className="chat-sidebar-card">
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ marginBottom: 0 }}>文档过滤</h3>
            <button className="mini-button" type="button" onClick={() => setSelectedDocumentIds([])} disabled={isStreaming}>
              清空
            </button>
          </div>
          <input
            className="input"
            type="text"
            placeholder="搜索文档..."
            value={docSearchQuery}
            onChange={(event) => setDocSearchQuery(event.target.value)}
            style={{ marginTop: 12, fontSize: 13, padding: "8px 12px" }}
          />
          <div className="chat-doc-list" style={{ marginTop: 12 }}>
            {data.documents
              .filter((doc) => !docSearchQuery || doc.title.toLowerCase().includes(docSearchQuery.toLowerCase()))
              .map((document) => (
                <button
                  key={document.id}
                  className={`chat-doc-button ${selectedDocumentIds.includes(document.id) ? "active" : ""}`}
                  type="button"
                  onClick={() => toggleDocumentSelection(document.id)}
                >
                  <strong>{document.title}</strong>
                  <div className="tiny">
                    {document.source_type} · {document.status}
                  </div>
                </button>
              ))}
            {docSearchQuery && !data.documents.filter((doc) => doc.title.toLowerCase().includes(docSearchQuery.toLowerCase())).length && (
              <div className="tiny">没有匹配的文档。</div>
            )}
          </div>
        </section>
      </aside>

      <section className="chat-main">
        <header className="chat-main-header">
          <div>
            <h1>Chat with your knowledge base</h1>
            <p>独立于后台管理入口的研究对话页，保留流式回答、引用证据和知识空间上下文。</p>
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
                <p>可以直接提问，也可以用下面的提示词快速开始。系统会按当前知识空间与文档过滤条件给出带引用的回答。</p>
                <div className="chat-suggestions">
                  {suggestions.map((item) => (
                    <button key={item} type="button" className="chat-suggestion" onClick={() => fillPrompt(item)}>
                      {item}
                    </button>
                  ))}
                </div>
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
                      <div className="space-y-2">
                        {turn.citations.map((citation, index) => (
                          <CitationCard key={citation.citation_id} citation={citation} index={index + 1} />
                        ))}
                      </div>
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
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
                placeholder="给知识库发一条消息，或要求它基于引用整理结论..."
              />
              <div className="chat-composer-actions">
                <div className="chat-composer-meta">
                  {selectedDocumentIds.length ? `已限定 ${selectedDocumentIds.length} 份文档` : "当前使用整个命名空间"}
                  <span style={{ marginLeft: 8, fontSize: 12, color: question.length > 2000 ? "#ef4444" : "inherit" }}>
                    {question.length}/2000
                  </span>
                </div>
                <button
                  className="button"
                  type="submit"
                  disabled={isStreaming || !question.trim()}
                  style={isStreaming || !question.trim() ? { opacity: 0.5, cursor: "default" } : undefined}
                >
                  {isStreaming ? "生成中..." : "发送"}
                </button>
              </div>
            </form>
          </div>
        </section>
      </section>
      <ToastContainer />
    </main>
  );
}
