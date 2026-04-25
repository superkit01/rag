"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ConsoleShell } from "@/components/console-shell";
import { useConsoleData } from "@/hooks/use-console-data";
import { fetchJson } from "@/lib/api";
import { getErrorMessage } from "@/lib/console";
import type { DocumentRead, FragmentRead } from "@/lib/types";

export function DocumentDetailPage({ documentId }: { documentId: string }) {
  const data = useConsoleData();
  const [status, setStatus] = useState("");
  const [document, setDocument] = useState<DocumentRead | null>(null);
  const [fragment, setFragment] = useState<FragmentRead | null>(null);

  useEffect(() => {
    void loadDocument();
  }, [documentId]);

  async function handleCreateSpace() {
    try {
      const created = await data.createSpace();
      setStatus(`知识空间“${created.name}”已创建。`);
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  async function loadDocument() {
    try {
      const result = await fetchJson<DocumentRead>(`/documents/${documentId}`);
      setDocument(result);
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  async function viewFragment(fragmentId: string) {
    try {
      const result = await fetchJson<FragmentRead>(`/documents/${documentId}/fragments/${fragmentId}`);
      setFragment(result);
    } catch (error) {
      setStatus(getErrorMessage(error));
    }
  }

  return (
    <ConsoleShell
      activeHref="/documents"
      title="Document Detail"
      description="文档记录详情页展示 source、storage、chunk 和 fragment 预览。"
      spaces={data.spaces}
      selectedSpaceId={data.selectedSpaceId}
      onSelectedSpaceIdChange={data.setSelectedSpaceId}
      spaceName={data.spaceName}
      onSpaceNameChange={data.setSpaceName}
      onCreateSpace={handleCreateSpace}
      status={status || data.bootStatus}
    >
      {document ? (
        <div className="detail-page-stack">
          <div className="card">
            <Link href="/documents" className="back-link">
              返回
            </Link>
            <div className="detail-hero">
              <div>
                <h2>{document.title}</h2>
                <div className="tiny">文档详情与切片内容</div>
              </div>
              <div className="detail-badge">{document.status}</div>
            </div>
            <div className="detail-meta-grid">
              <div className="preview-box">
                <div className="tiny">文档 ID</div>
                <div className="tiny mono">{document.id}</div>
              </div>
              <div className="preview-box">
                <div className="tiny">来源类型</div>
                <div>{document.source_type}</div>
              </div>
              <div className="preview-box">
                <div className="tiny">切片数量</div>
                <div>{document.chunks.length}</div>
              </div>
            </div>
          </div>

          <div className="card detail-scroll-card">
            <h2>切片列表</h2>
            <div className="list detail-scroll-list">
              {document.chunks.map((chunk) => (
                <div className={`list-item ${fragment?.fragment_id === chunk.fragment_id ? "active" : ""}`} key={chunk.id}>
                  <strong>{chunk.section_title}</strong>
                  <div className="tiny">
                    片段 ID：{chunk.fragment_id} · 词元数：{chunk.token_count}
                  </div>
                  <div style={{ marginTop: 12 }}>{fragment?.fragment_id === chunk.fragment_id ? fragment.content : chunk.content}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </ConsoleShell>
  );
}
