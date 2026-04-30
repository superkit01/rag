"use client";

import { useEffect, useMemo, useState } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { useConsoleData } from "@/hooks/use-console-data";
import { fetchSessions, fetchSessionTraces, type AnswerTrace, type Session } from "@/lib/api";
import { getErrorMessage } from "@/lib/console";
import type { Citation, SourceDocument } from "@/lib/types";

type DocumentChip = {
  document_id: string;
  title: string;
};

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

function getTraceDocuments(trace: AnswerTrace): DocumentChip[] {
  const documents = new Map<string, DocumentChip>();

  for (const item of trace.source_documents as SourceDocument[]) {
    documents.set(item.document_id, {
      document_id: item.document_id,
      title: item.title
    });
  }

  if (!documents.size) {
    for (const citation of trace.citations as Citation[]) {
      documents.set(citation.document_id, {
        document_id: citation.document_id,
        title: citation.document_title || "未知文档"
      });
    }
  }

  return Array.from(documents.values());
}

function countUniqueDocuments(traces: AnswerTrace[]): number {
  const documentIds = new Set<string>();

  for (const trace of traces) {
    for (const document of getTraceDocuments(trace)) {
      documentIds.add(document.document_id);
    }
  }

  return documentIds.size;
}

export function HistoryPage() {
  const data = useConsoleData();
  const [status, setStatus] = useState("");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [selectedTraces, setSelectedTraces] = useState<AnswerTrace[]>([]);
  const [sessionStatus, setSessionStatus] = useState("");
  const [traceStatus, setTraceStatus] = useState("");
  const selectedSession = useMemo(
    () => sessions.find((session) => session.id === selectedSessionId) ?? null,
    [selectedSessionId, sessions]
  );
  const uniqueDocumentCount = useMemo(() => countUniqueDocuments(selectedTraces), [selectedTraces]);

  useEffect(() => {
    void loadSessions();
  }, [data.selectedSpaceId]);

  useEffect(() => {
    if (!selectedSessionId) {
      setSelectedTraces([]);
      return;
    }
    void loadSessionTraces(selectedSessionId);
  }, [selectedSessionId]);

  async function loadSessions() {
    try {
      setSessionStatus("正在加载历史会话...");
      setTraceStatus("");
      const sessionList = await fetchSessions(data.selectedSpaceId || undefined);
      setSessions(sessionList);
      setSelectedSessionId(sessionList[0]?.id ?? null);
      setSelectedTraces([]);
      setSessionStatus("");
    } catch (error) {
      setSessions([]);
      setSelectedSessionId(null);
      setSelectedTraces([]);
      setSessionStatus(getErrorMessage(error));
    }
  }

  async function loadSessionTraces(sessionId: string) {
    try {
      setTraceStatus("正在加载会话详情...");
      const traces = await fetchSessionTraces(sessionId);
      setSelectedTraces(traces);
      setTraceStatus("");
    } catch (error) {
      setSelectedTraces([]);
      setTraceStatus(getErrorMessage(error));
    }
  }

  async function handleCreateSpace() {
    try {
      const created = await data.createSpace();
      setStatus(`知识空间“${created.name}”已创建。`);
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  return (
    <ConsoleShell
      activeHref="/history"
      title="历史会话"
      description="按会话查看历史问答，每个会话包含多轮问题、答案和引用文档。"
      spaces={data.spaces}
      selectedSpaceId={data.selectedSpaceId}
      onSelectedSpaceIdChange={data.setSelectedSpaceId}
      spaceName={data.spaceName}
      onSpaceNameChange={data.setSpaceName}
      onCreateSpace={handleCreateSpace}
      status={status || data.bootStatus}
    >
      <div className="history-session-layout">
        <section className="card history-session-list-card">
          <div className="card-header">
            <div>
              <h2>历史会话</h2>
              <div className="tiny">{sessions.length ? `${sessions.length} 个会话` : "按当前知识空间筛选"}</div>
            </div>
          </div>

          <div className="history-session-list">
            {sessionStatus ? <div className="tiny">{sessionStatus}</div> : null}
            {!sessionStatus && !sessions.length ? <div className="tiny">暂无历史会话</div> : null}
            {sessions.map((session) => (
              <button
                key={session.id}
                className={`history-session-item ${selectedSessionId === session.id ? "active" : ""}`}
                type="button"
                onClick={() => setSelectedSessionId(session.id)}
              >
                <strong>{session.name}</strong>
                <span>{getRelativeTime(session.updated_at)}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="card history-session-detail-card">
          {selectedSession ? (
            <>
              <div className="history-session-detail-header">
                <div>
                  <h2>{selectedSession.name}</h2>
                  <div className="tiny">最近更新：{getRelativeTime(selectedSession.updated_at)}</div>
                </div>
                <div className="history-stat-row">
                  <span>{selectedTraces.length} 轮问答</span>
                  <span>{uniqueDocumentCount} 份引用文档</span>
                </div>
              </div>

              {traceStatus ? <div className="tiny">{traceStatus}</div> : null}
              {!traceStatus && !selectedTraces.length ? <div className="tiny">该会话暂无问答记录</div> : null}

              <div className="history-trace-list">
                {selectedTraces.map((trace, index) => {
                  const documents = getTraceDocuments(trace);
                  return (
                    <article className="history-trace-card" key={trace.id}>
                      <div className="tiny">问题 {index + 1}</div>
                      <h3>{trace.question}</h3>
                      <div className="history-trace-answer">{trace.answer}</div>
                      <div className="history-stat-row">
                        <span>置信度 {Math.round(trace.confidence * 100)}%</span>
                        <span>{documents.length} 份引用文档</span>
                      </div>
                      {documents.length ? (
                        <div className="chip-row">
                          {documents.map((document) => (
                            <div className="chip" key={document.document_id}>
                              {document.title}
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            </>
          ) : (
            <div className="history-empty-detail">
              <h2>请选择一个会话</h2>
              <p>选择左侧会话后，这里会展示多轮问答和引用文档。</p>
            </div>
          )}
        </section>
      </div>
    </ConsoleShell>
  );
}
