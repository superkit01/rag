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
      {importTask ? (
        <div className="detail-page-stack">
          <div className="card">
            <Link href="/tasks" className="back-link">
              返回任务列表
            </Link>
            <div className="detail-hero">
              <div>
                <h2>导入任务详情</h2>
                <div className="tiny">查看任务状态、来源地址和关联文档</div>
              </div>
              <div className="detail-badge">{importTask.ingestion_job.status}</div>
            </div>
            <div className="detail-meta-grid">
              <div className="preview-box">
                <div className="tiny">任务类型</div>
                <div>{importTask.ingestion_job.job_kind}</div>
              </div>
              <div className="preview-box">
                <div className="tiny">重试次数</div>
                <div>{importTask.ingestion_job.attempt_count}</div>
              </div>
              <div className="preview-box">
                <div className="tiny">任务 ID</div>
                <div className="tiny mono">{importTask.ingestion_job.id}</div>
              </div>
            </div>
          </div>

          <div className="grid">
            <div className="stack">
              <div className="card">
                <h2>任务信息</h2>
                <div className="tiny mono">{importTask.ingestion_job.source_uri}</div>
                {importTask.ingestion_job.workflow_id ? <div className="tiny mono">工作流 ID：{importTask.ingestion_job.workflow_id}</div> : null}
                {importTask.ingestion_job.error_message ? (
                  <div className="preview-box">
                    <div className="tiny">错误信息</div>
                    <div>{importTask.ingestion_job.error_message}</div>
                  </div>
                ) : null}
              </div>
            </div>

            <div className="stack">
              <div className="card">
                <h2>关联文档</h2>
                {importTask.document ? (
                  <div className="list-item">
                    <strong>{importTask.document.title}</strong>
                    <div className="tiny mono">{importTask.document.id}</div>
                    <Link href={`/documents/${importTask.document.id}`} className="back-link">
                      查看关联文档
                    </Link>
                  </div>
                ) : (
                  <div className="preview-box">
                    <div className="tiny">当前任务还没有可展示的关联文档。</div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {evalTask ? (
        <div className="detail-page-stack">
          <div className="card">
            <Link href="/tasks" className="back-link">
              返回任务列表
            </Link>
            <div className="detail-hero">
              <div>
                <h2>评测任务详情</h2>
                <div className="tiny">查看评测进度、指标结果与用例明细</div>
              </div>
              <div className="detail-badge">{evalTask.status}</div>
            </div>
            <div className="detail-meta-grid">
              <div className="preview-box">
                <div className="tiny">已完成用例</div>
                <div>{evalTask.completed_cases}/{evalTask.total_cases}</div>
              </div>
              <div className="preview-box">
                <div className="tiny">召回率</div>
                <div>{formatMetric(evalTask.summary.document_recall)}</div>
              </div>
              <div className="preview-box">
                <div className="tiny">引用准确率</div>
                <div>{formatMetric(evalTask.summary.citation_precision)}</div>
              </div>
            </div>
          </div>

          <div className="grid">
            <div className="stack">
              <div className="card">
                <h2>任务信息</h2>
                <div className="tiny mono">{evalTask.id}</div>
                {evalTask.workflow_id ? <div className="tiny mono">工作流 ID：{evalTask.workflow_id}</div> : null}
                <div className="tiny">平均置信度：{formatMetric(evalTask.summary.avg_confidence)}</div>
              </div>
            </div>

            <div className="stack">
              <div className="card">
                <h2>用例结果</h2>
                {evalTask.results.length ? (
                  <div className="list">
                    {evalTask.results.map((result) => (
                      <div className="list-item" key={result.name}>
                        <strong>{result.name}</strong>
                        <div>{result.question}</div>
                        <div className="tiny">
                          是否命中：{result.hit ? "是" : "否"} · 置信度：{formatMetric(result.confidence)}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="preview-box">
                    <div className="tiny">当前还没有产出用例结果。</div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </ConsoleShell>
  );
}
