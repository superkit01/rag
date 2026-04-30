import type { Citation } from "./types";

export type CitationDocumentGroup = {
  documentId: string;
  title: string;
  fileType: string;
  citations: Citation[];
};

export function getFileTypeLabel(title: string, sourceType?: string): string {
  const normalizedSource = sourceType?.trim().toLowerCase();
  const extension = title.includes(".") ? title.split(".").pop()?.toLowerCase() : undefined;
  const value = extension || normalizedSource;

  if (!value) return "FILE";
  if (value.includes("pdf")) return "PDF";
  if (value.includes("doc")) return "DOC";
  if (value.includes("xls") || value.includes("sheet")) return "XLS";
  if (value.includes("ppt")) return "PPT";
  if (value.includes("md")) return "MD";
  if (value.includes("txt") || value.includes("text")) return "TXT";

  return value.slice(0, 4).toUpperCase();
}

export function groupCitationsByDocument(citations: Citation[]): CitationDocumentGroup[] {
  const groups = new Map<string, CitationDocumentGroup>();

  for (const citation of citations) {
    const current = groups.get(citation.document_id);
    if (current) {
      current.citations.push(citation);
      continue;
    }

    groups.set(citation.document_id, {
      documentId: citation.document_id,
      title: citation.document_title || "未知文档",
      fileType: getFileTypeLabel(citation.document_title || ""),
      citations: [citation]
    });
  }

  return Array.from(groups.values());
}
