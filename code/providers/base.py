"""Provider abstraction.

A provider turns a prompt, optionally with images, into a parsed JSON object plus
usage accounting. Every backend shares this interface so the rest of the pipeline
does not care which model answered.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


class QuotaExhausted(Exception):
    """Raised when a Gemini key (or all keys) has hit its quota or rate limit and
    no key is available to serve the request on this run."""


@dataclass
class Usage:
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    image_count: int = 0
    latency_s: float = 0.0
    cached: bool = False


@dataclass
class ProviderResult:
    data: dict
    usage: Usage
    raw_text: str = ""


def extract_json(text: str) -> dict:
    """Best-effort parse of a single JSON object from model text."""
    text = (text or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            text = text.split("\n", 1)[1]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return {}
    return {}


class LLMProvider:
    name = "base"

    def text_json(self, system, user_text, schema=None,
                  temperature=0.0, max_tokens=2048) -> "ProviderResult":
        raise NotImplementedError

    def vision_json(self, system, user_text, images, schema=None,
                    temperature=0.0, max_tokens=2048) -> "ProviderResult":
        raise NotImplementedError
