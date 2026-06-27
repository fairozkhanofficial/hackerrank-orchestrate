"""Disk-backed response cache and a provider wrapper that uses it.

The cache key is a hash of the full request (stage, model, system, user text,
image content, schema, temperature). Identical requests are served from disk with
no network call, which makes re-runs free, makes the run resumable after a
failure, and makes the two-config comparison affordable. Changing a prompt
changes the key automatically, so configs never collide.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from providers.base import ProviderResult, Usage


def _hash(*parts) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(repr(part).encode("utf-8"))
    return digest.hexdigest()[:40]


class Cache:
    def __init__(self, directory):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)

    def get(self, key):
        path = self.dir / f"{key}.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def put(self, key, value):
        (self.dir / f"{key}.json").write_text(
            json.dumps(value, ensure_ascii=False), encoding="utf-8")


class CachingProvider:
    """Wraps any provider and serves identical requests from the cache."""

    def __init__(self, inner, cache: Cache, enabled: bool = True):
        self.inner = inner
        self.cache = cache
        self.enabled = enabled
        self.name = f"cached:{inner.name}"
        self.live_calls = 0
        self.cache_hits = 0

    def _model(self):
        return getattr(self.inner, "model", self.inner.name)

    def _restore(self, payload):
        usage_data = payload.get("usage", {})
        usage = Usage(
            model=usage_data.get("model", ""),
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            image_count=usage_data.get("image_count", 0),
            latency_s=usage_data.get("latency_s", 0.0),
            cached=True,
        )
        return ProviderResult(data=payload.get("data", {}), usage=usage,
                              raw_text=payload.get("raw_text", ""))

    def _store(self, key, result):
        self.cache.put(key, {
            "data": result.data,
            "raw_text": result.raw_text,
            "usage": vars(result.usage),
        })

    def text_json(self, system, user_text, schema=None, temperature=0.0, max_tokens=2048):
        key = _hash("text", self._model(), system, user_text, schema, temperature)
        return self._run(key, lambda: self.inner.text_json(
            system, user_text, schema, temperature, max_tokens))

    def vision_json(self, system, user_text, images, schema=None, temperature=0.0, max_tokens=2048):
        image_sig = _hash(*[(img.image_id, img.b64) for img in images])
        key = _hash("vision", self._model(), system, user_text, image_sig, schema, temperature)
        return self._run(key, lambda: self.inner.vision_json(
            system, user_text, images, schema, temperature, max_tokens))

    def _run(self, key, call):
        if self.enabled:
            cached = self.cache.get(key)
            if cached is not None:
                self.cache_hits += 1
                return self._restore(cached)
        result = call()
        self.live_calls += 1
        if self.enabled:
            self._store(key, result)
        return result
