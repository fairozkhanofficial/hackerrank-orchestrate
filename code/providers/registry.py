"""Select the model backend.

This build uses one shared backend for both the vision and decision roles, so a
single MultiKeyGeminiProvider tracks key exhaustion globally. Falls back to the
mock backend when no Gemini key is available, so the pipeline always runs.
"""

from __future__ import annotations

import config
from providers.mock import MockProvider


def get_model_provider(settings, model=None):
    name = settings.vision_provider
    if name == "mock":
        return MockProvider()
    if name == "gemini":
        keys = config.load_api_keys()
        if not keys:
            print("[registry] no Gemini keys found (config/api_keys.txt or env); using mock backend")
            return MockProvider()
        from providers.gemini_multikey import MultiKeyGeminiProvider
        provider = MultiKeyGeminiProvider(keys, model=model)
        model_name = provider.model
        print(f"[registry] gemini-multikey ready with {provider.pool.status()['total']} key(s), model={model_name}")
        return provider
    raise ValueError(f"unknown provider: {name}")


# Backwards-compatible helpers. Both roles share one backend in this build, so
# callers that want shared key exhaustion should build once via get_model_provider.
def get_vision_provider(settings):
    return get_model_provider(settings)


def get_decision_provider(settings):
    return get_model_provider(settings)
