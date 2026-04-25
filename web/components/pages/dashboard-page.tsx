"use client";

import Link from "next/link";
import { useState } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { useConsoleData } from "@/hooks/use-console-data";
import { formatMetric, getErrorMessage } from "@/lib/console";

export function DashboardPage() {
  const data = useConsoleData();
  const [status, setStatus] = useState("");

  async function handleCreateSpace() {
    try {
      const created = await data.createSpace();
      setStatus(`知识空间“${created.name}”已就绪。`);
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  const metrics = [
    { label: "Documents", value: data.summary?.document_count ?? 0 },
    { label: "Chunks", value: data.summary?.chunk_count ?? 0 },
    { label: "Answer Traces", value: data.summary?.trace_count ?? 0 },
    { label: "Eval Runs", value: data.summary?.eval_run_count ?? 0 }
  ];

  return (
    <ConsoleShell
      activeHref="/dashboard"
      title="Research-Grade RAG Dashboard"
      description="把运营总览、任务进度、最新问答和评测信号拆出来，先看全局，再进入具体页面处理。"
      spaces={data.spaces}
      selectedSpaceId={data.selectedSpaceId}
      onSelectedSpaceIdChange={data.setSelectedSpaceId}
      spaceName={data.spaceName}
      onSpaceNameChange={data.setSpaceName}
      onCreateSpace={handleCreateSpace}
      status={status || data.bootStatus}
    >
      <div className="card">
        <h2>运营总览</h2>
        <div className="metrics">
          {metrics.map((item) => (
            <div className="metric" key={item.label}>
              <span className="metric-label">{item.label}</span>
              <span className="metric-value">{item.value}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid">
        <div className="stack">
          <div className="card">
            <h2>快捷入口</h2>
            <div className="list">
              <Link href="/documents" className="list-item link-card">
                文档导入与详情
              </Link>
              <Link href="/chat" className="list-item link-card">
                研究问答与流式输出
              </Link>
              <Link href="/tasks" className="list-item link-card">
                导入任务与评测任务
              </Link>
              <Link href="/evaluation" className="list-item link-card">
                评测运行与指标回看
              </Link>
            </div>
          </div>
        </div>

        <div className="stack">
          <div className="card">
            <h2>最新任务</h2>
            <div className="list">
              {data.ingestionJobs.slice(0, 4).map((item) => (
                <Link key={item.ingestion_job.id} href={`/tasks/ingestion/${item.ingestion_job.id}`} className="list-item link-card">
                  <strong>{item.document?.title ?? item.ingestion_job.source_uri}</strong>
                  <div className="tiny">
                    import · status={item.ingestion_job.status} · attempt={item.ingestion_job.attempt_count}
                  </div>
                </Link>
              ))}
              {data.evalRuns.slice(0, 4).map((item) => (
                <Link key={item.id} href={`/tasks/evaluation/${item.id}`} className="list-item link-card">
                  <strong>{item.id}</strong>
                  <div className="tiny">
                    eval · status={item.status} · recall={formatMetric(item.summary.document_recall)}
                  </div>
                </Link>
              ))}
            </div>
          </div>

          <div className="card">
            <h2>最近查询</h2>
            <div className="list">
              {data.traces.slice(0, 5).map((trace) => (
                <Link key={trace.id} href="/history" className="list-item link-card">
                  <strong>{trace.question}</strong>
                  <div className="tiny">confidence {Math.round(trace.confidence * 100)}%</div>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </ConsoleShell>
  );
}
