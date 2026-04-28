"use client";

import Link from "next/link";
import { ChangeEvent, FormEvent, useRef, useState } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { useConsoleData } from "@/hooks/use-console-data";
import { fetchJson } from "@/lib/api";
import { describeImportSubmission, fileToBase64, getErrorMessage, inferSourceTypeFromName } from "@/lib/console";
import type { DocumentDeleteResponse, SourceImportResponse } from "@/lib/types";

export function DocumentsPage() {
  const data = useConsoleData();
  const [status, setStatus] = useState("");
  const [importTitle, setImportTitle] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [documentPendingDelete, setDocumentPendingDelete] = useState<{ id: string; title: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function handleCreateSpace() {
    try {
      const created = await data.createSpace();
      setStatus(`知识空间“${created.name}”已创建。`);
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  async function handleImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const payload: Record<string, unknown> = {
        title: importTitle || selectedFile?.name,
        knowledge_space_id: data.selectedSpaceId || undefined,
        knowledge_space_name: data.selectedSpaceId ? undefined : data.spaceName,
        visibility_scope: "internal",
        source_acl_refs: [],
        uploaded_file_name: selectedFile?.name,
        uploaded_file_base64: await fileToBase64(selectedFile),
        source_type: inferSourceTypeFromName(selectedFile?.name ?? importTitle)
      };

      const result = await fetchJson<SourceImportResponse>("/sources/import", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      setStatus(describeImportSubmission(result, "导入任务"));
      setIsImportModalOpen(false);
      setSelectedFile(null);
      setImportTitle("");
      await data.refreshAll();
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    if (file) {
      setImportTitle(file.name);
      setStatus(`已选择本地文件“${file.name}”。`);
    }
  }

  async function handleDeleteDocument() {
    if (!documentPendingDelete) {
      return;
    }
    try {
      const deleted = await fetchJson<DocumentDeleteResponse>(`/documents/${documentPendingDelete.id}`, {
        method: "DELETE"
      });
      setStatus(`文档“${deleted.title}”已删除。`);
      setDocumentPendingDelete(null);
      await data.refreshAll();
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  return (
    <ConsoleShell
      activeHref="/documents"
      title="Document Intake & Records"
      description="上传入口只保留本地文件上传；文档记录可单独进入详情页查看 source、chunk 和 fragment。"
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
          <h2>文档管理</h2>
          <div className="page-toolbar-meta">集中查看文档记录，并通过弹窗导入本地文件。</div>
        </div>
        <div className="row" style={{ alignItems: "center" }}>
          <button className="button" type="button" onClick={() => setIsImportModalOpen(true)}>
            导入文档
          </button>
        </div>
      </div>

      <div className="card scroll-card">
        <div className="card-header">
          <h2>文档列表</h2>
          <div className="count-badge">{data.documents.length} 条</div>
        </div>
        <div className="list scroll-list">
          {data.documents.map((document) => (
            <div key={document.id} className="list-item">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <Link href={`/documents/${document.id}`} className="link-card" style={{ flex: 1, minWidth: 0 }}>
                  <strong>{document.title}</strong>
                  <div className="tiny">
                    {document.source_type} · {document.status} · {document.chunk_count} 个切片
                  </div>
                  <div className="tiny mono">{document.id}</div>
                </Link>
                <button
                  className="mini-button danger"
                  type="button"
                  onClick={() => setDocumentPendingDelete({ id: document.id, title: document.title })}
                >
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {isImportModalOpen ? (
        <div className="modal-overlay" role="presentation" onClick={() => setIsImportModalOpen(false)}>
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="import-document-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <h2 id="import-document-title" style={{ marginBottom: 0 }}>
                导入文档
              </h2>
              <button className="mini-button" type="button" onClick={() => setIsImportModalOpen(false)}>
                关闭
              </button>
            </div>
            <form onSubmit={handleImport}>
              <div className="field">
                <label>文档标题</label>
                <input
                  className="input"
                  value={importTitle}
                  onChange={(event) => setImportTitle(event.target.value)}
                  placeholder="默认使用文件名"
                />
              </div>
              <div className="field">
                <label>本地文件</label>
                <input
                  ref={fileInputRef}
                  type="file"
                  style={{ display: "none" }}
                  accept=".md,.markdown,.txt,.html,.htm,.pdf,.docx,.pptx"
                  onChange={handleFileChange}
                />
                <div className="row">
                  <button className="button secondary" type="button" onClick={() => fileInputRef.current?.click()}>
                    选择文件
                  </button>
                  <span className="hint">{selectedFile ? selectedFile.name : "尚未选择文件"}</span>
                </div>
              </div>
              <div className="row" style={{ marginTop: 16, justifyContent: "flex-end" }}>
                <button className="button secondary" type="button" onClick={() => setIsImportModalOpen(false)}>
                  取消
                </button>
                <button className="button" type="submit">
                  提交导入
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {documentPendingDelete ? (
        <div className="modal-overlay" role="presentation" onClick={() => setDocumentPendingDelete(null)}>
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-document-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <h2 id="delete-document-title" style={{ marginBottom: 0 }}>
                删除文档
              </h2>
              <button className="mini-button" type="button" onClick={() => setDocumentPendingDelete(null)}>
                关闭
              </button>
            </div>
            <div className="tiny" style={{ marginTop: 16 }}>
              确认删除文档“{documentPendingDelete.title}”吗？删除后文档记录和检索切片会一起移除。
            </div>
            <div className="row" style={{ marginTop: 16, justifyContent: "flex-end" }}>
              <button className="button secondary" type="button" onClick={() => setDocumentPendingDelete(null)}>
                取消
              </button>
              <button className="button danger" type="button" onClick={handleDeleteDocument}>
                确认删除
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </ConsoleShell>
  );
}
