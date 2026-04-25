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
      setSelectedSpaceId(spaces[0].id);
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

  async function refreshAll() {
    const loadedSpaces = await fetchJson<KnowledgeSpace[]>("/knowledge-spaces");
    setSpaces(loadedSpaces);
    const defaultSpaceId = loadedSpaces[0]?.id ?? "";
    if (defaultSpaceId) {
      setSelectedSpaceId(defaultSpaceId);
      await refreshCollections(defaultSpaceId);
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

  return {
    spaces,
    selectedSpaceId,
    setSelectedSpaceId,
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
    createSpace
  };
}
