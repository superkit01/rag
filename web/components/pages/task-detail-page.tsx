"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { useConsoleData } from "@/hooks/use-console-data";
import { fetchJson } from "@/lib/api";
import { formatMetric, getErrorMessage } from "@/lib/console";
import type { EvalRunResponse, SourceImportResponse } from "@/lib/types";

type TaskDetailPageProps =
  | { kind: "ingestion"; taskId: string }
  | { kind: "evaluation"; taskId: string };

export function TaskDetailPage(props: TaskDetailPageProps) {
  const data = useConsoleData();
  const [status, setStatus] = useState("");
  const [importTask, setImportTask] = useState<SourceImportResponse | null>(null);
  const [evalTask, setEvalTask] = useState<EvalRunResponse | null>(null);

  useEffect(() => {
    void loadDetail();
  }, [props.kind, props.taskId]);

  async function handleCreateSpace() {
    try {
      const created = await data.createSpace();
      setStatus(`知识空间“${created.name}”已创建。`);
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  async function loadDetail() {
    try {
      if (props.kind === "ingestion") {
        const result = await fetchJson<SourceImportResponse>(`/sources/jobs/${props.taskId}`);
        setImportTask(result);
        setEvalTask(null);
      } else {
        const result = await fetchJson<EvalRunResponse>(`/eval/runs/${props.taskId}`);
        setEvalTask(result);
        setImportTask(null);
      }
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  return (
    <ConsoleShell
      activeHref="/tasks"
      title="Task Detail"
      description="任务详情页用来查看 workflow、错误、关联对象和结果，不需要再回到列表页猜上下文。"
      spaces={data.spaces}
      selectedSpaceId={data.selectedSpaceId}
      onSelectedSpaceIdChange={data.setSelectedSpaceId}
      spaceName={data.spaceName}
      onSpaceNameChange={data.setSpaceName}
      onCreateSpace={handleCreateSpace}
      status={status || data.bootStatus}
    >
      <Link href="/tasks" className="back-link">
        返回任务列表
      </Link>

      {importTask ? (
        <div className="card">
          <h2>导入任务详情</h2>
          <div className="tiny mono">{importTask.ingestion_job.id}</div>
          <div className="tiny">
            status={importTask.ingestion_job.status} · job_kind={importTask.ingestion_job.job_kind} · attempt={importTask.ingestion_job.attempt_count}
          </div>
          <div className="tiny mono">{importTask.ingestion_job.source_uri}</div>
          {importTask.ingestion_job.workflow_id ? <div className="tiny mono">workflow={importTask.ingestion_job.workflow_id}</div> : null}
          {importTask.ingestion_job.error_message ? <div className="tiny">error={importTask.ingestion_job.error_message}</div> : null}
          {importTask.document ? (
            <div className="list-item" style={{ marginTop: 16 }}>
              <strong>{importTask.document.title}</strong>
              <div className="tiny mono">{importTask.document.id}</div>
              <Link href={`/documents/${importTask.document.id}`} className="back-link">
                查看关联文档
              </Link>
            </div>
          ) : null}
        </div>
      ) : null}

      {evalTask ? (
        <div className="card">
          <h2>评测任务详情</h2>
          <div className="tiny mono">{evalTask.id}</div>
          <div className="tiny">
            status={evalTask.status} · cases={evalTask.completed_cases}/{evalTask.total_cases}
          </div>
          {evalTask.workflow_id ? <div className="tiny mono">workflow={evalTask.workflow_id}</div> : null}
          <div className="tiny">
            recall={formatMetric(evalTask.summary.document_recall)} · precision={formatMetric(evalTask.summary.citation_precision)} · avg confidence={formatMetric(evalTask.summary.avg_confidence)}
          </div>
          {evalTask.results.length ? (
            <div className="list" style={{ marginTop: 16 }}>
              {evalTask.results.map((result) => (
                <div className="list-item" key={result.name}>
                  <strong>{result.name}</strong>
                  <div>{result.question}</div>
                  <div className="tiny">
                    hit={String(result.hit)} · confidence={formatMetric(result.confidence)}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </ConsoleShell>
  );
}
