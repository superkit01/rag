"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { useConsoleData } from "@/hooks/use-console-data";
import { useToast } from "@/hooks/use-toast";
import { fetchJson, streamAnswer } from "@/lib/api";
import { getErrorMessage } from "@/lib/console";
import { hasIncompleteMarkdown, preprocessCitations } from "@/lib/streaming-parser";
import type { AnswerResponse, Citation, FeedbackResponse, SourceDocument } from "@/lib/types";
import { CitationCard } from "@/components/ui/citation-card";
import { MarkdownRenderer } from "@/components/ui/markdown-renderer";
import { DocumentSkeleton } from "@/components/ui/skeleton";
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
};

export function ChatPage() {
  const data = useConsoleData();
  const { showToast } = useToast();
  const [status, setStatus] = useState("");
  const [question, setQuestion] = useState("核心数据变更需要满足哪些前置条件？");
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [renderedContent, setRenderedContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [answer, setAnswer] = useState<AnswerResponse | null>(null);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [sourceDocuments, setSourceDocuments] = useState<SourceDocument[]>([]);
  const [feedbackStatus, setFeedbackStatus] = useState("");
  const [turns, setTurns] = useState<ChatTurn[]>([]);

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
              const preprocessed = preprocessCitations(nextText);

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
          onDone(result) {
            setAnswer(result);
            const finalContent = preprocessCitations(result.answer);
            setStreamingText(finalContent);
            setRenderedContent(finalContent);
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
      setStatus(getErrorMessage(error));
      setTurns((current) =>
        current.map((turn) => (turn.id === turnId ? { ...turn, answer: getErrorMessage(error), isStreaming: false } : turn))
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

        <section className="chat-sidebar-card">
          <h3>知识空间</h3>
          <div className="field" style={{ marginTop: 0 }}>
            <label>当前命名空间</label>
            <select className="select" value={data.selectedSpaceId} onChange={(event) => data.setSelectedSpaceId(event.target.value)}>
              <option value="">自动选择默认空间</option>
              {data.spaces.map((space) => (
                <option key={space.id} value={space.id}>
                  {space.name}
                </option>
              ))}
            </select>
          </div>
          <p style={{ marginTop: 12 }}>这里可以直接切换命名空间，并配合文档过滤缩小问答范围。</p>
        </section>

        <section className="chat-sidebar-card">
          <h3>最近对话</h3>
          <div className="chat-history">
            {turns.length ? (
              turns
                .slice()
                .reverse()
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
          <div className="chat-doc-list" style={{ marginTop: 12 }}>
            {data.documents.map((document) => (
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
              <textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="给知识库发一条消息，或要求它基于引用整理结论..." />
              <div className="chat-composer-actions">
                <div className="chat-composer-meta">
                  {selectedDocumentIds.length ? `已限定 ${selectedDocumentIds.length} 份文档` : "当前使用整个命名空间"}
                </div>
                <button className="button" type="submit" disabled={isStreaming}>
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
