import type { EvalRunResponse, SourceImportResponse } from "@/lib/types";

export function formatMetric(value: number | undefined) {
  if (typeof value !== "number") {
    return "n/a";
  }
  return value.toFixed(2);
}

export function isActiveTaskStatus(status: string) {
  return ["pending", "running", "cancelling"].includes(status);
}

export function canRetryTask(status: string) {
  return ["failed", "cancelled"].includes(status);
}

export function canCancelTask(status: string) {
  return ["pending", "running"].includes(status);
}

export function getErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  return "请求失败，请检查后端服务和环境变量。";
}

export function describeImportSubmission(result: SourceImportResponse, label: string) {
  if (result.ingestion_job.status === "completed" && result.document) {
    return `${label}已完成，文档“${result.document.title}”共 ${result.document.chunks.length} 个片段。`;
  }
  if (result.ingestion_job.status === "failed") {
    return `${label}失败：${result.ingestion_job.error_message ?? "未知错误"}`;
  }
  return `${label}已提交，job=${result.ingestion_job.id}，当前状态 ${result.ingestion_job.status}。`;
}

export function describeEvalSubmission(result: EvalRunResponse) {
  if (result.status === "completed") {
    return `评测完成，document recall=${formatMetric(result.summary.document_recall)}，citation precision=${formatMetric(result.summary.citation_precision)}。`;
  }
  if (result.status === "failed") {
    return `评测失败：${String(result.error_message ?? result.summary.error_message ?? "未知错误")}`;
  }
  return `评测任务已提交，run=${result.id}，当前状态 ${result.status}。`;
}

export async function fileToBase64(file: File | null) {
  if (!file) {
    throw new Error("请先选择本地文件。");
  }
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  let binary = "";

  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  }

  return window.btoa(binary);
}

export function inferSourceTypeFromName(name: string) {
  const suffix = name.split(".").pop()?.toLowerCase();
  switch (suffix) {
    case "md":
    case "markdown":
      return "markdown";
    case "html":
    case "htm":
      return "html";
    case "txt":
      return "text";
    case "pdf":
      return "pdf";
    case "docx":
      return "docx";
    case "pptx":
      return "pptx";
    default:
      return "markdown";
  }
}
