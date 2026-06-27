"""Typed structures for model outputs and the final CSV row.

Model output is treated as untrusted. The from_model_dict constructors pull each
field defensively and snap it onto the closest allowed value, falling back to a
safe default when the model returns something unexpected. This keeps every value
written to output.csv inside the allowed vocabularies in config.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import config


def snap_enum(value, allowed, default: str) -> str:
    """Return value normalised onto one of the allowed options, else default."""
    if value is None:
        return default
    text = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    return text if text in allowed else default


def to_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("true", "yes", "1", "y"):
        return True
    if text in ("false", "no", "0", "n"):
        return False
    return default


def bool_str(value: bool) -> str:
    return "true" if value else "false"


def join_ids(ids, empty: str = "none") -> str:
    """Join identifiers with semicolons, dropping blanks and 'none', preserving
    order and removing duplicates. Returns empty marker when nothing remains."""
    seen = []
    for item in ids or []:
        token = str(item).strip()
        if not token or token.lower() == "none":
            continue
        if token not in seen:
            seen.append(token)
    return ";".join(seen) if seen else empty


@dataclass
class ImageObservation:
    issue_type: str = "unknown"
    object_part: str = "unknown"
    severity: str = "unknown"
    confidence: float = 0.0

    @classmethod
    def from_model_dict(cls, d: dict, claim_object: str) -> "ImageObservation":
        parts = config.OBJECT_PARTS.get(claim_object, ("unknown",))
        try:
            conf = float(d.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        return cls(
            issue_type=snap_enum(d.get("issue_type"), config.ISSUE_TYPES, "unknown"),
            object_part=snap_enum(d.get("object_part"), parts, "unknown"),
            severity=snap_enum(d.get("severity"), config.SEVERITIES, "unknown"),
            confidence=max(0.0, min(1.0, conf)),
        )


# How clearly an image shows the claimed subject. Mirrors the visibility-related
# risk flags so the risk layer can translate directly.
CLARITY_VALUES = (
    "clear", "blurry", "cropped_or_obstructed", "low_light_or_glare",
    "wrong_angle", "unknown",
)

# Whether the images in one claim appear to show the same object.
CONSISTENCY_VALUES = ("consistent", "inconsistent", "unknown")


@dataclass
class ImageFacts:
    """What the vision call reports about a single image."""

    image_id: str
    is_relevant: bool = False
    object_present: bool = False
    object_matches_claim: bool = False
    claimed_part_visible: bool = False
    clarity: str = "unknown"
    observations: list = field(default_factory=list)
    tampering_signs: bool = False
    screenshot_signs: bool = False
    in_image_text_present: bool = False
    in_image_instruction_present: bool = False
    notes: str = ""

    @classmethod
    def from_model_dict(cls, d: dict, image_id: str, claim_object: str) -> "ImageFacts":
        raw_obs = d.get("observations") or d.get("observed_issues") or []
        observations = [
            ImageObservation.from_model_dict(o, claim_object)
            for o in raw_obs if isinstance(o, dict)
        ]
        return cls(
            image_id=image_id,
            is_relevant=to_bool(d.get("is_relevant")),
            object_present=to_bool(d.get("object_present")),
            object_matches_claim=to_bool(d.get("object_matches_claim")),
            claimed_part_visible=to_bool(d.get("claimed_part_visible")),
            clarity=snap_enum(d.get("clarity"), CLARITY_VALUES, "unknown"),
            observations=observations,
            tampering_signs=to_bool(d.get("tampering_signs")),
            screenshot_signs=to_bool(d.get("screenshot_signs")),
            in_image_text_present=to_bool(d.get("in_image_text_present")),
            in_image_instruction_present=to_bool(d.get("in_image_instruction_present")),
            notes=str(d.get("notes", ""))[:500],
        )


@dataclass
class Decision:
    """What the decision call returns for one claim."""

    claim_status: str = "not_enough_information"
    issue_type: str = "unknown"
    object_part: str = "unknown"
    severity: str = "unknown"
    supporting_image_ids: list = field(default_factory=list)
    justification: str = ""
    claim_mismatch: bool = False

    @classmethod
    def from_model_dict(cls, d: dict, claim_object: str) -> "Decision":
        parts = config.OBJECT_PARTS.get(claim_object, ("unknown",))
        ids = d.get("supporting_image_ids") or []
        if isinstance(ids, str):
            ids = [x.strip() for x in ids.replace(";", ",").split(",")]
        return cls(
            claim_status=snap_enum(d.get("claim_status"), config.CLAIM_STATUSES, "not_enough_information"),
            issue_type=snap_enum(d.get("issue_type"), config.ISSUE_TYPES, "unknown"),
            object_part=snap_enum(d.get("object_part"), parts, "unknown"),
            severity=snap_enum(d.get("severity"), config.SEVERITIES, "unknown"),
            supporting_image_ids=[str(i).strip() for i in ids if str(i).strip()],
            justification=str(d.get("justification", "")).strip()[:600],
            claim_mismatch=to_bool(d.get("claim_mismatch")),
        )


@dataclass
class OutputRow:
    """One row of output.csv. to_csv_dict serialises in the exact column order."""

    user_id: str
    image_paths: str
    user_claim: str
    claim_object: str
    evidence_standard_met: bool
    evidence_standard_met_reason: str
    risk_flags: list
    issue_type: str
    object_part: str
    claim_status: str
    claim_status_justification: str
    supporting_image_ids: list
    valid_image: bool
    severity: str

    def to_csv_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "image_paths": self.image_paths,
            "user_claim": self.user_claim,
            "claim_object": self.claim_object,
            "evidence_standard_met": bool_str(self.evidence_standard_met),
            "evidence_standard_met_reason": self.evidence_standard_met_reason,
            "risk_flags": join_ids(self.risk_flags),
            "issue_type": self.issue_type,
            "object_part": self.object_part,
            "claim_status": self.claim_status,
            "claim_status_justification": self.claim_status_justification,
            "supporting_image_ids": join_ids(self.supporting_image_ids),
            "valid_image": bool_str(self.valid_image),
            "severity": self.severity,
        }


if __name__ == "__main__":
    assert snap_enum("Glass Shatter", config.ISSUE_TYPES, "unknown") == "glass_shatter"
    assert snap_enum("back light", config.OBJECT_PARTS["car"], "unknown") == "unknown"
    assert to_bool("TRUE") is True and to_bool("nope", False) is False

    decision = Decision.from_model_dict(
        {
            "claim_status": "Supported", "issue_type": "dent",
            "object_part": "rear_bumper", "severity": "Medium",
            "supporting_image_ids": "img_1; img_2", "justification": "visible dent",
        },
        "car",
    )
    assert decision.claim_status == "supported"
    assert decision.supporting_image_ids == ["img_1", "img_2"]

    row = OutputRow(
        "user_1", "images/test/case_x/img_1.jpg", "claim text", "car",
        True, "part visible", [], "dent", "rear_bumper", "supported",
        "dent visible in img_1", ["img_1"], True, "medium",
    ).to_csv_dict()
    assert row["risk_flags"] == "none"
    assert row["evidence_standard_met"] == "true"
    assert list(row.keys()) == list(config.OUTPUT_COLUMNS)
    print("schemas self-test OK")
