"""Gemini provider that rotates across an unbounded set of API keys.

Keys come from config/api_keys.txt (see config.load_api_keys). The number of keys
needs no code change. Each key is driven by its own single-key GeminiProvider in
failover mode, so a quota or rate-limit 429 raises QuotaExhausted; this wrapper
rotates keys round-robin and puts rate-limited keys on a timed cooldown. When all
keys are cooling, the wrapper waits for the soonest one to recover. When all keys
have failed too many times, QuotaExhausted propagates.
"""

from __future__ import annotations

import time

import config
from providers.base import LLMProvider, QuotaExhausted
from providers.gemini import GeminiProvider

COOLDOWN_SECONDS = 65
MAX_STRIKES = 12


class KeyPool:
    """Round-robin keys with timed cooldowns."""

    def __init__(self, keys):
        self._keys = []
        for key in keys:
            if key and key not in self._keys:
                self._keys.append(key)
        self._ready_at = {}
        self._strikes = {}
        self._index = 0

    @property
    def active(self):
        now = time.time()
        return [k for k in self._keys if self._ready_at.get(k, 0) <= now
                and self._strikes.get(k, 0) < MAX_STRIKES]

    def current(self):
        now = time.time()
        n = len(self._keys)
        for _ in range(n):
            key = self._keys[self._index % n]
            if self._ready_at.get(key, 0) <= now and self._strikes.get(key, 0) < MAX_STRIKES:
                return key
            self._index = (self._index + 1) % n
        return None

    def advance(self):
        self._index = (self._index + 1) % len(self._keys)

    def mark_cooling(self, key):
        self._strikes[key] = self._strikes.get(key, 0) + 1
        if self._strikes[key] >= MAX_STRIKES:
            self._ready_at[key] = float("inf")
        else:
            self._ready_at[key] = time.time() + COOLDOWN_SECONDS

    def clear_strikes(self, key):
        if key in self._strikes:
            del self._strikes[key]

    def soonest_ready(self):
        now = time.time()
        candidates = [t for t in self._ready_at.values() if t > now and t != float("inf")]
        return min(candidates) if candidates else None

    def status(self):
        now = time.time()
        active = len(self.active)
        cooling = len([k for k in self._keys
                       if self._ready_at.get(k, 0) > now
                       and self._strikes.get(k, 0) < MAX_STRIKES])
        exhausted = len([k for k in self._keys if self._strikes.get(k, 0) >= MAX_STRIKES])
        return {"total": len(self._keys), "active": active,
                "cooling": cooling, "exhausted": exhausted}


class MultiKeyGeminiProvider(LLMProvider):
    name = "gemini-multikey"

    def __init__(self, keys, model=None):
        keys = list(keys or [])
        if not keys:
            raise RuntimeError("no Gemini API keys provided")
        self.model = model or config.GEMINI_MODEL
        self.pool = KeyPool(keys)
        self._clients = {}
        self.key_switches = 0

    def _client(self, key):
        if key not in self._clients:
            self._clients[key] = GeminiProvider(api_key=key, model=self.model, failover=True)
        return self._clients[key]

    def _with_failover(self, call):
        """Run call(provider) against the current key, rotating round-robin."""
        while True:
            key = self.pool.current()
            if key is None:
                soonest = self.pool.soonest_ready()
                if soonest is None:
                    raise QuotaExhausted(
                        f"all {self.pool.status()['total']} Gemini keys exhausted this run")
                wait = soonest - time.time()
                if wait > 0:
                    print(f"[multikey] all keys cooling, waiting {wait:.0f}s...")
                    time.sleep(wait + 1)
                continue
            try:
                result = call(self._client(key))
                self.pool.clear_strikes(key)
                self.pool.advance()
                return result
            except QuotaExhausted:
                self.pool.mark_cooling(key)
                self.key_switches += 1
                self.pool.advance()
                status = self.pool.status()
                print(f"[multikey] key ...{key[-4:]} rate-limited "
                      f"(strike {self.pool._strikes[key]}/{MAX_STRIKES}); "
                      f"{status['active']} active, {status['cooling']} cooling")
                continue

    def text_json(self, system, user_text, schema=None, temperature=0.0, max_tokens=2048):
        return self._with_failover(
            lambda client: client.text_json(system, user_text, schema, temperature, max_tokens))

    def vision_json(self, system, user_text, images, schema=None, temperature=0.0, max_tokens=2048):
        return self._with_failover(
            lambda client: client.vision_json(system, user_text, images, schema, temperature, max_tokens))
