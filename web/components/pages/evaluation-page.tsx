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
  const [evalName, setEvalName] = useState("变更控制验证");
  const [evalQuestion, setEvalQuestion] = useState("核心数据上线需要满足什么要求？");
  const [expectedDocumentId, setExpectedDocumentId] = useState("");

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
      await data.refreshCollections(data.selectedSpaceId || data.spaces[0]?.id || "");
    } catch (error) {
      setStatus(getErrorMessage(error));
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
      <div className="grid">
        <div className="stack">
          <div className="card">
            <h2>运行评测</h2>
            <form onSubmit={handleRunEval}>
              <div className="field">
                <label>评测名称</label>
                <input className="input" value={evalName} onChange={(event) => setEvalName(event.target.value)} />
              </div>
              <div className="field">
                <label>评测问题</label>
                <textarea className="textarea" style={{ minHeight: 100 }} value={evalQuestion} onChange={(event) => setEvalQuestion(event.target.value)} />
              </div>
              <div className="field">
                <label>期望命中文档</label>
                <select className="select" value={expectedDocumentId} onChange={(event) => setExpectedDocumentId(event.target.value)}>
                  <option value="">不指定</option>
                  {data.documents.map((document) => (
                    <option key={document.id} value={document.id}>
                      {document.title}
                    </option>
                  ))}
                </select>
              </div>
              <button className="button" type="submit">
                提交评测
              </button>
            </form>
          </div>
        </div>

        <div className="stack">
          <div className="card">
            <h2>评测记录</h2>
            <div className="list">
              {data.evalRuns.map((run) => (
                <Link key={run.id} href={`/tasks/evaluation/${run.id}`} className="list-item link-card">
                  <strong>{run.id}</strong>
                  <div className="tiny">
                    status={run.status} · recall={formatMetric(run.summary.document_recall)} · precision={formatMetric(run.summary.citation_precision)}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </ConsoleShell>
  );
}
