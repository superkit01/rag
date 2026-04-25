"use client";

import { useState } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { useConsoleData } from "@/hooks/use-console-data";
import { getErrorMessage } from "@/lib/console";

export function NamespacePage() {
  const data = useConsoleData();
  const [status, setStatus] = useState("");

  async function handleCreateSpace() {
    try {
      const created = await data.createSpace();
      setStatus(`知识空间“${created.name}”已创建并设为当前空间。`);
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  return (
    <ConsoleShell
      activeHref="/namespace"
      title="Knowledge Space Namespace"
      description="把知识空间单独拆成 namespace 页面，方便明确当前上下文，而不是让空间选择散落在各个业务面板里。"
      spaces={data.spaces}
      selectedSpaceId={data.selectedSpaceId}
      onSelectedSpaceIdChange={data.setSelectedSpaceId}
      spaceName={data.spaceName}
      onSpaceNameChange={data.setSpaceName}
      onCreateSpace={handleCreateSpace}
      status={status || data.bootStatus}
    >
      <div className="card">
        <h2>知识空间列表</h2>
        <div className="list">
          {data.spaces.map((space) => (
            <div className={`list-item ${space.id === data.selectedSpaceId ? "active" : ""}`} key={space.id}>
              <strong>{space.name}</strong>
              <div className="tiny">{space.language}</div>
              <div className="tiny mono">{space.id}</div>
            </div>
          ))}
        </div>
      </div>
    </ConsoleShell>
  );
}
