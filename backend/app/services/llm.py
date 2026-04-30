from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import hashlib
import json
import math
from collections.abc import Iterator

import httpx

from app.core.config import Settings
from app.services.indexing import SearchResult
from app.services.text_utils import shorten_text, tokenize_text


@dataclass(slots=True)
class ConversationTurn:
    question: str
    answer: str


class HashEmbeddingProvider:
    def __init__(self, dimensions: int = 128) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize_text(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = digest[0] % self.dimensions
            sign = 1.0 if digest[1] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [round(value / norm, 6) for value in vector]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class OpenAICompatibleEmbeddingProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        batch_size: int = 10,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.batch_size = max(1, batch_size)
        self.client = client or httpx.Client(timeout=30.0)

    def embed(self, text: str) -> list[float]:
        embeddings = self.embed_many([text])
        return embeddings[0] if embeddings else []

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            response = self.client.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "input": batch,
                },
            )
            self._raise_for_status(response)
            payload = response.json()
            data = payload.get("data")
            if not isinstance(data, list):
                raise ValueError("Embedding response is missing data array.")
            ordered = sorted(data, key=lambda item: item.get("index", 0))
            for item in ordered:
                embedding = item.get("embedding")
                if not isinstance(embedding, list):
                    raise ValueError("Embedding response item is missing embedding vector.")
                embeddings.append([float(value) for value in embedding])
        if len(embeddings) != len(texts):
            raise ValueError("Embedding response count does not match request input count.")
        return embeddings

    def _raise_for_status(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text.strip()
            if detail:
                raise ValueError(f"Embedding request failed: {response.status_code} {detail}") from exc
            raise


class AnswerGenerationProvider(ABC):
    @abstractmethod
    def generate(self, question: str, evidence: list[SearchResult], history: list[ConversationTurn] | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def stream_generate(
        self, question: str, evidence: list[SearchResult], history: list[ConversationTurn] | None = None
    ) -> Iterator[str]:
        raise NotImplementedError

    def rewrite_query(self, question: str, history: list[ConversationTurn]) -> str:
        del history
        return question

    def generate_session_title(self, question: str, answer: str) -> str | None:
        del question, answer
        return None


class HeuristicAnswerProvider(AnswerGenerationProvider):
    def generate(self, question: str, evidence: list[SearchResult], history: list[ConversationTurn] | None = None) -> str:
        del history
        return self._compose_answer(question, evidence)

    def stream_generate(
        self, question: str, evidence: list[SearchResult], history: list[ConversationTurn] | None = None
    ) -> Iterator[str]:
        del history
        answer = self._compose_answer(question, evidence)
        chunk_size = 48
        for start in range(0, len(answer), chunk_size):
            yield answer[start : start + chunk_size]

    def rewrite_query(self, question: str, history: list[ConversationTurn]) -> str:
        recent_questions = [turn.question for turn in history[-3:] if turn.question.strip()]
        return " ".join([*recent_questions, question]).strip() or question

    def generate_session_title(self, question: str, answer: str) -> str | None:
        del answer
        stripped = " ".join(question.split())
        if not stripped:
            return None
        return stripped[:20] + "..." if len(stripped) > 20 else stripped

    def _compose_answer(self, question: str, evidence: list[SearchResult]) -> str:
        if not evidence:
            return "当前知识库中没有找到足够证据来回答这个问题，建议缩小问题范围或补充文档。"

        claims = []
        for item in evidence[:3]:
            claims.append(shorten_text(item.content, limit=120))
        bullet_like = "；".join(claims)
        return f"根据当前检索到的可验证资料，关于“{question}”，可以确认的要点包括：{bullet_like}。如果需要更严格的结论，建议继续查看引用片段并补充上下文。"


class OpenAICompatibleAnswerProvider(AnswerGenerationProvider):
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.openai_base_url.rstrip("/")
        self.api_key = settings.openai_api_key
        self.model = settings.openai_chat_model
        self.fallback = HeuristicAnswerProvider()

    def generate(self, question: str, evidence: list[SearchResult], history: list[ConversationTurn] | None = None) -> str:
        if not self.api_key or not self.model:
            return self.fallback.generate(question, evidence, history)
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": "你是企业知识库问答助手。只能依据给定证据回答，不能编造；若证据不足，必须明确说明不足。",
                },
                {
                    "role": "user",
                    "content": self._build_prompt(question, evidence, history or []),
                },
            ],
        }
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            return content or self.fallback.generate(question, evidence, history)
        except Exception:
            return self.fallback.generate(question, evidence, history)

    def stream_generate(
        self, question: str, evidence: list[SearchResult], history: list[ConversationTurn] | None = None
    ) -> Iterator[str]:
        if not self.api_key or not self.model:
            yield from self.fallback.stream_generate(question, evidence, history)
            return

        payload = {
            "model": self.model,
            "temperature": 0.1,
            "stream": True,
            "messages": [
                {
                    "role": "system",
                    "content": "你是企业知识库问答助手。只能依据给定证据回答，不能编造；若证据不足，必须明确说明不足。",
                },
                {
                    "role": "user",
                    "content": self._build_prompt(question, evidence, history or []),
                },
            ],
        }
        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=30.0,
            ) as response:
                response.raise_for_status()
                emitted = False
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        payload_item = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = payload_item.get("choices")
                    if not isinstance(choices, list) or not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content") if isinstance(delta, dict) else None
                    if isinstance(content, str) and content:
                        emitted = True
                        yield content
                if emitted:
                    return
        except Exception:
            pass

        yield from self.fallback.stream_generate(question, evidence, history)

    def rewrite_query(self, question: str, history: list[ConversationTurn]) -> str:
        if not history:
            return question
        if not self.api_key or not self.model:
            return self.fallback.rewrite_query(question, history)
        rendered_history = self._render_history(history)
        payload = {
            "model": self.model,
            "temperature": 0.0,
            "messages": [
                {
                    "role": "system",
                    "content": "你负责把多轮追问改写成适合知识库检索的独立查询。只输出改写后的查询，不要解释。",
                },
                {
                    "role": "user",
                    "content": f"历史对话：\n{rendered_history}\n\n当前问题：{question}\n\n请输出一个简洁、完整、可检索的中文查询。",
                },
            ],
        }
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=15.0,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip()
            return content or self.fallback.rewrite_query(question, history)
        except Exception:
            return self.fallback.rewrite_query(question, history)

    def generate_session_title(self, question: str, answer: str) -> str | None:
        if not self.api_key or not self.model:
            return self.fallback.generate_session_title(question, answer)
        payload = {
            "model": self.model,
            "temperature": 0.0,
            "messages": [
                {
                    "role": "system",
                    "content": "你负责为企业知识库问答会话生成简短中文标题。只输出标题，不要解释。",
                },
                {
                    "role": "user",
                    "content": (
                        f"问题：{question}\n\n"
                        f"答案摘要：{shorten_text(answer, 500)}\n\n"
                        "请生成 8-20 个中文字符的标题，不要加引号，不要使用句号。"
                    ),
                },
            ],
        }
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=15.0,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip()
            title = content.strip("「」“”\"' ，。；;：:")
            return shorten_text(title, 24) if title else self.fallback.generate_session_title(question, answer)
        except Exception:
            return self.fallback.generate_session_title(question, answer)

    def _build_prompt(self, question: str, evidence: list[SearchResult], history: list[ConversationTurn]) -> str:
        rendered_history = self._render_history(history)
        rendered_evidence = "\n\n".join(
            [
                f"[证据{i + 1}] 文档={item.document_title} 章节={' / '.join(item.heading_path)} 内容={item.content}"
                for i, item in enumerate(evidence[:8])
            ]
        )
        history_section = f"历史对话（只用于理解上下文，不作为证据）：\n{rendered_history}\n\n" if rendered_history else ""
        return (
            f"{history_section}"
            f"当前问题：{question}\n\n"
            f"证据：\n{rendered_evidence}\n\n"
            "请输出中文答案，优先给出结论，再说明证据不足之处。引用依据只能来自本轮证据。"
        )

    def _render_history(self, history: list[ConversationTurn]) -> str:
        return "\n".join(
            [
                f"用户：{turn.question}\n助手：{shorten_text(turn.answer, 700)}"
                for turn in history
                if turn.question.strip() or turn.answer.strip()
            ]
        )


def build_answer_provider(settings: Settings) -> AnswerGenerationProvider:
    if settings.openai_api_key and settings.openai_chat_model:
        return OpenAICompatibleAnswerProvider(settings)
    return HeuristicAnswerProvider()


def build_embedding_provider(settings: Settings) -> HashEmbeddingProvider | OpenAICompatibleEmbeddingProvider:
    if settings.embedding_backend == "hash":
        return HashEmbeddingProvider(settings.embedding_dimensions)
    if settings.embedding_backend == "openai":
        if not settings.openai_api_key or not settings.openai_embedding_model:
            raise ValueError("EMBEDDING_BACKEND=openai requires OPENAI_API_KEY and OPENAI_EMBEDDING_MODEL.")
        return OpenAICompatibleEmbeddingProvider(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            batch_size=settings.openai_embedding_batch_size,
        )
    raise ValueError(f"Unsupported EMBEDDING_BACKEND: {settings.embedding_backend}")
