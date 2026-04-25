"use client";

import { FormEvent, useState } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { useConsoleData } from "@/hooks/use-console-data";
import { getErrorMessage } from "@/lib/console";

export function NamespacePage() {
  const data = useConsoleData();
  const [status, setStatus] = useState("");
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [spacePendingDelete, setSpacePendingDelete] = useState<{ id: string; name: string } | null>(null);

  async function handleCreateSpace() {
    try {
      const created = await data.createSpace();
      setStatus(`知识空间“${created.name}”已创建并设为当前空间。`);
      setIsCreateModalOpen(false);
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  async function handleCreateSpaceSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await handleCreateSpace();
  }

  async function handleDeleteSpace() {
    if (!spacePendingDelete) {
      return;
    }
    try {
      const deleted = await data.deleteSpace(spacePendingDelete.id);
      setStatus(`知识空间“${deleted.name}”已删除。`);
      setSpacePendingDelete(null);
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
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ marginBottom: 0 }}>知识空间管理</h2>
          <button className="button" type="button" onClick={() => setIsCreateModalOpen(true)}>
            新增知识空间
          </button>
        </div>
      </div>

      <div className="card scroll-card">
        <h2>知识空间列表</h2>
        <div className="list scroll-list namespace-scroll-list">
          {data.spaces.map((space) => (
            <div className={`list-item ${space.id === data.selectedSpaceId ? "active" : ""}`} key={space.id}>
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <div className="link-card" style={{ flex: 1, minWidth: 0 }}>
                  <strong>{space.name}</strong>
                  <div className="tiny">{space.language}</div>
                  <div className="tiny mono">{space.id}</div>
                </div>
                <button
                  className="mini-button danger"
                  type="button"
                  onClick={() => setSpacePendingDelete({ id: space.id, name: space.name })}
                >
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {isCreateModalOpen ? (
        <div className="modal-overlay" role="presentation" onClick={() => setIsCreateModalOpen(false)}>
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-space-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <h2 id="create-space-title" style={{ marginBottom: 0 }}>
                新增知识空间
              </h2>
              <button className="mini-button" type="button" onClick={() => setIsCreateModalOpen(false)}>
                关闭
              </button>
            </div>
            <form onSubmit={handleCreateSpaceSubmit}>
              <div className="field">
                <label>空间名称</label>
                <input
                  className="input"
                  value={data.spaceName}
                  onChange={(event) => data.setSpaceName(event.target.value)}
                  placeholder="新知识空间名称"
                />
              </div>
              <div className="row" style={{ marginTop: 16, justifyContent: "flex-end" }}>
                <button className="button secondary" type="button" onClick={() => setIsCreateModalOpen(false)}>
                  取消
                </button>
                <button className="button" type="submit">
                  创建知识空间
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {spacePendingDelete ? (
        <div className="modal-overlay" role="presentation" onClick={() => setSpacePendingDelete(null)}>
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-space-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <h2 id="delete-space-title" style={{ marginBottom: 0 }}>
                删除知识空间
              </h2>
              <button className="mini-button" type="button" onClick={() => setSpacePendingDelete(null)}>
                关闭
              </button>
            </div>
            <div className="tiny" style={{ marginTop: 16 }}>
              确认删除知识空间“{spacePendingDelete.name}”吗？如果当前空间仍有关联文档、任务、问答或评测数据，系统会阻止删除。
            </div>
            <div className="row" style={{ marginTop: 16, justifyContent: "flex-end" }}>
              <button className="button secondary" type="button" onClick={() => setSpacePendingDelete(null)}>
                取消
              </button>
              <button className="button danger" type="button" onClick={handleDeleteSpace}>
                确认删除
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </ConsoleShell>
  );
}
