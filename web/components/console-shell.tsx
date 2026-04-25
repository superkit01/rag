"use client";

import Link from "next/link";
import { ReactNode } from "react";

import type { KnowledgeSpace } from "@/lib/types";

const NAV_ITEMS = [
  { href: "/namespace", label: "知识空间" },
  { href: "/dashboard", label: "总览" },
  { href: "/documents", label: "文档" },
  { href: "/tasks", label: "任务" },
  { href: "/evaluation", label: "评测" },
  { href: "/history", label: "历史问答" }
];

type ConsoleShellProps = {
  activeHref: string;
  title: string;
  description: string;
  spaces: KnowledgeSpace[];
  selectedSpaceId: string;
  onSelectedSpaceIdChange: (value: string) => void;
  spaceName: string;
  onSpaceNameChange: (value: string) => void;
  onCreateSpace: () => Promise<void> | void;
  status?: string;
  children: ReactNode;
};

export function ConsoleShell({
  activeHref,
  spaces,
  selectedSpaceId,
  onSelectedSpaceIdChange,
  status,
  children
}: ConsoleShellProps) {
  const visibleStatus =
    status && status !== "工作台已同步。" && status !== "正在准备工作台数据。"
      ? status
      : "";

  return (
    <main className="admin-shell">
      <aside className="admin-sider">
        <Link href="/dashboard" className="admin-brand">
          <span className="admin-brand-mark">R</span>
          <span>
            <strong>RAG Console</strong>
            <small>后台管理</small>
          </span>
        </Link>

        <nav className="admin-nav" aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <Link key={item.href} href={item.href} className={`admin-nav-item ${item.href === activeHref ? "active" : ""}`}>
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="admin-sider-footer">
          <div className="admin-sider-namespace">
            <label htmlFor="admin-namespace-select">命名空间</label>
            <select
              id="admin-namespace-select"
              className="select"
              value={selectedSpaceId}
              onChange={(event) => onSelectedSpaceIdChange(event.target.value)}
            >
              <option value="">自动选择默认空间</option>
              {spaces.map((space) => (
                <option key={space.id} value={space.id}>
                  {space.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </aside>

      <section className="admin-main">
        {visibleStatus ? <div className="status">{visibleStatus}</div> : null}
        <section className="page-stack">{children}</section>
      </section>
    </main>
  );
}
