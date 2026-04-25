"use client";

import { FormEvent, useState } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { useConsoleData } from "@/hooks/use-console-data";
import { fetchJson, streamAnswer } from "@/lib/api";
import { getErrorMessage } from "@/lib/console";
import type { AnswerResponse, Citation, FeedbackResponse, SourceDocument } from "@/lib/types";

export function ChatPage() {
  const data = useConsoleData();
  const [status, setStatus] = useState("");
  const [question, setQuestion] = useState("核心数据变更需要满足哪些前置条件？");
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [streamingText, setStreamingText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [answer, setAnswer] = useState<AnswerResponse | null>(null);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [sourceDocuments, setSourceDocuments] = useState<SourceDocument[]>([]);
  const [feedbackStatus, setFeedbackStatus] = useState("");

  async function handleCreateSpace() {
    try {
      const created = await data.createSpace();
      setStatus(`知识空间“${created.name}”已创建。`);
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  async function handleAsk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      setIsStreaming(true);
      setStreamingText("");
      setAnswer(null);
      setCitations([]);
      setSourceDocuments([]);
      setFeedbackStatus("");
      await streamAnswer<AnswerResponse>(
        {
          question,
          knowledge_space_id: data.selectedSpaceId || undefined,
          knowledge_space_name: data.selectedSpaceId ? undefined : data.spaceName,
          document_ids: selectedDocumentIds,
          max_citations: 4
        },
        {
          onMeta(meta) {
            setCitations(meta.citations);
            setSourceDocuments(meta.source_documents);
          },
          onDelta(delta) {
            setStreamingText((current) => current + delta);
          },
          onDone(result) {
            setAnswer(result);
            setStreamingText(result.answer);
            setCitations(result.citations);
            setSourceDocuments(result.source_documents);
            setStatus(`问答已完成，当前置信度 ${Math.round(result.confidence * 100)}%。`);
          }
        }
      );
      await data.refreshCollections(data.selectedSpaceId || data.spaces[0]?.id || "");
    } catch (error) {
      setStatus(getErrorMessage(error));
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

  return (
    <ConsoleShell
      activeHref="/chat"
      title="Streaming Research Chat"
      description="聊天页独立出来，并通过服务端流事件边生成边展示答案，不再等整段 JSON 一次性返回。"
      spaces={data.spaces}
      selectedSpaceId={data.selectedSpaceId}
      onSelectedSpaceIdChange={data.setSelectedSpaceId}
      spaceName={data.spaceName}
      onSpaceNameChange={data.setSpaceName}
      onCreateSpace={handleCreateSpace}
      status={status || data.bootStatus}
    >
      <div className="grid">
        <div className="stack">
          <div className="card">
            <h2>研究问答</h2>
            <form onSubmit={handleAsk}>
              <div className="field">
                <label>问题</label>
                <textarea className="textarea" style={{ minHeight: 120 }} value={question} onChange={(event) => setQuestion(event.target.value)} />
              </div>
              <div className="row" style={{ marginTop: 16 }}>
                <button className="button" type="submit" disabled={isStreaming}>
                  {isStreaming ? "正在流式生成..." : "开始问答"}
                </button>
                <button className="button ghost" type="button" onClick={() => setSelectedDocumentIds([])} disabled={isStreaming}>
                  清空文档过滤
                </button>
              </div>
            </form>

            {streamingText ? (
              <div className="answer-block">
                {answer ? <div className="tiny mono">Answer Trace ID: {answer.answer_trace_id}</div> : null}
                <div className="answer-copy">
                  {streamingText}
                  {isStreaming ? <span className="stream-cursor">▋</span> : null}
                </div>
                <div className="chip-row">
                  {sourceDocuments.map((source) => (
                    <div className="chip" key={source.document_id}>
                      {source.title}
                    </div>
                  ))}
                </div>
                <div className="list">
                  {citations.map((citation) => (
                    <div className="list-item" key={citation.citation_id}>
                      <strong>
                        {citation.document_title} · {citation.section_title}
                      </strong>
                      <div>{citation.quote}</div>
                      <div className="tiny">
                        fragment={citation.fragment_id} · score={citation.score.toFixed(3)}
                      </div>
                    </div>
                  ))}
                </div>
                {answer ? (
                  <form onSubmit={handleFeedback}>
                    <button className="button secondary" type="submit">
                      记录正向反馈
                    </button>
                    {feedbackStatus ? <div className="status">{feedbackStatus}</div> : null}
                  </form>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>

        <div className="stack">
          <div className="card">
            <h2>文档过滤</h2>
            <div className="list">
              {data.documents.map((document) => (
                <button
                  key={document.id}
                  className={`list-item selector-card ${selectedDocumentIds.includes(document.id) ? "active" : ""}`}
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
          </div>
        </div>
      </div>
    </ConsoleShell>
  );
}
