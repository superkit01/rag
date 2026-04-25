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
      setStatus(`已载入文档“${result.title}”。`);
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
      <Link href="/documents" className="back-link">
        返回文档列表
      </Link>

      {document ? (
        <div className="grid">
          <div className="stack">
            <div className="card">
              <h2>{document.title}</h2>
              <div className="tiny mono">{document.id}</div>
              <div className="tiny mono">{document.source_uri}</div>
              {document.storage_uri ? <div className="tiny mono">{document.storage_uri}</div> : null}
              <div className="tiny">
                {document.source_type} · {document.status} · chunks={document.chunks.length}
              </div>
            </div>

            <div className="card">
              <h2>Chunks</h2>
              <div className="list">
                {document.chunks.map((chunk) => (
                  <div className="list-item" key={chunk.id}>
                    <strong>{chunk.section_title}</strong>
                    <div className="tiny">
                      fragment={chunk.fragment_id} · tokens={chunk.token_count}
                    </div>
                    <div>{chunk.content}</div>
                    <div className="action-row">
                      <button className="mini-button" type="button" onClick={() => viewFragment(chunk.fragment_id)}>
                        查看片段
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="stack">
            <div className="card">
              <h2>片段预览</h2>
              {fragment ? (
                <div className="preview-box">
                  <div className="tiny">
                    {fragment.heading_path.join(" / ")} · fragment={fragment.fragment_id}
                  </div>
                  <div style={{ marginTop: 10 }}>{fragment.content}</div>
                </div>
              ) : (
                <div className="tiny">点击任一 chunk 查看对应片段。</div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </ConsoleShell>
  );
}
