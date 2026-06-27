"""Deterministic offline provider.

Returns valid, schema-shaped JSON without any network call so the whole pipeline
can run and be tested without an API key or spend. It does not actually inspect
images, so it reports a neutral "cannot assess" result and the decision layer
resolves to not_enough_information. Use it for plumbing and CI, not accuracy.
"""

from __future__ import annotations

from providers.base import LLMProvider, ProviderResult, Usage


class MockProvider(LLMProvider):
    name = "mock"

    def text_json(self, system, user_text, schema=None, temperature=0.0, max_tokens=2048):
        data = {
            "claim_status": "not_enough_information",
            "issue_type": "unknown",
            "object_part": "unknown",
            "severity": "unknown",
            "supporting_image_ids": [],
            "justification": "Mock backend: no real inference performed.",
            "claim_mismatch": False,
        }
        return ProviderResult(data=data, usage=Usage(model="mock"), raw_text="")

    def vision_json(self, system, user_text, images, schema=None, temperature=0.0, max_tokens=2048):
        per_image = [
            {
                "image_id": getattr(img, "image_id", f"img_{i + 1}"),
                "is_relevant": False,
                "object_present": False,
                "object_matches_claim": False,
                "claimed_part_visible": False,
                "clarity": "unknown",
                "observations": [],
                "tampering_signs": False,
                "screenshot_signs": False,
                "in_image_text_present": False,
                "in_image_instruction_present": False,
                "notes": "mock backend",
            }
            for i, img in enumerate(images)
        ]
        return ProviderResult(
            data={"images": per_image},
            usage=Usage(model="mock", image_count=len(images)),
            raw_text="",
        )
