"use client";

import Link from "next/link";
import { useState } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { useConsoleData } from "@/hooks/use-console-data";
import { fetchJson } from "@/lib/api";
import { canCancelTask, canRetryTask, describeEvalSubmission, describeImportSubmission, getErrorMessage } from "@/lib/console";
import type { EvalRunResponse, SourceImportResponse } from "@/lib/types";

export function TasksPage() {
  const data = useConsoleData();
  const [status, setStatus] = useState("");

  async function handleCreateSpace() {
    try {
      const created = await data.createSpace();
      setStatus(`知识空间“${created.name}”已创建。`);
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  async function retryImport(jobId: string) {
    try {
      const result = await fetchJson<SourceImportResponse>(`/sources/jobs/${jobId}/retry`, { method: "POST" });
      setStatus(describeImportSubmission(result, "导入任务重试"));
      await data.refreshCollections(data.selectedSpaceId || data.spaces[0]?.id || "");
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  async function cancelImport(jobId: string) {
    try {
      const result = await fetchJson<SourceImportResponse>(`/sources/jobs/${jobId}/cancel`, { method: "POST" });
      setStatus(`导入任务已请求取消，job=${result.ingestion_job.id}。`);
      await data.refreshCollections(data.selectedSpaceId || data.spaces[0]?.id || "");
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  async function retryEval(runId: string) {
    try {
      const result = await fetchJson<EvalRunResponse>(`/eval/runs/${runId}/retry`, { method: "POST" });
      setStatus(describeEvalSubmission(result));
      await data.refreshCollections(data.selectedSpaceId || data.spaces[0]?.id || "");
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  async function cancelEval(runId: string) {
    try {
      const result = await fetchJson<EvalRunResponse>(`/eval/runs/${runId}/cancel`, { method: "POST" });
      setStatus(`评测任务已请求取消，run=${result.id}。`);
      await data.refreshCollections(data.selectedSpaceId || data.spaces[0]?.id || "");
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  return (
    <ConsoleShell
      activeHref="/tasks"
      title="Task Records"
      description="任务页专门承载导入与评测记录，并支持进入详情页查看 workflow、错误、关联文档和结果。"
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
            <h2>导入任务</h2>
            <div className="list">
              {data.ingestionJobs.map((item) => (
                <div className="list-item" key={item.ingestion_job.id}>
                  <Link href={`/tasks/ingestion/${item.ingestion_job.id}`} className="link-card">
                    <strong>{item.document?.title ?? item.ingestion_job.source_uri}</strong>
                    <div className="tiny">
                      status={item.ingestion_job.status} · attempt={item.ingestion_job.attempt_count}
                    </div>
                  </Link>
                  <div className="action-row">
                    {canRetryTask(item.ingestion_job.status) ? (
                      <button className="mini-button" type="button" onClick={() => retryImport(item.ingestion_job.id)}>
                        重试
                      </button>
                    ) : null}
                    {canCancelTask(item.ingestion_job.status) ? (
                      <button className="mini-button" type="button" onClick={() => cancelImport(item.ingestion_job.id)}>
                        取消
                      </button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="stack">
          <div className="card">
            <h2>评测任务</h2>
            <div className="list">
              {data.evalRuns.map((run) => (
                <div className="list-item" key={run.id}>
                  <Link href={`/tasks/evaluation/${run.id}`} className="link-card">
                    <strong>{run.id}</strong>
                    <div className="tiny">
                      status={run.status} · cases={run.completed_cases}/{run.total_cases}
                    </div>
                  </Link>
                  <div className="action-row">
                    {canRetryTask(run.status) ? (
                      <button className="mini-button" type="button" onClick={() => retryEval(run.id)}>
                        重试
                      </button>
                    ) : null}
                    {canCancelTask(run.status) ? (
                      <button className="mini-button" type="button" onClick={() => cancelEval(run.id)}>
                        取消
                      </button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </ConsoleShell>
  );
}
