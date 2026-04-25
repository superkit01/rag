"use client";

import Link from "next/link";
import { ChangeEvent, FormEvent, useRef, useState } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { useConsoleData } from "@/hooks/use-console-data";
import { fetchJson } from "@/lib/api";
import { describeImportSubmission, fileToBase64, getErrorMessage, inferSourceTypeFromName } from "@/lib/console";
import type { SourceImportResponse } from "@/lib/types";

type ImportMode = "inline" | "upload";

export function DocumentsPage() {
  const data = useConsoleData();
  const [status, setStatus] = useState("");
  const [importMode, setImportMode] = useState<ImportMode>("inline");
  const [importTitle, setImportTitle] = useState("企业研发管理办法.md");
  const [inlineContent, setInlineContent] = useState(
    "# 研发管理办法\n\n## 目标\n企业研发流程强调需求评审、架构评审和上线复盘。\n\n## 风险控制\n任何涉及核心数据的变更都需要回滚预案和发布窗口审批。"
  );
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
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
        title: importTitle,
        knowledge_space_id: data.selectedSpaceId || undefined,
        knowledge_space_name: data.selectedSpaceId ? undefined : data.spaceName,
        visibility_scope: "internal",
        source_acl_refs: []
      };
      if (importMode === "inline") {
        payload.inline_content = inlineContent;
        payload.source_type = "markdown";
      } else {
        payload.uploaded_file_name = selectedFile?.name;
        payload.uploaded_file_base64 = await fileToBase64(selectedFile);
        payload.source_type = inferSourceTypeFromName(selectedFile?.name ?? importTitle);
      }

      const result = await fetchJson<SourceImportResponse>("/sources/import", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      setStatus(describeImportSubmission(result, "导入任务"));
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

  return (
    <ConsoleShell
      activeHref="/documents"
      title="Document Intake & Records"
      description="上传入口只保留内联内容和本地文件上传；文档记录可单独进入详情页查看 source、chunk 和 fragment。"
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
            <h2>文档导入</h2>
            <form onSubmit={handleImport}>
              <div className="field">
                <label>文档标题</label>
                <input className="input" value={importTitle} onChange={(event) => setImportTitle(event.target.value)} />
              </div>
              <div className="field">
                <label>导入方式</label>
                <select className="select" value={importMode} onChange={(event) => setImportMode(event.target.value as ImportMode)}>
                  <option value="inline">内联内容</option>
                  <option value="upload">本地文件上传</option>
                </select>
              </div>
              {importMode === "inline" ? (
                <div className="field">
                  <label>文档内容</label>
                  <textarea className="textarea" value={inlineContent} onChange={(event) => setInlineContent(event.target.value)} />
                </div>
              ) : (
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
              )}
              <div className="row" style={{ marginTop: 16 }}>
                <button className="button" type="submit">
                  提交导入
                </button>
              </div>
            </form>
          </div>
        </div>

        <div className="stack">
          <div className="card">
            <h2>文档记录</h2>
            <div className="list">
              {data.documents.map((document) => (
                <Link key={document.id} href={`/documents/${document.id}`} className="list-item link-card">
                  <strong>{document.title}</strong>
                  <div className="tiny">
                    {document.source_type} · {document.status} · {document.chunk_count} chunks
                  </div>
                  <div className="tiny mono">{document.id}</div>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </ConsoleShell>
  );
}
