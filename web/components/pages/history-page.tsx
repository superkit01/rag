"use client";

import { useState } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { useConsoleData } from "@/hooks/use-console-data";
import { getErrorMessage } from "@/lib/console";

export function HistoryPage() {
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

  return (
    <ConsoleShell
      activeHref="/history"
      title="Answer History"
      description="历史查询单独成页，避免和实时聊天混在一起；每条记录都展示答案、引用来源和追问建议。"
      spaces={data.spaces}
      selectedSpaceId={data.selectedSpaceId}
      onSelectedSpaceIdChange={data.setSelectedSpaceId}
      spaceName={data.spaceName}
      onSpaceNameChange={data.setSpaceName}
      onCreateSpace={handleCreateSpace}
      status={status || data.bootStatus}
    >
      <div className="card scroll-card">
        <h2>历史查询</h2>
        <div className="list scroll-list">
          {data.traces.map((trace) => (
            <div className="list-item" key={trace.id}>
              <strong>{trace.question}</strong>
              <div className="tiny mono">{trace.id}</div>
              <div style={{ marginTop: 8 }}>{trace.answer}</div>
              <div className="tiny">置信度 {Math.round(trace.confidence * 100)}%</div>
              <div className="chip-row" style={{ marginTop: 8 }}>
                {trace.source_documents.map((item) => (
                  <div className="chip" key={item.document_id}>
                    {item.title}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </ConsoleShell>
  );
}
