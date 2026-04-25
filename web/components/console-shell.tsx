"use client";

import Link from "next/link";
import { FormEvent, ReactNode } from "react";

import type { KnowledgeSpace } from "@/lib/types";

const NAV_ITEMS = [
  { href: "/namespace", label: "Namespace" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/documents", label: "Documents" },
  { href: "/chat", label: "Chat" },
  { href: "/tasks", label: "Tasks" },
  { href: "/evaluation", label: "Evaluation" },
  { href: "/history", label: "History" }
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
  title,
  description,
  spaces,
  selectedSpaceId,
  onSelectedSpaceIdChange,
  spaceName,
  onSpaceNameChange,
  onCreateSpace,
  status,
  children
}: ConsoleShellProps) {
  async function handleCreateSpace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onCreateSpace();
  }

  return (
    <main className="shell">
      <section className="hero">
        <div className="hero-eyebrow">Enterprise Knowledge Intelligence</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </section>

      <section className="card" style={{ marginTop: 24 }}>
        <div className="nav-row">
          {NAV_ITEMS.map((item) => (
            <Link key={item.href} href={item.href} className={`nav-pill ${item.href === activeHref ? "active" : ""}`}>
              {item.label}
            </Link>
          ))}
        </div>

        <form onSubmit={handleCreateSpace} className="workspace-bar">
          <input
            className="input"
            value={spaceName}
            onChange={(event) => onSpaceNameChange(event.target.value)}
            placeholder="新知识空间名称"
          />
          <button className="button secondary" type="submit">
            创建知识空间
          </button>
          <select className="select" value={selectedSpaceId} onChange={(event) => onSelectedSpaceIdChange(event.target.value)}>
            <option value="">自动选择默认空间</option>
            {spaces.map((space) => (
              <option key={space.id} value={space.id}>
                {space.name}
              </option>
            ))}
          </select>
        </form>

        {status ? <div className="status">{status}</div> : null}
      </section>

      <section className="page-stack">{children}</section>
    </main>
  );
}
