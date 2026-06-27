"""Vision stage (Call 1).

Sends all of a claim's images in one request and returns one ImageFacts per
image. The per-image image_id label added by the provider lets the model tie
findings back to the right image; here we re-key by image_id and guarantee one
ImageFacts per submitted image even if the model drops or reorders entries.
"""

from __future__ import annotations

import config
import schemas


def build_vision_schema(claim_object: str) -> dict:
    parts = list(config.OBJECT_PARTS.get(claim_object, ("unknown",)))
    observation = {
        "type": "OBJECT",
        "properties": {
            "issue_type": {"type": "STRING", "enum": list(config.ISSUE_TYPES)},
            "object_part": {"type": "STRING", "enum": parts},
            "severity": {"type": "STRING", "enum": list(config.SEVERITIES)},
            "confidence": {"type": "NUMBER"},
        },
        "required": ["issue_type", "object_part", "severity"],
    }
    image = {
        "type": "OBJECT",
        "properties": {
            "image_id": {"type": "STRING"},
            "is_relevant": {"type": "BOOLEAN"},
            "object_present": {"type": "BOOLEAN"},
            "object_matches_claim": {"type": "BOOLEAN"},
            "claimed_part_visible": {"type": "BOOLEAN"},
            "clarity": {"type": "STRING", "enum": list(schemas.CLARITY_VALUES)},
            "observations": {"type": "ARRAY", "items": observation},
            "tampering_signs": {"type": "BOOLEAN"},
            "screenshot_signs": {"type": "BOOLEAN"},
            "in_image_text_present": {"type": "BOOLEAN"},
            "in_image_instruction_present": {"type": "BOOLEAN"},
            "notes": {"type": "STRING"},
        },
        "required": ["image_id", "object_present", "claimed_part_visible", "clarity"],
    }
    return {
        "type": "OBJECT",
        "properties": {
            "images": {"type": "ARRAY", "items": image},
            "cross_image_consistency": {"type": "STRING", "enum": list(schemas.CONSISTENCY_VALUES)},
        },
        "required": ["images", "cross_image_consistency"],
    }


def run_vision(provider, record, prepared_images, variant=""):
    """Return (list[ImageFacts], cross_image_consistency, usage_or_None)."""
    if not prepared_images:
        return [], "unknown", None

    system = config.load_prompt(f"vision_system{variant}.txt")
    user_text = config.load_prompt("vision_user.txt").format(
        claim_object=record.claim_object,
        claim_summary=(record.user_claim or "").strip()[:700],
        image_count=len(prepared_images),
    )
    schema = build_vision_schema(record.claim_object)
    result = provider.vision_json(
        system, user_text, prepared_images, schema=schema,
        temperature=config.VISION_TEMPERATURE, max_tokens=config.MAX_OUTPUT_TOKENS,
    )

    by_id = {
        str(entry.get("image_id")): entry
        for entry in (result.data.get("images") or [])
        if isinstance(entry, dict)
    }
    facts = [
        schemas.ImageFacts.from_model_dict(
            by_id.get(img.image_id, {}), img.image_id, record.claim_object)
        for img in prepared_images
    ]

    # A single image cannot be inconsistent with itself.
    if len(prepared_images) < 2:
        consistency = "consistent"
    else:
        consistency = schemas.snap_enum(
            result.data.get("cross_image_consistency"), schemas.CONSISTENCY_VALUES, "unknown")
    return facts, consistency, result.usage
