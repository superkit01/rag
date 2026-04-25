from __future__ import annotations

import html
from html.parser import HTMLParser
import re


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def tokenize_text(value: str) -> list[str]:
    tokens: list[str] = []
    latin_buffer: list[str] = []
    chinese_buffer: list[str] = []

    def flush_latin() -> None:
        if latin_buffer:
            tokens.append("".join(latin_buffer).lower())
            latin_buffer.clear()

    def flush_chinese() -> None:
        if not chinese_buffer:
            return
        tokens.extend(chinese_buffer)
        if len(chinese_buffer) > 1:
            tokens.extend(
                "".join(chinese_buffer[index : index + 2])
                for index in range(len(chinese_buffer) - 1)
            )
        chinese_buffer.clear()

    for char in value:
        if "\u4e00" <= char <= "\u9fff":
            flush_latin()
            chinese_buffer.append(char)
            continue
        if char.isalnum() or char == "_":
            flush_chinese()
            latin_buffer.append(char)
            continue
        flush_latin()
        flush_chinese()

    flush_latin()
    flush_chinese()
    return tokens


def estimate_token_count(value: str) -> int:
    return max(1, len(tokenize_text(value)))


def shorten_text(value: str, limit: int = 180) -> str:
    normalized = normalize_whitespace(value)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._parts.append(data.strip())

    def get_text(self) -> str:
        return " ".join(self._parts)


def strip_html(value: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(value)
    parser.close()
    return normalize_whitespace(html.unescape(parser.get_text()))
