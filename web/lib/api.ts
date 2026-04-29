const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store",
    ...init
  });

  if (!response.ok) {
    const fallback = `Request failed with status ${response.status}`;
    let detail = fallback;
    try {
      const data = (await response.json()) as { detail?: string };
      detail = data.detail ?? fallback;
    } catch {
      const text = await response.text().catch(() => "");
      detail = text || fallback;
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

type StreamAnswerMeta = {
  confidence: number;
  citations: Array<{
    citation_id: string;
    document_id: string;
    document_title: string;
    fragment_id: string;
    section_title: string;
    heading_path: string[];
    page_number: number | null;
    quote: string;
    score: number;
  }>;
  source_documents: Array<{
    document_id: string;
    title: string;
    score: number;
  }>;
};

type StreamAnswerHandlers<TDone> = {
  onMeta: (meta: StreamAnswerMeta) => void;
  onDelta: (delta: string) => void;
  onDone: (result: TDone) => void;
};

export async function streamAnswer<TDone = unknown>(
  payload: Record<string, unknown>,
  handlers: StreamAnswerHandlers<TDone>
) {
  const response = await fetch(`${API_BASE_URL}/queries/answer/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload),
    cache: "no-store"
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(text || `Request failed with status ${response.status}`);
  }

  if (!response.body) {
    throw new Error("Stream response body is empty.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const eventBlock of events) {
      const lines = eventBlock.split("\n");
      const event = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
      const dataLine = lines.find((line) => line.startsWith("data:"))?.slice(5).trim();
      if (!event || !dataLine) {
        continue;
      }
      const parsed = JSON.parse(dataLine);
      if (event === "meta") {
        handlers.onMeta(parsed as StreamAnswerMeta);
      }
      if (event === "delta") {
        handlers.onDelta(parsed as string);
      }
      if (event === "done") {
        handlers.onDone(parsed as TDone);
      }
      if (event === "error") {
        throw new Error((parsed as { message?: string }).message ?? "Streaming request failed.");
      }
    }
  }
}

export type AnswerTrace = {
  id: string;
  knowledge_space_id: string;
  question: string;
  answer: string;
  confidence: number;
  citations: StreamAnswerMeta["citations"];
};

export async function fetchAnswerTraces(knowledgeSpaceId?: string): Promise<AnswerTrace[]> {
  const params = knowledgeSpaceId ? `?knowledge_space_id=${knowledgeSpaceId}` : "";
  return fetchJson<AnswerTrace[]>(`/answer-traces${params}`);
}
