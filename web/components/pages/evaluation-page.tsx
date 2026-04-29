"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { useConsoleData } from "@/hooks/use-console-data";
import { fetchJson } from "@/lib/api";
import { describeEvalSubmission, formatMetric, getErrorMessage } from "@/lib/console";
import type { EvalRunResponse } from "@/lib/types";

export function EvaluationPage() {
  const data = useConsoleData();
  const [status, setStatus] = useState("");
  const [evalName, setEvalName] = useState("");
  const [evalQuestion, setEvalQuestion] = useState("");
  const [expectedDocumentId, setExpectedDocumentId] = useState("");
  const [isEvalModalOpen, setIsEvalModalOpen] = useState(false);
  const [isEvalSubmitting, setIsEvalSubmitting] = useState(false);

  async function handleCreateSpace() {
    try {
      const created = await data.createSpace();
      setStatus(`知识空间“${created.name}”已创建。`);
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  async function handleRunEval(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isEvalSubmitting) {
      return;
    }
    setIsEvalSubmitting(true);
    setStatus("正在提交评测任务，请稍候。");
    try {
      const result = await fetchJson<EvalRunResponse>("/eval/runs", {
        method: "POST",
        body: JSON.stringify({
          knowledge_space_id: data.selectedSpaceId || undefined,
          knowledge_space_name: data.selectedSpaceId ? undefined : data.spaceName,
          cases: [
            {
              name: evalName,
              question: evalQuestion,
              expected_document_ids: expectedDocumentId ? [expectedDocumentId] : [],
              expected_snippets: []
            }
          ]
        })
      });
      setStatus(describeEvalSubmission(result));
      setIsEvalModalOpen(false);
      await data.refreshCollections(data.selectedSpaceId || data.spaces[0]?.id || "");
    } catch (error) {
      setStatus(getErrorMessage(error));
    } finally {
      setIsEvalSubmitting(false);
    }
  }

  return (
    <ConsoleShell
      activeHref="/evaluation"
      title="Evaluation Workspace"
      description="评测页独立运行单案例评测，并把历史 run 及其指标拆出来单独查看。"
      spaces={data.spaces}
      selectedSpaceId={data.selectedSpaceId}
      onSelectedSpaceIdChange={data.setSelectedSpaceId}
      spaceName={data.spaceName}
      onSpaceNameChange={data.setSpaceName}
      onCreateSpace={handleCreateSpace}
      status={status || data.bootStatus}
    >
      <div className="page-toolbar">
        <div className="page-toolbar-main">
          <h2>评测管理</h2>
          <div className="page-toolbar-meta">查看评测记录，并通过弹窗提交新的评测任务。</div>
        </div>
        <div className="row" style={{ alignItems: "center" }}>
          <button className="button" type="button" onClick={() => setIsEvalModalOpen(true)}>
            运行评测
          </button>
        </div>
      </div>

      <div className="card scroll-card">
        <div className="card-header">
          <h2>评测记录</h2>
          <div className="count-badge">{data.evalRuns.length} 条</div>
        </div>
        <div className="list scroll-list">
          {data.evalRuns.map((run) => (
            <Link key={run.id} href={`/tasks/evaluation/${run.id}`} className="list-item link-card">
              <strong>{run.id}</strong>
              <div className="tiny">
                状态：{run.status} · 召回率：{formatMetric(run.summary.document_recall)} · 引用准确率：{formatMetric(run.summary.citation_precision)}
              </div>
            </Link>
          ))}
        </div>
      </div>

      {isEvalModalOpen ? (
        <div className="modal-overlay" role="presentation">
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="run-eval-title"
          >
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <h2 id="run-eval-title" style={{ marginBottom: 0 }}>
                运行评测
              </h2>
              <button className="mini-button" type="button" onClick={() => setIsEvalModalOpen(false)} disabled={isEvalSubmitting}>
                关闭
              </button>
            </div>
            <form onSubmit={handleRunEval}>
              <div className="field">
                <label>评测名称</label>
                <input className="input" value={evalName} onChange={(event) => setEvalName(event.target.value)} disabled={isEvalSubmitting} />
              </div>
              <div className="field">
                <label>评测问题</label>
                <textarea
                  className="textarea"
                  style={{ minHeight: 100 }}
                  value={evalQuestion}
                  onChange={(event) => setEvalQuestion(event.target.value)}
                  disabled={isEvalSubmitting}
                />
              </div>
              <div className="field">
                <label>期望命中文档</label>
                <select
                  className="select"
                  value={expectedDocumentId}
                  onChange={(event) => setExpectedDocumentId(event.target.value)}
                  disabled={isEvalSubmitting}
                >
                  <option value="">不指定</option>
                  {data.documents.map((document) => (
                    <option key={document.id} value={document.id}>
                      {document.title}
                    </option>
                  ))}
                </select>
              </div>
              <div className="row" style={{ marginTop: 16, justifyContent: "flex-end" }}>
                <button className="button secondary" type="button" onClick={() => setIsEvalModalOpen(false)} disabled={isEvalSubmitting}>
                  取消
                </button>
                <button className="button" type="submit" disabled={isEvalSubmitting} aria-busy={isEvalSubmitting}>
                  {isEvalSubmitting ? "提交中..." : "提交评测"}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </ConsoleShell>
  );
}
