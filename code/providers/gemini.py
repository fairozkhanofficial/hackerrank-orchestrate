"""Gemini 2.5 Flash provider over the Generative Language REST API.

Uses requests directly to avoid SDK version lock-in. Structured output is
requested with responseMimeType application/json plus an optional responseSchema.
Gemini 2.5 thinking is disabled for cheap, deterministic JSON. Transient errors
(rate limit, server errors) are retried with exponential backoff and jitter.
"""

from __future__ import annotations

import os
import random
import re
import threading
import time

import requests

import config
from providers.base import LLMProvider, ProviderResult, QuotaExhausted, Usage, extract_json

ENDPOINT = "https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent"
RETRYABLE_STATUS = (429, 500, 502, 503, 504)


def _is_quota_error(resp):
    """True when a 429 is a quota / rate-limit exhaustion (RESOURCE_EXHAUSTED)."""
    if resp.status_code != 429:
        return False
    try:
        if resp.json().get("error", {}).get("status") == "RESOURCE_EXHAUSTED":
            return True
    except ValueError:
        pass
    return "quota" in (resp.text or "").lower()


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key=None, model=None, failover=False):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.model = model or config.GEMINI_MODEL
        # In failover mode a quota 429 raises QuotaExhausted immediately, so a
        # multi-key wrapper can switch keys instead of waiting out the window.
        self.failover = failover
        # Per-key request spacing: each key has its own rate window.
        self._last_call = 0.0
        self._lock = threading.Lock()
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")

    def _generation_config(self, schema, temperature, max_tokens):
        cfg = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": config.GEMINI_THINKING_BUDGET},
        }
        if schema:
            cfg["responseSchema"] = schema
        return cfg

    def _post(self, parts, system, schema, temperature, max_tokens, image_count):
        body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": self._generation_config(schema, temperature, max_tokens),
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        url = ENDPOINT.format(version=config.GEMINI_API_VERSION, model=self.model)
        params = {"key": self.api_key}
        headers = {"Content-Type": "application/json"}

        self._throttle()
        last_error = None
        for attempt in range(config.MAX_RETRIES):
            start = time.time()
            try:
                resp = requests.post(url, params=params, headers=headers, json=body, timeout=120)
            except requests.RequestException as exc:
                last_error = str(exc)
                self._sleep(attempt)
                continue
            latency = time.time() - start
            if resp.status_code == 200:
                return self._parse(resp.json(), latency, image_count)
            if _is_quota_error(resp):
                retry_delay = self._retry_after(resp)
                if self.failover and (retry_delay is None or retry_delay > 120):
                    raise QuotaExhausted(f"key ...{self.api_key[-4:]} quota exhausted")
                if attempt < config.MAX_RETRIES - 1:
                    self._sleep(attempt, retry_delay)
                    continue
                raise QuotaExhausted("quota exhausted after retries")
            if resp.status_code in RETRYABLE_STATUS and attempt < config.MAX_RETRIES - 1:
                last_error = f"HTTP {resp.status_code}"
                self._sleep(attempt)
                continue
            raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:300]}")
        raise RuntimeError(f"Gemini API failed after {config.MAX_RETRIES} attempts: {last_error}")

    def _throttle(self):
        interval = 60.0 / max(1, config.REQUESTS_PER_MINUTE)
        with self._lock:
            wait = self._last_call + interval - time.time()
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.time()

    def _retry_after(self, resp):
        """Seconds the server asks us to wait, from RetryInfo or the message text."""
        try:
            details = resp.json().get("error", {}).get("details", [])
            for item in details:
                if item.get("@type", "").endswith("RetryInfo") and "retryDelay" in item:
                    return float(str(item["retryDelay"]).rstrip("s"))
        except (ValueError, AttributeError):
            pass
        match = re.search(r"retry in ([\d.]+)s", resp.text or "")
        return float(match.group(1)) if match else None

    def _sleep(self, attempt, server_delay=None):
        if server_delay is not None:
            delay = min(server_delay + 1.0, config.MAX_RETRY_DELAY_SECONDS)
        else:
            delay = config.BACKOFF_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
        time.sleep(delay)

    def _parse(self, payload, latency, image_count):
        meta = payload.get("usageMetadata", {})
        usage = Usage(
            model=self.model,
            input_tokens=meta.get("promptTokenCount", 0),
            output_tokens=meta.get("candidatesTokenCount", 0),
            image_count=image_count,
            latency_s=latency,
        )
        text = ""
        candidates = payload.get("candidates", [])
        if candidates:
            content = candidates[0].get("content", {})
            text = "".join(part.get("text", "") for part in content.get("parts", []))
        return ProviderResult(data=extract_json(text), usage=usage, raw_text=text)

    def text_json(self, system, user_text, schema=None, temperature=0.0, max_tokens=2048):
        return self._post([{"text": user_text}], system, schema, temperature, max_tokens, 0)

    def vision_json(self, system, user_text, images, schema=None, temperature=0.0, max_tokens=2048):
        # Each image is preceded by a text label carrying its image_id so the
        # model can tie every finding back to the correct image.
        parts = [{"text": user_text}]
        for img in images:
            parts.append({"text": f"[image_id: {img.image_id}]"})
            parts.append({"inline_data": {"mime_type": img.mime_type, "data": img.b64}})
        return self._post(parts, system, schema, temperature, max_tokens, len(images))
