"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { useConsoleData } from "@/hooks/use-console-data";
import { fetchJson } from "@/lib/api";
import { canCancelTask, canRetryTask, describeEvalSubmission, describeImportSubmission, getErrorMessage } from "@/lib/console";
import type { EvalRunResponse, SourceImportResponse } from "@/lib/types";

type TaskFilter = "all" | "ingestion" | "evaluation";

type UnifiedTaskItem =
  | {
      type: "ingestion";
      id: string;
      createdAt: string;
      title: string;
      subtitle: string;
      href: string;
      status: string;
      onRetry: () => Promise<void>;
      onCancel: () => Promise<void>;
    }
  | {
      type: "evaluation";
      id: string;
      createdAt: string;
      title: string;
      subtitle: string;
      href: string;
      status: string;
      onRetry: () => Promise<void>;
      onCancel: () => Promise<void>;
    };

export function TasksPage() {
  const data = useConsoleData();
  const [status, setStatus] = useState("");
  const [taskFilter, setTaskFilter] = useState<TaskFilter>("all");

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

  const taskItems = useMemo<UnifiedTaskItem[]>(() => {
    const ingestionItems: UnifiedTaskItem[] = data.ingestionJobs.map((item) => ({
      type: "ingestion",
      id: item.ingestion_job.id,
      createdAt: item.ingestion_job.created_at,
      title: item.document?.title ?? item.ingestion_job.source_uri,
      subtitle: `状态：${item.ingestion_job.status} · 重试次数：${item.ingestion_job.attempt_count}`,
      href: `/tasks/ingestion/${item.ingestion_job.id}`,
      status: item.ingestion_job.status,
      onRetry: () => retryImport(item.ingestion_job.id),
      onCancel: () => cancelImport(item.ingestion_job.id)
    }));

    const evalItems: UnifiedTaskItem[] = data.evalRuns.map((run) => ({
      type: "evaluation",
      id: run.id,
      createdAt: run.created_at,
      title: run.id,
      subtitle: `状态：${run.status} · 已完成用例：${run.completed_cases}/${run.total_cases}`,
      href: `/tasks/evaluation/${run.id}`,
      status: run.status,
      onRetry: () => retryEval(run.id),
      onCancel: () => cancelEval(run.id)
    }));

    return [...ingestionItems, ...evalItems].sort((left, right) => right.createdAt.localeCompare(left.createdAt));
  }, [data.ingestionJobs, data.evalRuns]);

  const filteredTaskItems = taskItems.filter((item) => taskFilter === "all" || item.type === taskFilter);

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
      <div className="page-toolbar">
        <div className="page-toolbar-main">
          <h2>任务管理</h2>
          <div className="page-toolbar-meta">统一查看导入任务和评测任务，并支持按类型筛选。</div>
        </div>
        <div className="field" style={{ marginTop: 0, width: 220 }}>
          <label>任务类型</label>
          <select className="select" value={taskFilter} onChange={(event) => setTaskFilter(event.target.value as TaskFilter)}>
            <option value="all">全部任务</option>
            <option value="ingestion">导入任务</option>
            <option value="evaluation">评测任务</option>
          </select>
        </div>
      </div>

      <div className="card scroll-card">
        <div className="card-header">
          <h2>任务列表</h2>
          <div className="count-badge">{filteredTaskItems.length} 条</div>
        </div>
        <div className="list scroll-list">
          {filteredTaskItems.map((item) => (
            <div className="list-item" key={`${item.type}-${item.id}`}>
              <Link href={item.href} className="link-card">
                <div className="row" style={{ alignItems: "center" }}>
                  <strong style={{ marginBottom: 0 }}>{item.title}</strong>
                  <div className="chip">{item.type === "ingestion" ? "导入任务" : "评测任务"}</div>
                </div>
                <div className="tiny">{item.subtitle}</div>
                <div className="tiny mono">{item.id}</div>
              </Link>
              <div className="action-row">
                {canRetryTask(item.status) ? (
                  <button className="mini-button" type="button" onClick={() => void item.onRetry()}>
                    重试
                  </button>
                ) : null}
                {canCancelTask(item.status) ? (
                  <button className="mini-button" type="button" onClick={() => void item.onCancel()}>
                    取消
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      </div>
    </ConsoleShell>
  );
}
