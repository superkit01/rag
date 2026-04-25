"use client";

import { useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";
import { isActiveTaskStatus } from "@/lib/console";
import type {
  AnswerTrace,
  DashboardSummary,
  DocumentListItem,
  DocumentListResponse,
  EvalRunResponse,
  KnowledgeSpace,
  SourceImportResponse
} from "@/lib/types";

const SELECTED_SPACE_STORAGE_KEY = "rag:selected-space-id";

export function useConsoleData() {
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [selectedSpaceId, setSelectedSpaceId] = useState("");
  const [spaceName, setSpaceName] = useState("专家研究台");
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [ingestionJobs, setIngestionJobs] = useState<SourceImportResponse[]>([]);
  const [traces, setTraces] = useState<AnswerTrace[]>([]);
  const [evalRuns, setEvalRuns] = useState<EvalRunResponse[]>([]);
  const [bootStatus, setBootStatus] = useState("正在准备工作台数据。");

  useEffect(() => {
    void refreshAll();
  }, []);

  useEffect(() => {
    if (!selectedSpaceId && spaces[0]?.id) {
      updateSelectedSpaceId(spaces[0].id);
    }
  }, [spaces, selectedSpaceId]);

  useEffect(() => {
    if (selectedSpaceId) {
      void refreshCollections(selectedSpaceId);
    }
  }, [selectedSpaceId]);

  useEffect(() => {
    if (!selectedSpaceId) {
      return;
    }
    const hasActiveJobs =
      ingestionJobs.some((item) => isActiveTaskStatus(item.ingestion_job.status)) ||
      evalRuns.some((item) => isActiveTaskStatus(item.status));
    if (!hasActiveJobs) {
      return;
    }
    const timer = window.setTimeout(() => {
      void refreshCollections(selectedSpaceId);
    }, 2000);
    return () => window.clearTimeout(timer);
  }, [selectedSpaceId, ingestionJobs, evalRuns]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const persistedSpaceId = window.localStorage.getItem(SELECTED_SPACE_STORAGE_KEY);
    if (persistedSpaceId) {
      setSelectedSpaceId(persistedSpaceId);
    }
  }, []);

  function updateSelectedSpaceId(spaceId: string) {
    setSelectedSpaceId(spaceId);
    if (typeof window !== "undefined") {
      if (spaceId) {
        window.localStorage.setItem(SELECTED_SPACE_STORAGE_KEY, spaceId);
      } else {
        window.localStorage.removeItem(SELECTED_SPACE_STORAGE_KEY);
      }
    }
  }

  async function refreshAll() {
    const loadedSpaces = await fetchJson<KnowledgeSpace[]>("/knowledge-spaces");
    setSpaces(loadedSpaces);
    const persistedSpaceId =
      typeof window !== "undefined" ? window.localStorage.getItem(SELECTED_SPACE_STORAGE_KEY) ?? "" : "";
    const nextSpaceId =
      loadedSpaces.find((space) => space.id === persistedSpaceId)?.id ?? loadedSpaces[0]?.id ?? "";
    if (nextSpaceId) {
      updateSelectedSpaceId(nextSpaceId);
      await refreshCollections(nextSpaceId);
    }
    setBootStatus("工作台已同步。");
  }

  async function refreshCollections(spaceId: string) {
    const query = spaceId ? `?knowledge_space_id=${spaceId}` : "";
    const [loadedSummary, loadedDocuments, loadedJobs, loadedTraces, loadedEvalRuns] = await Promise.all([
      fetchJson<DashboardSummary>(`/dashboard/summary${query}`),
      fetchJson<DocumentListResponse>(`/documents${query}`),
      fetchJson<SourceImportResponse[]>(`/sources/jobs${query}`),
      fetchJson<AnswerTrace[]>(`/answer-traces${query}`),
      fetchJson<EvalRunResponse[]>(`/eval/runs${query}`)
    ]);
    setSummary(loadedSummary);
    setDocuments(loadedDocuments.items);
    setIngestionJobs(loadedJobs);
    setTraces(loadedTraces);
    setEvalRuns(loadedEvalRuns);
  }

  async function createSpace() {
    const created = await fetchJson<KnowledgeSpace>("/knowledge-spaces", {
      method: "POST",
      body: JSON.stringify({
        name: spaceName,
        description: "面向专家研究问答的知识空间",
        language: "zh-CN"
      })
    });
    setSelectedSpaceId(created.id);
    await refreshAll();
    return created;
  }

  async function deleteSpace(spaceId: string) {
    const deleted = await fetchJson<KnowledgeSpace>(`/knowledge-spaces/${spaceId}`, {
      method: "DELETE"
    });
    const remainingSpaces = spaces.filter((space) => space.id !== spaceId);
    const nextSelectedSpaceId =
      remainingSpaces.find((space) => space.id === selectedSpaceId)?.id ??
      remainingSpaces[0]?.id ??
      "";
    updateSelectedSpaceId(nextSelectedSpaceId);
    await refreshAll();
    return deleted;
  }

  return {
    spaces,
    selectedSpaceId,
    setSelectedSpaceId: updateSelectedSpaceId,
    spaceName,
    setSpaceName,
    summary,
    documents,
    ingestionJobs,
    traces,
    evalRuns,
    bootStatus,
    refreshAll,
    refreshCollections,
    createSpace,
    deleteSpace
  };
}
